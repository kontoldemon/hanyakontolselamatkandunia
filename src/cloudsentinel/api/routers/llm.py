"""LLM status, threat summary, chat, and runtime config routes."""

from __future__ import annotations

from typing import Any, Callable

import structlog
from fastapi import APIRouter, Depends, HTTPException

from ...config import Settings, secret_to_str
from ...runtime_config import RuntimeConfigStore

logger = structlog.get_logger("cloudsentinel.api.routers.llm")


def build_llm_router(
    settings: Settings,
    require_auth: Callable[..., Any],
    config_store: RuntimeConfigStore,
) -> APIRouter:
    router = APIRouter()

    @router.get("/llm/status", dependencies=[Depends(require_auth)])
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

    @router.post("/threat-summary", dependencies=[Depends(require_auth)])
    async def threat_summary(body: dict[str, Any]) -> dict[str, Any]:
        session_id = str(body.get("session_id") or body.get("id") or "latest")
        try:
            from ...threat_reporter import generate_report

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
            logger.warning("Threat summary failed: %s", exc)
            return {
                "ok": False,
                "error": "AI summary unavailable",
                "report": {
                    "session_id": session_id,
                    "summary": "AI summary unavailable on sensor",
                    "primary_objective": "Unknown",
                    "confidence": 0,
                    "model_used": "none",
                },
            }

    @router.post("/llm/chat", dependencies=[Depends(require_auth)])
    async def llm_chat(body: dict[str, Any]) -> dict[str, Any]:
        prompt = str(body.get("prompt") or "")
        context = str(body.get("context") or "")
        try:
            from ...threat_reporter import chat_with_agent

            response_text = await chat_with_agent(prompt, context)
            return {"ok": True, "response": response_text}
        except Exception as exc:
            logger.warning("LLM chat failed: %s", exc)
            return {"ok": False, "error": "AI assistant unavailable"}

    @router.get("/llm/config", dependencies=[Depends(require_auth)])
    async def get_llm_config() -> dict[str, Any]:
        llm = config_store.snapshot()["llm"]
        return {
            "ok": True,
            "available": llm["has_api_key"],
            "api_key": secret_to_str(settings.llm.api_key),
            **llm,
        }

    @router.post("/llm/config", dependencies=[Depends(require_auth)])
    async def llm_config(body: dict[str, Any]) -> dict[str, Any]:
        try:
            llm = config_store.update({"llm": body})["llm"]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "available": llm["has_api_key"],
            "api_key": secret_to_str(settings.llm.api_key),
            **llm,
        }

    return router
