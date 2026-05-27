"""
CloudSentinel AI Threat Reporter powered by litellm.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger("cloudsentinel.threat_reporter")


class ThreatReport:
    __slots__ = (
        "attacker_ip",
        "city",
        "commands",
        "confidence",
        "country",
        "generated_at",
        "hassh",
        "mitre_techniques",
        "model_used",
        "primary_objective",
        "risk_score",
        "session_id",
        "summary",
    )

    def __init__(
        self,
        session_id: str,
        attacker_ip: str,
        country: str = "Unknown",
        city: str = "Unknown",
        risk_score: int = 0,
        mitre_techniques: list[str] | None = None,
        hassh: str | None = None,
        commands: list[str] | None = None,
    ) -> None:
        self.session_id = session_id
        self.attacker_ip = attacker_ip
        self.country = country
        self.city = city
        self.risk_score = risk_score
        self.mitre_techniques = mitre_techniques or []
        self.hassh = hassh or ""
        self.commands = commands or []
        self.summary = ""
        self.primary_objective = "Unknown"
        self.confidence = 0.0
        self.model_used = "none"
        self.generated_at = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "attacker_ip": self.attacker_ip,
            "country": self.country,
            "city": self.city,
            "risk_score": self.risk_score,
            "mitre_techniques": self.mitre_techniques,
            "hassh": self.hassh,
            "commands": self.commands,
            "summary": self.summary,
            "primary_objective": self.primary_objective,
            "confidence": self.confidence,
            "model_used": self.model_used,
            "generated_at": self.generated_at,
        }


def _empty_session_data(session_id: str) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "attacker_ip": "",
        "commands": [],
        "risk_score": 0,
        "mitre_techniques": [],
        "hassh": "",
    }


async def fetch_session_data(session_id: str, redis_url: str = "") -> dict[str, Any]:
    if not redis_url:
        return _empty_session_data(session_id)
    try:
        import redis.asyncio as aioredis

        redis = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        commands = await redis.lrange(f"cloudsentinel:session:{session_id}:commands", 0, -1)
        ip = await redis.get(f"cloudsentinel:session:{session_id}:ip") or ""
        risk = await redis.get(f"cloudsentinel:session:{session_id}:risk") or "0"
        techniques = await redis.smembers(f"soar:session:{session_id}:techniques")
        hassh = await redis.get(f"soar:session:{session_id}:hassh") or ""
        await redis.aclose()
        return {
            "session_id": session_id,
            "attacker_ip": ip,
            "commands": list(commands) if commands else [],
            "risk_score": int(risk),
            "mitre_techniques": list(techniques),
            "hassh": hassh,
        }
    except Exception as exc:
        logger.debug("Redis session fetch failed: %s", exc)
        return _empty_session_data(session_id)


def _build_analysis_prompt(report: ThreatReport) -> str:
    commands_text = "\n".join(f"  $ {cmd}" for cmd in report.commands[:80])
    techniques_text = ", ".join(report.mitre_techniques[:20]) or "none detected"
    return (
        "You are a cyber threat intelligence analyst.\n"
        "Analyze this honeypot session and return JSON only.\n\n"
        f"Attacker IP: {report.attacker_ip} ({report.city}, {report.country})\n"
        f"Risk Score: {report.risk_score}/100\n"
        f"MITRE Techniques: {techniques_text}\n"
        f"HASSH: {report.hassh or 'N/A'}\n\n"
        "Commands:\n"
        f"{commands_text}\n\n"
        '{"summary":"...", "primary_objective":"...", "confidence":0.0}'
    )


def _parse_json_response(text: str, model: str) -> dict[str, Any]:
    content = text.strip()
    if "```json" in content:
        start = content.index("```json") + 7
        end = content.find("```", start)
        content = content[start:] if end == -1 else content[start:end]
    elif "```" in content:
        start = content.index("```") + 3
        end = content.find("```", start)
        content = content[start:] if end == -1 else content[start:end]
    try:
        parsed = json.loads(content.strip())
        parsed["model_used"] = model
        return parsed
    except json.JSONDecodeError:
        return {
            "summary": content[:700] if content else "LLM returned non-JSON output",
            "primary_objective": "Unknown",
            "confidence": 0.2,
            "model_used": model,
        }


async def _call_litellm(prompt: str) -> dict[str, Any]:
    try:
        from litellm import acompletion
    except ImportError:
        return {
            "summary": "litellm not installed on sensor",
            "primary_objective": "Unknown",
            "confidence": 0.0,
            "model_used": "none",
        }

    model = os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash")
    fallback_raw = os.getenv(
        "LLM_FALLBACK_MODELS",
        "groq/llama-3.3-70b-versatile,openai/gpt-4o-mini",
    )
    fallbacks = [{"model": m.strip()} for m in fallback_raw.split(",") if m.strip()]
    try:
        response = await acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=700,
            fallbacks=fallbacks or None,
        )
        text = str(response.choices[0].message.content or "")
        return _parse_json_response(text, model)
    except Exception as exc:
        logger.warning("litellm analysis failed: %s", exc)
        return {
            "summary": "LLM analysis unavailable",
            "primary_objective": "Unknown",
            "confidence": 0.0,
            "model_used": "none",
        }


async def generate_report(
    session_id: str,
    redis_url: str = "",
    attacker_ip: str = "",
    country: str = "Unknown",
    city: str = "Unknown",
    risk_score: int = 0,
    mitre_techniques: list[str] | None = None,
    hassh: str | None = None,
    commands: list[str] | None = None,
) -> ThreatReport:
    if redis_url and not attacker_ip and not commands:
        data = await fetch_session_data(session_id, redis_url)
        attacker_ip = data.get("attacker_ip", attacker_ip)
        commands = commands or data.get("commands", [])
        risk_score = risk_score or data.get("risk_score", 0)
        mitre_techniques = mitre_techniques or data.get("mitre_techniques", [])
        hassh = hassh or data.get("hassh", "")

    report = ThreatReport(
        session_id=session_id,
        attacker_ip=attacker_ip or "unknown",
        country=country,
        city=city,
        risk_score=risk_score,
        mitre_techniques=mitre_techniques,
        hassh=hassh,
        commands=commands or [],
    )
    if not report.commands:
        report.summary = "No command telemetry captured for this session yet."
        report.primary_objective = "Unknown"
        report.confidence = 0.0
        report.model_used = "none"
        report.generated_at = datetime.now(UTC).isoformat()
        return report

    analysis = await _call_litellm(_build_analysis_prompt(report))
    report.summary = analysis.get("summary", "Analysis unavailable")
    report.primary_objective = analysis.get("primary_objective", "Unknown")
    report.confidence = float(analysis.get("confidence", 0.0))
    report.model_used = analysis.get("model_used", "unknown")
    report.generated_at = datetime.now(UTC).isoformat()
    return report


async def generate_report_string(report: ThreatReport) -> str:
    techniques = ", ".join(report.mitre_techniques) if report.mitre_techniques else "none"
    return (
        "CLOUDSENTINEL AI THREAT REPORT\n"
        f"Session:    {report.session_id}\n"
        f"Attacker:   {report.attacker_ip} ({report.city}, {report.country})\n"
        f"Risk:       {report.risk_score}/100\n"
        f"Objective:  {report.primary_objective}\n"
        f"Confidence: {report.confidence:.0%}\n"
        f"Model:      {report.model_used}\n"
        f"Techniques: {techniques}\n"
        f"HASSH:      {report.hassh or 'N/A'}\n"
        f"Generated:  {report.generated_at}\n"
        f"{report.summary}\n"
    )


async def main() -> None:
    report = await generate_report("session_demo_001")
    print(await generate_report_string(report))
    print(json.dumps(report.to_dict(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
