"""Stats, attack distribution, attack graph, and anomaly routes."""

from __future__ import annotations

import time
from typing import Any, Callable

from fastapi import APIRouter, Depends

from ...config import Settings
from ...pipeline import EventPipeline
from .. import queries


def build_analytics_router(
    settings: Settings,
    pipeline: EventPipeline,
    require_auth: Callable[..., Any],
    hot_cache_get: Callable[..., Any],
    hot_cache_set: Callable[..., Any],
    soar: Any,
    attack_distribution_ttl_seconds: int,
    attack_graph_ttl_seconds: int,
    anomaly: Any = None,
) -> APIRouter:
    router = APIRouter()

    @router.get("/stats", dependencies=[Depends(require_auth)])
    async def stats() -> dict[str, Any]:
        data: dict[str, Any] = {
            "pending_events": pipeline.pending_count,
            "session_scores": dict(getattr(pipeline, "session_scores", {})),
        }
        try:
            from ...metrics import get_metrics

            metrics = get_metrics()
            mttb_value = metrics.mttb_ms or await queries.load_latest_mttb_async(settings)
            data.update(
                {
                    "active_sessions": metrics.active_sessions,
                    "total_connections": metrics.total_connections,
                    "total_auth_failures": metrics.total_auth_failures,
                    "total_auth_successes": metrics.total_auth_successes,
                    "total_commands": metrics.total_commands,
                    "total_blocks": metrics.total_blocks,
                    "total_blocks_iptables": metrics.total_blocks_iptables,
                    "mttb_ms": mttb_value,
                    "blocked_ips_current": len(metrics.blocked_ips),
                    "uptime_seconds": time.time() - metrics.start_time,
                }
            )
        except Exception:
            pass
        return data

    @router.get("/attack-distribution", dependencies=[Depends(require_auth)])
    async def attack_distribution() -> list[dict[str, Any]]:
        strict_truth = queries._strict_truth_mode_enabled()
        if strict_truth:
            cached_payload, _ = await hot_cache_get("attack-distribution:strict")
            if isinstance(cached_payload, list):
                return cached_payload
        metrics_data = await queries.load_attack_distribution_async(settings)
        if not strict_truth:
            try:
                from ...metrics import get_metrics

                metrics = get_metrics()
                metrics_data["Brute Force"] = max(
                    int(metrics_data.get("Brute Force", 0)),
                    int(metrics.total_auth_failures),
                )
                metrics_data["Command Injection"] = max(
                    int(metrics_data.get("Command Injection", 0)),
                    int(metrics.total_commands),
                )
            except Exception:
                pass
        payload = [
            {"name": "Brute Force", "value": metrics_data["Brute Force"], "fill": "#ef4444"},
            {
                "name": "Command Injection",
                "value": metrics_data["Command Injection"],
                "fill": "#f97316",
            },
            {"name": "Port Scanning", "value": metrics_data["Port Scanning"], "fill": "#eab308"},
            {"name": "Malware Upload", "value": metrics_data["Malware Upload"], "fill": "#8b5cf6"},
        ]
        if strict_truth:
            await hot_cache_set(
                "attack-distribution:strict",
                payload,
                attack_distribution_ttl_seconds,
            )
        return payload

    @router.get("/attack-graph", dependencies=[Depends(require_auth)])
    async def attack_graph() -> dict[str, Any]:
        strict_truth = queries._strict_truth_mode_enabled()
        if strict_truth:
            cached_payload, _ = await hot_cache_get("attack-graph:strict")
            if isinstance(cached_payload, dict) and isinstance(cached_payload.get("nodes"), list):
                return cached_payload
        nodes: list[dict[str, Any]] = [
            {"id": "honeypot", "type": "honeypot", "label": settings.honeypot.hostname}
        ]
        edges: list[dict[str, Any]] = []
        used_soar = False

        if not strict_truth and soar is not None:
            used_soar = True
            for i, chain in enumerate(soar.get_attack_chains()):
                node_id = f"ip-{i}"
                nodes.append(
                    {
                        "id": node_id,
                        "type": "attacker",
                        "label": chain["ip"],
                        "sessions": chain["sessions"],
                        "risk": chain["risk"],
                        "techniques": chain["techniques"],
                    }
                )
                edges.append(
                    {
                        "id": f"edge-{i}",
                        "source": node_id,
                        "target": "honeypot",
                        "label": f"{chain['sessions']} sessions",
                    }
                )
                for tech in chain.get("techniques", [])[:3]:
                    tech_id = f"tech-{tech}"
                    if not any(node["id"] == tech_id for node in nodes):
                        nodes.append({"id": tech_id, "type": "technique", "label": tech})
                    edges.append(
                        {"id": f"edge-{node_id}-{tech_id}", "source": node_id, "target": tech_id}
                    )
        if len(nodes) <= 1:
            clickhouse_graph = await queries.load_attack_graph_async(settings)
            nodes.extend(clickhouse_graph.get("nodes", []))
            edges.extend(clickhouse_graph.get("edges", []))
        payload = {
            "nodes": nodes,
            "edges": edges,
            "source": "clickhouse" if strict_truth else ("mixed" if used_soar else "clickhouse"),
            "authoritative": strict_truth,
            "sourceBreakdown": {
                "graph": "clickhouse" if strict_truth else ("mixed" if used_soar else "clickhouse")
            },
        }
        if strict_truth:
            await hot_cache_set("attack-graph:strict", payload, attack_graph_ttl_seconds)
        return payload

    @router.get("/anomaly-stats", dependencies=[Depends(require_auth)])
    async def anomaly_stats() -> dict[str, Any]:
        stats = getattr(anomaly, "stats", None)
        if not isinstance(stats, dict):
            return {"available": False}
        return {"available": True, **stats}

    return router
