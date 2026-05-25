"""CloudSentinel Admin API — JWT-protected health, stats, attack graphs."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings
from .pipeline import EventPipeline

security = HTTPBearer(auto_error=False)


def create_admin_app(settings: Settings, pipeline: EventPipeline, soar: Any = None) -> FastAPI:
    app = FastAPI(
        title="CloudSentinel Admin API",
        version="2.0.0",
        docs_url="/docs" if settings.admin.enabled else None,
        redoc_url=None,
    )

    # ── Auth dependency ──────────────────────────────────────────
    async def require_auth(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
    ) -> bool:
        try:
            from .auth import get_auth
            auth = get_auth()
            if not auth.config.enabled:
                return True
            if credentials is None:
                raise HTTPException(status_code=401, detail="Missing authorization header")
            payload = auth.validate_token(credentials.credentials)
            if payload is None:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            return True
        except HTTPException:
            raise
        except Exception:
            return True  # Degrade gracefully if auth module unavailable

    # ── Health ────────────────────────────────────────────────────
    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {
            "ok": True,
            "hostname": settings.honeypot.hostname,
            "redis_connected": pipeline.connected,
            "pending_events": pipeline.pending_count,
        }

    # ── Readiness ─────────────────────────────────────────────────
    @app.get("/readiness", dependencies=[Depends(require_auth)])
    async def readiness() -> dict[str, Any]:
        checks = {
            "redis_connected": pipeline.connected,
            "clickhouse_ok": getattr(pipeline, "_connected", False),
            "stream_enabled": True,
            "ok": pipeline.connected,
        }
        return checks


    # ── Prometheus Metrics ──────────────────────────────────────
    @app.get("/metrics")
    async def metrics_endpoint() -> Response:
        """Prometheus /metrics endpoint (scraped by Prometheus)."""
        try:
            from .metrics import get_metrics
            m = get_metrics()
            return Response(content=m.render(), media_type=m.content_type)
        except Exception:
            return Response(content="# CloudSentinel metrics unavailable\n", media_type="text/plain")

    # ── Stats ─────────────────────────────────────────────────────
    @app.get("/stats", dependencies=[Depends(require_auth)])
    async def stats() -> dict[str, Any]:
        data: dict[str, Any] = {
            "pending_events": pipeline.pending_count,
            "session_scores": dict(pipeline.session_scores) if hasattr(pipeline, "session_scores") else {},
        }
        # Metrics integration
        try:
            from .metrics import get_metrics
            m = get_metrics()
            data.update({
                "active_sessions": m.active_sessions,
                "total_connections": m.total_connections,
                "total_auth_failures": m.total_auth_failures,
                "total_auth_successes": m.total_auth_successes,
                "total_commands": m.total_commands,
                "total_blocks": m.total_blocks,
                "total_blocks_iptables": m.total_blocks_iptables,
                "mttb_ms": m.mttb_ms,
                "blocked_ips_current": len(m.blocked_ips),
                "uptime_seconds": __import__("time").time() - m.start_time,
            })
        except Exception:
            pass
        return data

    # ── Attack Graph ──────────────────────────────────────────────
    @app.get("/attack-graph", dependencies=[Depends(require_auth)])
    async def attack_graph() -> dict[str, Any]:
        """Return SOAR attack chains as graph nodes/edges for visualization."""
        nodes: list[dict] = []
        edges: list[dict] = []

        if soar is not None:
            try:
                chains = soar.get_attack_chains()
                for i, chain in enumerate(chains):
                    node_id = f"ip-{i}"
                    nodes.append({
                        "id": node_id,
                        "type": "attacker",
                        "label": chain["ip"],
                        "sessions": chain["sessions"],
                        "risk": chain["risk"],
                        "techniques": chain["techniques"],
                    })
                    # Edge to honeypot
                    edges.append({
                        "id": f"edge-{i}",
                        "source": node_id,
                        "target": "honeypot",
                        "label": f"{chain['sessions']} sessions",
                    })
                    # Technique nodes
                    for tech in chain.get("techniques", [])[:3]:
                        tech_id = f"tech-{tech}"
                        if not any(n["id"] == tech_id for n in nodes):
                            nodes.append({
                                "id": tech_id,
                                "type": "technique",
                                "label": tech,
                            })
                        edges.append({
                            "id": f"edge-{node_id}-{tech_id}",
                            "source": node_id,
                            "target": tech_id,
                        })
            except Exception:
                pass

        # Always add honeypot node
        nodes.append({
            "id": "honeypot",
            "type": "honeypot",
            "label": settings.honeypot.hostname,
        })

        return {"nodes": nodes, "edges": edges}

    # ── Anomaly Stats ─────────────────────────────────────────────
    @app.get("/anomaly-stats", dependencies=[Depends(require_auth)])
    async def anomaly_stats() -> dict[str, Any]:
        try:
            from .anomaly import CommandAnomalyDetector
            # Return placeholder — detector instance is on server
            return {"available": True, "note": "Anomaly detector active on sensor"}
        except Exception:
            return {"available": False}

    # ── Auth Login ────────────────────────────────────────────────
    @app.post("/auth/login")
    async def login(body: dict[str, str]) -> dict[str, Any]:
        try:
            from .auth import get_auth
            auth = get_auth()
            if not auth.config.enabled:
                return {"message": "Auth not enabled", "token": "dev-mode"}
            username = body.get("username", "")
            password = body.get("password", "")
            # Simple credential check (env-based)
            import os
            expected_user = os.getenv("CLOUDSENTINEL_ADMIN_USER", "admin")
            expected_pass = os.getenv("CLOUDSENTINEL_ADMIN_PASS", "cloudsentinel")
            if username != expected_user or password != expected_pass:
                raise HTTPException(status_code=401, detail="Invalid credentials")
            return auth.create_login_token(username)
        except HTTPException:
            raise
        except Exception:
            return {"message": "Auth module unavailable", "token": "dev-mode"}

    # ── DNS Stats ─────────────────────────────────────────────────
    @app.get("/dns-stats", dependencies=[Depends(require_auth)])
    async def dns_stats() -> dict[str, Any]:
        return {"available": True, "note": "DNS honeypot stats available on sensor"}

    return app
