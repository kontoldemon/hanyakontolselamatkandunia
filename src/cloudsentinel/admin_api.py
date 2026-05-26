"""CloudSentinel Admin API with token/JWT auth and dashboard endpoints."""

from __future__ import annotations

import os
import time
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, secret_to_str
from .pipeline import EventPipeline

security = HTTPBearer(auto_error=False)


def create_admin_app(settings: Settings, pipeline: EventPipeline, soar: Any = None) -> FastAPI:
    app = FastAPI(
        title="CloudSentinel Admin API",
        version="2.0.0",
        docs_url="/docs" if settings.admin.enabled else None,
        redoc_url=None,
    )

    async def require_auth(
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
    ) -> bool:
        configured_token = secret_to_str(settings.admin.token)
        if configured_token:
            if credentials is None or credentials.credentials != configured_token:
                raise HTTPException(status_code=401, detail="Invalid or missing token")
            return True

        try:
            from .auth import get_auth

            auth = get_auth()
            if not auth.config.enabled:
                return True
            if credentials is None:
                raise HTTPException(status_code=401, detail="Missing authorization header")
            if auth.validate_token(credentials.credentials) is None:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            return True
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Authentication unavailable") from exc

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {
            "ok": True,
            "hostname": settings.honeypot.hostname,
            "redis_connected": pipeline.connected,
            "pending_events": pipeline.pending_count,
        }

    @app.get("/readiness", dependencies=[Depends(require_auth)])
    async def readiness() -> dict[str, Any]:
        clickhouse_enabled = bool(getattr(settings.clickhouse, "enabled", False))
        return {
            "ok": pipeline.connected or pipeline.pending_count >= 0,
            "redis_connected": pipeline.connected,
            "pending_events": pipeline.pending_count,
            "clickhouse_enabled": clickhouse_enabled,
            "stream_enabled": bool(settings.stream.enabled),
        }

    @app.get("/metrics", dependencies=[Depends(require_auth)])
    async def metrics_endpoint():
        from fastapi import Response

        try:
            from .metrics import get_metrics

            metrics = get_metrics()
            return Response(content=metrics.render(), media_type=metrics.content_type)
        except Exception:
            return Response(
                content="# CloudSentinel metrics unavailable\n",
                media_type="text/plain",
            )

    @app.get("/metrics/json", dependencies=[Depends(require_auth)])
    async def metrics_json() -> dict[str, Any]:
        try:
            from .metrics import get_metrics

            metrics = get_metrics()
            return {
                "active_sessions": metrics.active_sessions,
                "mttb_ms": metrics.mttb_ms,
                "total_connections": metrics.total_connections,
                "total_auth_failures": metrics.total_auth_failures,
                "total_auth_successes": metrics.total_auth_successes,
                "total_commands": metrics.total_commands,
                "total_blocks": metrics.total_blocks,
                "total_blocks_iptables": metrics.total_blocks_iptables,
                "blocked_ips_current": len(metrics.blocked_ips),
                "uptime_seconds": time.time() - metrics.start_time,
            }
        except Exception:
            return {"error": "metrics unavailable"}

    @app.get("/stats", dependencies=[Depends(require_auth)])
    async def stats() -> dict[str, Any]:
        data: dict[str, Any] = {
            "pending_events": pipeline.pending_count,
            "session_scores": dict(getattr(pipeline, "session_scores", {})),
        }
        try:
            from .metrics import get_metrics

            metrics = get_metrics()
            data.update(
                {
                    "active_sessions": metrics.active_sessions,
                    "total_connections": metrics.total_connections,
                    "total_auth_failures": metrics.total_auth_failures,
                    "total_auth_successes": metrics.total_auth_successes,
                    "total_commands": metrics.total_commands,
                    "total_blocks": metrics.total_blocks,
                    "total_blocks_iptables": metrics.total_blocks_iptables,
                    "mttb_ms": metrics.mttb_ms,
                    "blocked_ips_current": len(metrics.blocked_ips),
                    "uptime_seconds": time.time() - metrics.start_time,
                }
            )
        except Exception:
            pass
        return data

    @app.get("/sessions", dependencies=[Depends(require_auth)])
    async def sessions() -> dict[str, Any]:
        sessions_list: list[dict[str, Any]] = []
        if soar is not None:
            for ip, session_ids in getattr(soar, "_mem_ip_sessions", {}).items():
                profile = soar.get_ip_profile(ip) if hasattr(soar, "get_ip_profile") else {}
                sessions_list.append(
                    {
                        "id": f"sess-{ip}",
                        "ip": ip,
                        "country": "unknown",
                        "startTime": time.strftime(
                            "%H:%M:%S",
                            time.localtime(profile.get("first_seen") or time.time()),
                        ),
                        "duration": "active",
                        "client": "unknown",
                        "fingerprint": "",
                        "input": [],
                        "status": "active",
                        "sessionCount": len(session_ids),
                        "riskScore": profile.get("cumulative_risk", 0),
                        "mitreTechniques": profile.get("techniques", []),
                    }
                )
        return {"sessions": sessions_list}

    @app.get("/attack-distribution", dependencies=[Depends(require_auth)])
    async def attack_distribution() -> list[dict[str, Any]]:
        metrics_data = {
            "Brute Force": 0,
            "Command Injection": 0,
            "Port Scanning": 0,
            "Malware Upload": 0,
        }
        try:
            from .metrics import get_metrics

            metrics = get_metrics()
            metrics_data["Brute Force"] = int(metrics.total_auth_failures)
            metrics_data["Command Injection"] = int(metrics.total_commands)
        except Exception:
            pass
        return [
            {"name": "Brute Force", "value": metrics_data["Brute Force"], "fill": "#ef4444"},
            {
                "name": "Command Injection",
                "value": metrics_data["Command Injection"],
                "fill": "#f97316",
            },
            {"name": "Port Scanning", "value": metrics_data["Port Scanning"], "fill": "#eab308"},
            {"name": "Malware Upload", "value": metrics_data["Malware Upload"], "fill": "#8b5cf6"},
        ]

    @app.get("/attack-graph", dependencies=[Depends(require_auth)])
    async def attack_graph() -> dict[str, Any]:
        nodes: list[dict[str, Any]] = [
            {"id": "honeypot", "type": "honeypot", "label": settings.honeypot.hostname}
        ]
        edges: list[dict[str, Any]] = []

        if soar is not None:
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
        return {"nodes": nodes, "edges": edges}

    @app.get("/anomaly-stats", dependencies=[Depends(require_auth)])
    async def anomaly_stats() -> dict[str, Any]:
        try:
            from .anomaly import CommandAnomalyDetector  # noqa: F401

            return {"available": True, "note": "Anomaly detector active on sensor"}
        except Exception:
            return {"available": False}

    @app.get("/llm/status", dependencies=[Depends(require_auth)])
    async def llm_status() -> dict[str, Any]:
        api_key = secret_to_str(settings.llm.api_key)
        return {
            "available": bool(api_key),
            "provider": settings.llm.provider,
            "model": settings.llm.model,
            "fallback_models": settings.llm.fallback_models,
            "max_output_chars": settings.llm.max_output_chars,
            "features": {
                "command_vfs": True,
                "threat_summary": True,
                "deterministic_fallback": not bool(api_key),
            },
        }

    @app.post("/threat-summary", dependencies=[Depends(require_auth)])
    async def threat_summary(body: dict[str, Any]) -> dict[str, Any]:
        session_id = str(body.get("session_id") or body.get("id") or "latest")
        try:
            from .threat_reporter import generate_report

            report = await generate_report(
                session_id=session_id,
                redis_url=settings.redis.url,
                attacker_ip=str(body.get("attacker_ip") or body.get("ip") or ""),
                country=str(body.get("country") or "Unknown"),
                city=str(body.get("city") or "Unknown"),
                risk_score=int(body.get("risk_score") or 0),
                mitre_techniques=list(body.get("mitre_techniques") or []),
                hassh=str(body.get("hassh") or body.get("fingerprint") or ""),
                commands=list(body.get("commands") or body.get("input") or []),
            )
            return {"ok": True, "report": report.to_dict()}
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "report": {
                    "session_id": session_id,
                    "summary": "AI summary unavailable on sensor",
                    "primary_objective": "Unknown",
                    "confidence": 0,
                    "model_used": "none",
                },
            }

    @app.post("/auth/login")
    async def login(body: dict[str, str]) -> dict[str, Any]:
        try:
            from .auth import get_auth

            auth = get_auth()
            if not auth.config.enabled:
                return {"message": "Auth not enabled", "token": "dev-mode"}
            username = body.get("username", "")
            password = body.get("password", "")
            expected_user = os.getenv("CLOUDSENTINEL_ADMIN_USER", "admin")
            expected_pass = os.getenv("CLOUDSENTINEL_ADMIN_PASS", "")
            if username != expected_user or password != expected_pass:
                raise HTTPException(status_code=401, detail="Invalid credentials")
            return auth.create_login_token(username)
        except HTTPException:
            raise
        except Exception:
            return {"message": "Auth module unavailable", "token": "dev-mode"}

    return app
