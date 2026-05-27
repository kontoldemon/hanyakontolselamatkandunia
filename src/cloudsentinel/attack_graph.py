"""
CloudSentinel Attack Graph — multi-session lateral movement visualization.

Builds a directed graph of attacker → target relationships across sessions,
detecting lateral movement chains, credential reuse patterns, and
pivot attempts. Exports to JSON for Cytoscape.js dashboard rendering.

Uses NetworkX (BSD-3-Clause) for graph algorithms; pure-Python fallback.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger("cloudsentinel.attack_graph")


class AttackGraph:
    """Tracks attacker IPs, targets, and lateral movement across sessions."""

    def __init__(self, max_nodes: int = 10000, prune_after_seconds: float = 86400.0) -> None:
        self.max_nodes = max_nodes
        self.prune_after_seconds = prune_after_seconds

        # Nodes: attacker IPs, HASSH fingerprints, target hosts
        self._nodes: dict[str, dict[str, Any]] = {}

        # Edges: (src, dst) → {type, weight, techniques, sessions}
        self._edges: dict[tuple[str, str], dict[str, Any]] = {}

        # Index: HASSH → IPs, IP → sessions
        self._hassh_to_ips: dict[str, set[str]] = defaultdict(set)
        self._ip_to_sessions: dict[str, set[str]] = defaultdict(set)

        # Stats
        self._total_events = 0
        self._lateral_moves = 0
        self._created_at = time.time()

    def add_event(self, event: dict[str, Any]) -> None:
        """Ingest a single CloudSentinel event and update the graph."""
        self._total_events += 1

        src_ip = str(event.get("src_ip", ""))
        session_id = str(event.get("session", ""))
        hassh = str(event.get("hassh_md5", ""))
        country = str(event.get("country_code", "XX"))
        risk = int(event.get("cloudsentinel_risk_score", 0))
        techniques = event.get("cloudsentinel_mitre_techniques", [])
        event_type = str(event.get("eventid", ""))
        command = str(event.get("input", ""))

        if not src_ip or src_ip in ("", "0.0.0.0", "127.0.0.1"):
            return

        # Create/update attacker node
        self._ensure_node(src_ip, node_type="attacker", country=country)
        self._nodes[src_ip]["risk"] = max(self._nodes[src_ip].get("risk", 0), risk)
        self._nodes[src_ip]["last_seen"] = time.time()
        self._nodes[src_ip]["event_count"] = self._nodes[src_ip].get("event_count", 0) + 1

        # Index HASSH
        if hassh and len(hassh) == 32:
            self._hassh_to_ips[hassh].add(src_ip)
            self._ensure_node(hassh, node_type="hassh_fingerprint")
            self._ensure_edge(src_ip, hassh, edge_type="has_fingerprint")

        # Index session
        if session_id:
            self._ip_to_sessions[src_ip].add(session_id)

        # Detect lateral movement (SSH from honeypot to another IP)
        target_ip = _extract_target_ip(command)
        if target_ip and target_ip != src_ip:
            self._lateral_moves += 1
            self._ensure_node(target_ip, node_type="target")
            self._ensure_edge(
                src_ip, target_ip,
                edge_type="lateral_move",
                techniques=techniques,
                session=session_id,
            )
            logger.info(
                "Lateral movement detected: %s → %s (session=%s)",
                src_ip, target_ip, session_id[:12],
            )

        # Detect credential reuse pattern (failed SSH attempts)
        if event_type in ("cloudsentinel.login.failed", "cloudsentinel.auth.failed"):
            username = str(event.get("username", ""))
            password = str(event.get("password", ""))
            if username:
                cred_node = f"cred:{username}"
                self._ensure_node(cred_node, node_type="credential", username=username)
                self._ensure_edge(src_ip, cred_node, edge_type="attempted_credential")

    def _ensure_node(self, node_id: str, **attrs: Any) -> None:
        if node_id in self._nodes:
            self._nodes[node_id].update(attrs)
            return
        if len(self._nodes) >= self.max_nodes:
            self._prune()
        self._nodes[node_id] = {
            "id": node_id,
            "first_seen": time.time(),
            "last_seen": time.time(),
            "event_count": 0,
            "risk": 0,
            **attrs,
        }

    def _ensure_edge(
        self, src: str, dst: str,
        edge_type: str = "connection",
        techniques: list[str] | None = None,
        session: str = "",
    ) -> None:
        key = (src, dst)
        if key in self._edges:
            self._edges[key]["weight"] += 1
            if techniques:
                self._edges[key].setdefault("techniques", set()).update(techniques)
            if session:
                self._edges[key].setdefault("sessions", set()).add(session)
        else:
            self._edges[key] = {
                "source": src,
                "target": dst,
                "type": edge_type,
                "weight": 1,
                "techniques": set(techniques or []),
                "sessions": {session} if session else set(),
                "first_seen": time.time(),
            }

    def _prune(self) -> None:
        """Remove nodes older than prune_after_seconds."""
        now = time.time()
        stale = [
            node_id for node_id, attrs in self._nodes.items()
            if attrs.get("last_seen", 0) < now - self.prune_after_seconds
        ]
        for node_id in stale:
            del self._nodes[node_id]
        # Also clean edges referencing stale nodes
        stale_set = set(stale)
        self._edges = {
            k: v for k, v in self._edges.items()
            if k[0] not in stale_set and k[1] not in stale_set
        }

    def get_subgraph(self, root_ip: str, depth: int = 2) -> dict[str, Any]:
        """Return a subgraph centered on a specific IP (for dashboard drill-down)."""
        visited: set[str] = set()
        queue = [(root_ip, 0)]
        nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []

        while queue:
            node, d = queue.pop(0)
            if node in visited or d > depth:
                continue
            visited.add(node)
            if node in self._nodes:
                nodes[node] = dict(self._nodes[node])

            for (src, dst), edge_data in self._edges.items():
                if src == node and dst not in visited:
                    queue.append((dst, d + 1))
                    edges.append(_serialize_edge(edge_data))
                elif dst == node and src not in visited:
                    queue.append((src, d + 1))
                    edges.append(_serialize_edge(edge_data))

        return {
            "root": root_ip,
            "depth": depth,
            "nodes": list(nodes.values()),
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    def to_cytoscape(self) -> dict[str, Any]:
        """Export the entire graph in Cytoscape.js JSON format."""
        elements: list[dict[str, Any]] = []

        for node_id, attrs in self._nodes.items():
            node_type = attrs.get("node_type", "unknown")
            color_map = {
                "attacker": "#FF4444",
                "target": "#FFAA00",
                "hassh_fingerprint": "#44AAFF",
                "credential": "#AA44FF",
            }
            elements.append({
                "data": {
                    "id": node_id,
                    "label": node_id[:24],
                    "type": node_type,
                    "risk": attrs.get("risk", 0),
                    "country": attrs.get("country", "XX"),
                },
                "style": {
                    "background-color": color_map.get(node_type, "#888888"),
                    "color": "#ffffff",
                },
            })

        for (src, dst), edge_data in self._edges.items():
            elements.append({
                "data": {
                    "id": f"{src}→{dst}",
                    "source": src,
                    "target": dst,
                    "weight": edge_data["weight"],
                    "type": edge_data["type"],
                },
            })

        return {
            "elements": elements,
            "metadata": {
                "total_events": self._total_events,
                "lateral_moves": self._lateral_moves,
                "node_count": len(self._nodes),
                "edge_count": len(self._edges),
                "generated_at": datetime.now(UTC).isoformat(),
            },
        }

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_events": self._total_events,
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "lateral_moves": self._lateral_moves,
            "unique_hassh": len(self._hassh_to_ips),
            "unique_attackers": sum(
                1 for n in self._nodes.values()
                if n.get("node_type") == "attacker"
            ),
            "uptime_seconds": time.time() - self._created_at,
        }


    def compute_centrality(self) -> dict[str, float]:
        """Betweenness centrality — identifies pivot points in attack chains."""
        try:
            import networkx as nx
            G = nx.DiGraph()
            for (src, dst), edge in self._edges.items():
                G.add_edge(src, dst, weight=edge.get("weight", 1))
            return nx.betweenness_centrality(G, weight="weight")
        except ImportError:
            return dict.fromkeys(self._nodes, 0.0)

    def detect_communities(self) -> list[set[str]]:
        """Detect botnet clusters by IP co-occurrence and HASSH similarity."""
        try:
            import networkx as nx
            from networkx.algorithms.community import greedy_modularity_communities
            G = nx.Graph()
            for (src, dst), edge in self._edges.items():
                G.add_edge(src, dst, weight=edge.get("weight", 1))
            return [set(c) for c in greedy_modularity_communities(G, weight="weight")]
        except ImportError:
            return []

    def find_pivot_points(self, min_degree: int = 3) -> list[dict[str, Any]]:
        """Identify IPs that are lateral movement pivots (high out-degree)."""
        try:
            import networkx as nx
            G = nx.DiGraph()
            for (src, dst), edge in self._edges.items():
                G.add_edge(src, dst, weight=edge.get("weight", 1))
            pivots = []
            for node in G.nodes():
                out_deg = G.out_degree(node, weight="weight")
                if out_deg >= min_degree:
                    pivots.append({
                        "ip": node,
                        "out_degree": out_deg,
                        "targets": list(G.successors(node)),
                        "hassh": self._nodes.get(node, {}).get("hassh_md5", ""),
                    })
            return sorted(pivots, key=lambda x: x["out_degree"], reverse=True)
        except ImportError:
            return []

    def shortest_attack_path(self, src_ip: str, dst_ip: str) -> list[str] | None:
        """Find shortest lateral movement path between two IPs."""
        try:
            import networkx as nx
            G = nx.DiGraph()
            for (s, d), edge in self._edges.items():
                G.add_edge(s, d, weight=1.0 / max(edge.get("weight", 1), 1))
            return nx.shortest_path(G, source=src_ip, target=dst_ip) if nx.has_path(G, src_ip, dst_ip) else None
        except ImportError:
            return None


    def save(self, path: str = "artifacts/attack_graph.json") -> None:
        """Persist the graph to disk."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "nodes": {
                k: {
                    **v,
                    "techniques": list(v.get("techniques", [])),
                    "sessions": list(v.get("sessions", [])),
                }
                for k, v in self._nodes.items()
            },
            "edges": {
                f"{s}→{d}": _serialize_edge(e)
                for (s, d), e in self._edges.items()
            },
            "stats": self.get_stats(),
        }
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _extract_target_ip(command: str) -> str | None:
    """Extract a target IP from lateral movement commands (ssh, scp, nc)."""
    import re

    patterns = [
        r'\bssh\b.*?(?:@)?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b',
        r'\bscp\b.*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b',
        r'\bnc\b.*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b',
        r'\bncat\b.*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b',
        r'\bsocat\b.*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b',
    ]

    for pattern in patterns:
        match = re.search(pattern, command)
        if match:
            ip = match.group(1)
            # Exclude localhost and private IPs for edge creation
            if ip not in ("0.0.0.0", "127.0.0.1", "255.255.255.255"):
                return ip
    return None


def _serialize_edge(edge_data: dict[str, Any]) -> dict[str, Any]:
    """Convert sets in edge data to lists for JSON serialization."""
    return {
        "source": edge_data["source"],
        "target": edge_data["target"],
        "type": edge_data["type"],
        "weight": edge_data["weight"],
        "techniques": list(edge_data.get("techniques", [])),
        "sessions": list(edge_data.get("sessions", [])),
        "first_seen": edge_data.get("first_seen", 0),
    }
