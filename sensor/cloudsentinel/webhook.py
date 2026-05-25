"""
CloudSentinel Webhook Notifier — Slack, Discord, Telegram alerting.
Sends high-severity threat alerts when SOAR risk threshold is breached.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("cloudsentinel.webhook")


@dataclass
class WebhookConfig:
    """Multi-platform webhook configuration."""

    slack_url: str = ""
    discord_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    min_risk_score: int = 70
    cooldown_seconds: float = 300.0
    enabled: bool = False

    @classmethod
    def from_env(cls) -> WebhookConfig:
        return cls(
            slack_url=os.getenv("CLOUDSENTINEL_SLACK_WEBHOOK", ""),
            discord_url=os.getenv("CLOUDSENTINEL_DISCORD_WEBHOOK", ""),
            telegram_bot_token=os.getenv("CLOUDSENTINEL_TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("CLOUDSENTINEL_TELEGRAM_CHAT_ID", ""),
            min_risk_score=int(os.getenv("CLOUDSENTINEL_ALERT_THRESHOLD", "70")),
            cooldown_seconds=float(os.getenv("CLOUDSENTINEL_ALERT_COOLDOWN", "300")),
            enabled=os.getenv("CLOUDSENTINEL_WEBHOOKS_ENABLED", "false").lower() == "true",
        )


class WebhookNotifier:
    """Async multi-platform alert dispatcher with per-IP cooldown."""

    def __init__(self, config: WebhookConfig | None = None) -> None:
        self.config = config or WebhookConfig.from_env()
        self._client = httpx.AsyncClient(timeout=10.0)
        self._last_alert: dict[str, float] = {}

    async def close(self) -> None:
        await self._client.aclose()

    def _on_cooldown(self, ip: str) -> bool:
        now = asyncio.get_event_loop().time()
        last = self._last_alert.get(ip, 0)
        return (now - last) < self.config.cooldown_seconds

    async def send_alert(self, event: dict[str, Any]) -> list[str]:
        """Dispatch alert to all configured platforms."""
        if not self.config.enabled:
            return []

        ip = str(event.get("src_ip", ""))
        risk = int(event.get("cloudsentinel_risk_score", 0))

        if risk < self.config.min_risk_score:
            return []
        if self._on_cooldown(ip):
            return []

        self._last_alert[ip] = asyncio.get_event_loop().time()
        sent_to: list[str] = []
        tasks = []

        if self.config.slack_url:
            tasks.append(("slack", self._send_slack(event)))
        if self.config.discord_url:
            tasks.append(("discord", self._send_discord(event)))
        if self.config.telegram_bot_token and self.config.telegram_chat_id:
            tasks.append(("telegram", self._send_telegram(event)))

        for platform, task in tasks:
            try:
                if await task:
                    sent_to.append(platform)
            except Exception as exc:
                logger.warning("Webhook %s failed: %s", platform, exc)

        return sent_to

    def _format_payload(self, event: dict) -> dict:
        """Build a rich alert payload from a SOAR-annotated event."""
        techniques = event.get("cloudsentinel_mitre_techniques", [])
        risk = event.get("cloudsentinel_risk_score", 0)
        action = event.get("cloudsentinel_soar_action", "none")
        country = event.get("country_name", "Unknown")
        city = event.get("city", "Unknown")

        emoji = "🔴" if risk >= 90 else "🟠" if risk >= 70 else "🟡"
        block_emoji = "🚫 BLOCKED" if action == "iptables_block" else "⚠️ DETECTED"

        return {
            "title": f"{emoji} CloudSentinel Alert - Risk {risk}/100",
            "ip": event.get("src_ip", "?"),
            "country": f"{city}, {country}",
            "event": event.get("eventid", "unknown"),
            "action": block_emoji,
            "techniques": ", ".join(techniques[:5]) if techniques else "none",
            "username": event.get("username", "?"),
            "password": event.get("password", ""),
            "hassh": (event.get("hassh_md5", "")[:16] + "...") if event.get("hassh_md5") else "N/A",
            "session": event.get("session", "?")[:12],
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "input": str(event.get("input", ""))[:200],
        }

    def _build_slack_blocks(self, p: dict, event: dict) -> list[dict]:
        fields1 = [
            {"type": "mrkdwn", "text": f"*IP:* `{p['ip']}`"},
            {"type": "mrkdwn", "text": f"*Location:* {p['country']}"},
            {"type": "mrkdwn", "text": f"*Status:* {p['action']}"},
            {"type": "mrkdwn", "text": f"*Risk:* {event.get('cloudsentinel_risk_score', 0)}/100"},
        ]
        fields2 = [
            {"type": "mrkdwn", "text": f"*User:* `{p['username']}`"},
            {"type": "mrkdwn", "text": f"*Password:* `{p['password']}`"},
            {"type": "mrkdwn", "text": f"*HASSH:* `{p['hassh']}`"},
            {"type": "mrkdwn", "text": f"*Session:* `{p['session']}`"},
        ]
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": p["title"], "emoji": True}},
            {"type": "section", "fields": fields1},
            {"type": "section", "fields": fields2},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*MITRE TTPs:* {p['techniques']}"}},
        ]
        if p["input"]:
            cmd_text = p["input"][:500].replace("`", "'")
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"```{cmd_text}```"},
            })
        return blocks

    async def _send_slack(self, event: dict) -> bool:
        p = self._format_payload(event)
        blocks = self._build_slack_blocks(p, event)
        resp = await self._client.post(self.config.slack_url, json={"blocks": blocks})
        return 200 <= resp.status_code < 300

    async def _send_discord(self, event: dict) -> bool:
        p = self._format_payload(event)
        risk = event.get("cloudsentinel_risk_score", 0)
        color = 0xFF0000 if risk >= 90 else 0xFFA500 if risk >= 70 else 0xFFD700
        embed = {
            "title": p["title"],
            "color": color,
            "fields": [
                {"name": "IP Address", "value": f"`{p['ip']}`", "inline": True},
                {"name": "Location", "value": p["country"], "inline": True},
                {"name": "Status", "value": p["action"], "inline": True},
                {"name": "Username", "value": f"`{p['username']}`", "inline": True},
                {"name": "Password", "value": f"`{p['password']}`", "inline": True},
                {"name": "Risk Score", "value": f"{risk}/100", "inline": True},
                {"name": "HASSH", "value": f"`{p['hassh']}`", "inline": True},
                {"name": "MITRE TTPs", "value": p["techniques"], "inline": False},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": f"CloudSentinel - Session {p['session']}"},
        }
        if p["input"]:
            embed["fields"].append({
                "name": "Command",
                "value": f"```{p['input'][:500]}```",
                "inline": False,
            })
        resp = await self._client.post(self.config.discord_url, json={"embeds": [embed]})
        return 200 <= resp.status_code < 300

    async def _send_telegram(self, event: dict) -> bool:
        p = self._format_payload(event)
        lines = [
            p["title"],
            "",
            f"IP: `{p['ip']}` | {p['country']}",
            f"Status: {p['action']}",
            f"User: `{p['username']}` | Pass: `{p['password']}`",
            f"HASSH: `{p['hassh']}`",
            f"MITRE: {p['techniques']}",
            f"Time: {p['timestamp']}",
        ]
        if p["input"]:
            lines.append("")
            lines.append(f"Command: `{p['input'][:500]}`")
        text = "\n".join(lines)

        url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        resp = await self._client.post(url, json={
            "chat_id": self.config.telegram_chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        })
        return 200 <= resp.status_code < 300


_notifier: WebhookNotifier | None = None


def get_notifier() -> WebhookNotifier:
    global _notifier
    if _notifier is None:
        _notifier = WebhookNotifier()
    return _notifier
