"""
CloudSentinel Sigma Rule Engine — log-based detection rule matching.

Sigma is an open, community-driven signature format for SIEM systems.
This module matches CloudSentinel events against Sigma rules to detect
known attacker TTPs that regex-based MITRE mapping might miss.

All rules are pure Python with zero external dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger("cloudsentinel.sigma")

# ── Built-in Sigma-style rules ────────────────────────────────────────

BUILTIN_RULES: list[dict[str, Any]] = [
    {
        "id": "cs-sigma-001",
        "title": "Crypto Miner Execution Detected",
        "description": "Detects cryptocurrency miner execution via xmrig, cpuminer, or stratum references",
        "level": "high",
        "tags": ["attack.t1496", "attack.impact"],
        "detection": {
            "keywords": ["xmrig", "cpuminer", "minerd", "stratum", "cryptonight", "randomx"],
            "command_regex": r"\b(xmrig|cpuminer|minerd)\b",
            "min_risk_score": 60,
        },
    },
    {
        "id": "cs-sigma-002",
        "title": "SSH Lateral Movement Attempt",
        "description": "Detects SSH connection attempts to internal IPs from the honeypot",
        "level": "medium",
        "tags": ["attack.t1021.004", "attack.lateral_movement"],
        "detection": {
            "keywords": ["ssh ", "scp ", "sftp "],
            "command_regex": r"\bssh\b.*\b(root@|admin@|10\.|172\.|192\.168\.)\b",
            "min_risk_score": 40,
        },
    },
    {
        "id": "cs-sigma-003",
        "title": "Firewall Disable Attempt",
        "description": "Detects attempts to disable firewall (iptables flush, ufw disable, setenforce 0)",
        "level": "high",
        "tags": ["attack.t1562", "attack.defense_evasion"],
        "detection": {
            "keywords": ["iptables -F", "ufw disable", "setenforce 0", "systemctl stop firewalld"],
            "command_regex": r"\b(iptables\s+-F|ufw\s+disable|setenforce\s+0|systemctl\s+stop\s+firewalld)\b",
            "min_risk_score": 50,
        },
    },
    {
        "id": "cs-sigma-004",
        "title": "Credential File Access",
        "description": "Detects attempts to read credential files (/etc/shadow, .aws/credentials, id_rsa)",
        "level": "critical",
        "tags": ["attack.t1003", "attack.t1555", "attack.credential_access"],
        "detection": {
            "keywords": ["/etc/shadow", ".aws/credentials", "id_rsa", ".docker/config.json", ".ssh/"],
            "command_regex": r"\bcat\s+.*(?:/etc/shadow|\.aws/credentials|id_rsa|\.docker/config\.json)\b",
            "min_risk_score": 70,
        },
    },
    {
        "id": "cs-sigma-005",
        "title": "Reverse Shell Indicator",
        "description": "Detects reverse shell commands (nc listener, /dev/tcp, python socket)",
        "level": "critical",
        "tags": ["attack.t1059", "attack.execution"],
        "detection": {
            "keywords": ["/dev/tcp/", "nc -l", "ncat -l", "socket", "connect(", "os.dup2"],
            "command_regex": r"\b(/dev/tcp/|nc\s+-[le]|python.*socket|perl.*socket|bash\s+-i\s*>&)\b",
            "min_risk_score": 65,
        },
    },
    {
        "id": "cs-sigma-006",
        "title": "Web Shell Deployment",
        "description": "Detects attempts to write PHP/ASP/JSP web shells to web directories",
        "level": "critical",
        "tags": ["attack.t1505.003", "attack.persistence"],
        "detection": {
            "keywords": [".php", ".asp", ".jsp", ".aspx", "shell", "cmd", "exec", "system("],
            "command_regex": r"\becho\b.*\b(\.php|\.asp|\.jsp|\.aspx|system\s*\(|exec\s*\()\b",
            "min_risk_score": 60,
        },
    },
    {
        "id": "cs-sigma-007",
        "title": "Data Exfiltration via curl/wget POST",
        "description": "Detects data exfiltration using curl or wget with POST method",
        "level": "high",
        "tags": ["attack.t1048", "attack.exfiltration"],
        "detection": {
            "keywords": ["curl -X POST", "curl --data", "wget --post-data", "curl -F"],
            "command_regex": r"\b(curl|wget)\b.*\b(--data|--post-data|-F|--upload-file)\b",
            "min_risk_score": 55,
        },
    },
    {
        "id": "cs-sigma-008",
        "title": "Persistence via Crontab",
        "description": "Detects crontab manipulation for persistence (crontab -e, echo to cron.d)",
        "level": "medium",
        "tags": ["attack.t1053.003", "attack.persistence"],
        "detection": {
            "keywords": ["crontab", "cron.d", "cron.hourly", "@reboot"],
            "command_regex": r"\b(crontab|echo.*cron\.d|echo.*cron\.hourly|@reboot)\b",
            "min_risk_score": 40,
        },
    },
]

# ── Sigma Rule Engine ─────────────────────────────────────────────────


class SigmaRuleEngine:
    """Match CloudSentinel events against Sigma rules.

    Supports built-in rules and custom rule files in Sigma YAML format.
    Zero external dependencies — pure Python regex matching.
    """

    def __init__(self, rules_dir: str | None = None) -> None:
        self._rules: list[dict[str, Any]] = list(BUILTIN_RULES)
        self._match_counts: dict[str, int] = {}
        if rules_dir:
            self._load_rules_from_dir(rules_dir)

    def _load_rules_from_dir(self, rules_dir: str) -> None:
        """Load Sigma YAML rules from a directory."""
        path = Path(rules_dir)
        if not path.is_dir():
            return
        import yaml
        for rule_file in sorted(path.glob("*.yml")):
            try:
                rule = yaml.safe_load(rule_file.read_text(encoding="utf-8"))
                if isinstance(rule, dict) and "id" in rule:
                    self._rules.append(rule)
                    logger.debug("Loaded Sigma rule: %s", rule.get("id", "unknown"))
            except Exception as exc:
                logger.warning("Failed to load Sigma rule %s: %s", rule_file, exc)

    def match_event(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        """Match a single event against all Sigma rules.

        Returns list of matched rules with metadata.
        """
        event_input = str(event.get("input", "")).lower()
        event_type = str(event.get("eventid", "")).lower()
        risk_score = int(event.get("cloudsentinel_risk_score", 0))

        matches: list[dict[str, Any]] = []
        for rule in self._rules:
            detection = rule.get("detection", {})
            keywords = detection.get("keywords", [])
            command_regex = detection.get("command_regex", "")
            min_risk = detection.get("min_risk_score", 0)

            # Check minimum risk threshold
            if risk_score < min_risk:
                continue

            # Keyword matching
            keyword_match = any(kw.lower() in event_input for kw in keywords)

            # Regex matching (only if keywords matched or no keywords)
            regex_match = False
            if command_regex:
                try:
                    regex_match = bool(re.search(command_regex, event_input))
                except re.error:
                    pass

            if keyword_match or regex_match:
                rule_id = str(rule.get("id", "unknown"))
                self._match_counts[rule_id] = self._match_counts.get(rule_id, 0) + 1
                matches.append({
                    "rule_id": rule_id,
                    "title": rule.get("title", ""),
                    "level": rule.get("level", "medium"),
                    "tags": rule.get("tags", []),
                    "keyword_match": keyword_match,
                    "regex_match": regex_match,
                })

        return matches

    def match_events(self, events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Match a batch of events. Returns {event_index: [matched_rules]}."""
        results: dict[str, list[dict[str, Any]]] = {}
        for i, event in enumerate(events):
            session_id = str(event.get("session", f"event_{i}"))
            matches = self.match_event(event)
            if matches:
                results[session_id] = matches
        return results

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_rules": len(self._rules),
            "match_counts": dict(self._match_counts),
            "top_rules": sorted(
                self._match_counts.items(), key=lambda x: x[1], reverse=True
            )[:5],
        }

    def export_rules(self) -> list[dict[str, Any]]:
        """Export all rules as Sigma-compatible JSON."""
        return [
            {
                "id": r.get("id"),
                "title": r.get("title"),
                "description": r.get("description"),
                "level": r.get("level"),
                "tags": r.get("tags"),
            }
            for r in self._rules
        ]
