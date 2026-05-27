"""
CloudSentinel MITRE ATT&CK - Real-time TTP mapping engine.
MITRE ATT&CK v18 Enterprise Matrix.
"""

from __future__ import annotations

import re
import unicodedata
from typing import ClassVar

# ── Unicode Homoglyph Defense ─────────────────────────────────────
# Maps visually-similar Unicode characters to ASCII equivalents.
# Prevents attackers from evading regex detection via Cyrillic/Greek homoglyphs.
# NFKC alone does NOT normalize these (they're semantically distinct code points).
HOMOGLYPH_MAP: dict[int, str] = {
    # Cyrillic lowercase → ASCII
    0x0430: "a", 0x0441: "c", 0x0435: "e", 0x043E: "o",
    0x043B: "l", 0x0440: "p", 0x0455: "s", 0x0445: "x", 0x0443: "y",
    # Cyrillic uppercase → ASCII
    0x0410: "A", 0x0412: "B", 0x0415: "E", 0x041A: "K",
    0x041C: "M", 0x041D: "H", 0x041E: "O", 0x0420: "P",
    0x0421: "C", 0x0422: "T", 0x0425: "X",
    # Greek uppercase → ASCII
    0x0391: "A", 0x0392: "B", 0x0395: "E", 0x0396: "Z",
    0x0397: "H", 0x0399: "I", 0x039A: "K", 0x039C: "M",
    0x039D: "N", 0x039F: "O", 0x03A1: "P", 0x03A4: "T",
    0x03A5: "Y", 0x03A7: "X",
    # Greek lowercase → ASCII
    0x03B1: "a", 0x03B5: "e", 0x03B7: "n",
    0x03B9: "i", 0x03BA: "k", 0x03BD: "v", 0x03BF: "o",
    0x03C1: "p", 0x03C4: "t", 0x03C5: "u", 0x03C7: "x",
    # Fullwidth Latin → ASCII
    0xFF41: "a", 0xFF43: "c", 0xFF45: "e", 0xFF4F: "o",
    0xFF50: "p", 0xFF53: "s", 0xFF58: "x", 0xFF59: "y",
    0xFF21: "A", 0xFF23: "C", 0xFF25: "E", 0xFF2F: "O",
    0xFF30: "P", 0xFF33: "S", 0xFF38: "X", 0xFF39: "Y",
}


def _normalize_homoglyphs(text: str) -> str:
    """Replace Unicode homoglyphs with ASCII equivalents."""
    return text.translate(HOMOGLYPH_MAP)


MITRE_TECHNIQUES: dict[str, dict[str, str | int]] = {
    "T1059.004": {"name": "Command and Scripting Interpreter: Unix Shell", "tactic": "Execution", "severity": "high"},
    "T1105": {"name": "Ingress Tool Transfer", "tactic": "Command and Control", "severity": "high"},
    "T1082": {"name": "System Information Discovery", "tactic": "Discovery", "severity": "low"},
    "T1083": {"name": "File and Directory Discovery", "tactic": "Discovery", "severity": "low"},
    "T1033": {"name": "System Owner/User Discovery", "tactic": "Discovery", "severity": "low"},
    "T1222": {"name": "File and Directory Permissions Modification", "tactic": "Defense Evasion", "severity": "medium"},
    "T1110": {"name": "Brute Force", "tactic": "Credential Access", "severity": "high"},
    "T1078": {"name": "Valid Accounts", "tactic": "Defense Evasion, Persistence, Privilege Escalation, Initial Access", "severity": "high"},
    "T1021.004": {"name": "Remote Services: SSH", "tactic": "Lateral Movement", "severity": "medium"},
    "T1003": {"name": "OS Credential Dumping", "tactic": "Credential Access", "severity": "high"},
    "T1562": {"name": "Impair Defenses", "tactic": "Defense Evasion", "severity": "medium"},
    "T1046": {"name": "Network Service Discovery", "tactic": "Discovery", "severity": "medium"},
    "T1505.003": {"name": "Server Software Component: Web Shell", "tactic": "Persistence", "severity": "high"},
    "T1059.001": {"name": "Command and Scripting Interpreter: PowerShell", "tactic": "Execution", "severity": "medium"},
    "T1059.003": {"name": "Command and Scripting Interpreter: Windows Command Shell", "tactic": "Execution", "severity": "medium"},
    "T1543.002": {"name": "Create or Modify System Process: Systemd Service", "tactic": "Persistence, Privilege Escalation", "severity": "high"},
    "T1496": {"name": "Resource Hijacking", "tactic": "Impact", "severity": "high"},
    "T1486": {"name": "Data Encrypted for Impact", "tactic": "Impact", "severity": "critical"},
    "T1555": {"name": "Credentials from Password Stores", "tactic": "Credential Access", "severity": "high"},
    "T1098": {"name": "Account Manipulation", "tactic": "Persistence, Privilege Escalation", "severity": "critical"},
    "T1090": {"name": "Proxy", "tactic": "Command and Control", "severity": "medium"},
    "T1571": {"name": "Non-Standard Port", "tactic": "Command and Control", "severity": "low"},
}

COMMAND_PATTERNS: ClassVar[list[tuple[re.Pattern, int, str]]] = [
    (re.compile(r"\b(?:wget|curl|tftp|ftpget)\b.*(?:http|ftp)://"), 25, "T1105"),
    (re.compile(r"\b(?:sh|bash|dash|zsh)\b\s+-c\b"), 20, "T1059.004"),
    (re.compile(r"\bpython[23]?\b\s+-c\b"), 15, "T1059.004"),
    (re.compile(r"\bperl\b\s+-[eE]\b"), 15, "T1059.004"),
    (re.compile(r"\bchmod\b\s+[0-7]{3,4}"), 20, "T1222"),
    (re.compile(r"\bchown\b"), 15, "T1222"),
    (re.compile(r"\b(?:uname|hostnamectl|lscpu|lshw)\b"), 10, "T1082"),
    (re.compile(r"\bcat\s+/etc/(?:os-release|issue|hostname)\b"), 10, "T1082"),
    (re.compile(r"\b(?:free|df|top|ps|lsblk)\b"), 8, "T1082"),
    (re.compile(r"\b(?:whoami|id|who|w)\b"), 10, "T1033"),
    (re.compile(r"\bcat\s+/etc/(?:passwd|shadow)\b"), 12, "T1033"),
    (re.compile(r"\b(?:netstat|ss|nmap)\b"), 15, "T1046"),
    (re.compile(r"\bcat\s+/etc/shadow\b"), 20, "T1003"),
    (re.compile(r"\b(?:mimikatz|pypykatz)\b"), 20, "T1003"),
    (re.compile(r"\b(?:iptables\s+-f|ufw\s+disable|systemctl\s+stop\s+firewalld)\b"), 25, "T1562"),
    (re.compile(r"\bsetenforce\s+0\b"), 15, "T1562"),
    (re.compile(r"\bssh\b.*\b(?:-p|-l|root@|admin@)\b"), 15, "T1021.004"),
    (re.compile(r"\bsystemctl\s+(?:enable|daemon-reload)\b"), 12, "T1543.002"),
    (re.compile(r"\b(?:xmrig|cpuminer|minerd)\b"), 30, "T1496"),
    (re.compile(r"\becho\b.*\b(?:\.php|\.asp|\.jsp|\.aspx)\b"), 15, "T1505.003"),
    (re.compile(r"\b(?:ngrok|frp|chisel|socat)\b"), 20, "T1090"),
    (re.compile(r"\bpowershell(?:\.exe)?\b"), 15, "T1059.001"),
    (re.compile(r"\b(?:cmd\.exe|cmd)\s+/c\b"), 15, "T1059.003"),
    (re.compile(r"\b(?:gpg|openssl)\b.*(?:-c\b|\benc\b)"), 25, "T1486"),
    (re.compile(r"\bcat\s+(?:~|/root)/(?:\.aws/credentials|\.docker/config\.json|\.ssh/id_rsa)\b"), 25, "T1555"),
    (re.compile(r"\b(?:nc|ncat|socat)\b.*(?:-l\b|-p\b|\blisten\b).*\b[0-9]{4,5}\b"), 10, "T1571"),
    (
        re.compile(
            r"(?:authorized_keys|\.ssh(?:/|$).*(?:rm\s+-rf|chattr|chmod|echo\s+['\"]?ssh-rsa|mkdir\s+\.ssh))"
        ),
        45,
        "T1098",
    ),
]


def deobfuscate_bash(command: str) -> str:
    """Remove basic bash obfuscation to improve regex matching."""
    # Normalize unicode homoglyphs (Cyrillic а → ASCII a, etc.)
    cmd = _normalize_homoglyphs(command)
    cmd = unicodedata.normalize("NFKC", cmd)
    # Remove quotes
    cmd = cmd.replace("'", "").replace('"', "")
    # Remove backslashes
    cmd = cmd.replace("\\", "")
    # Remove simple variable expansions (e.g. $x, $@, ${VAR})
    cmd = re.sub(r'\$[a-zA-Z0-9_@*#?]+', '', cmd)
    cmd = re.sub(r'\$\{[a-zA-Z0-9_@*#?]+\}', '', cmd)
    # Condense spaces
    cmd = re.sub(r'\s+', ' ', cmd)
    return cmd.strip()


def match_command(command: str) -> list[tuple[str, int, str]]:
    results: list[tuple[str, int, str]] = []
    seen: set[str] = set()
    
    normalized_command = deobfuscate_bash(command).lower()
    
    for pattern, score, tech_id in COMMAND_PATTERNS:
        if tech_id in seen:
            continue
        # Check both raw and normalized commands to be safe
        if pattern.search(command.lower()) or pattern.search(normalized_command):
            tech = MITRE_TECHNIQUES.get(tech_id, {})
            name = str(tech.get("name", tech_id))
            results.append((tech_id, score, name))
            seen.add(tech_id)
    return results


def score_command(command: str) -> dict[str, object]:
    """Return compact MITRE risk annotation for a shell command."""

    matches = match_command(command)
    techniques = [tech_id for tech_id, _score, _name in matches]
    score = sum(score for _tech_id, score, _name in matches)
    names = {tech_id: name for tech_id, _score, name in matches}
    return {
        "risk_score": min(score, 100),
        "mitre_techniques": techniques,
        "mitre_names": names,
    }


def get_technique_info(tech_id: str) -> dict[str, str | int]:
    return dict(MITRE_TECHNIQUES.get(tech_id, {}))


def score_auth_event(username: str, attempt_count: int, password: str = "") -> dict[str, object]:
    """Score authentication events for TTPs not detectable via command regex.

    Returns MITRE annotations for:
      - T1110 (Brute Force) — triggered by repeated auth attempts
      - T1078 (Valid Accounts) — triggered by common admin/root usernames
    """
    techniques: list[str] = []
    risk_score = 0
    names: dict[str, str] = {}

    # T1110: Brute Force — high attempt count signals credential stuffing
    if attempt_count >= 5:
        techniques.append("T1110")
        risk_score += min(attempt_count * 3, 30)
        names["T1110"] = str(MITRE_TECHNIQUES["T1110"]["name"])

    # T1078: Valid Accounts — common administrative usernames
    valid_account_usernames = {
        "root", "admin", "administrator", "ubuntu", "debian",
        "pi", "ec2-user", "centos", "git", "jenkins", "www-data",
        "postgres", "mysql", "oracle", "tomcat", "guest",
    }
    if username.lower() in valid_account_usernames:
        techniques.append("T1078")
        risk_score += 15
        names["T1078"] = str(MITRE_TECHNIQUES["T1078"]["name"])

    # Bonus: detect default/weak password attempts (T1110 signal)
    weak_passwords = {
        "root", "admin", "password", "123456", "12345678", "qwerty",
        "letmein", "changeme", "test", "user", "guest", "ubuntu",
        "admin123", "root123", "toor", "default", "",
    }
    if password.lower() in weak_passwords and attempt_count >= 2:
        if "T1110" not in techniques:
            techniques.append("T1110")
            names["T1110"] = str(MITRE_TECHNIQUES["T1110"]["name"])
        risk_score += 10

    return {
        "risk_score": min(risk_score, 100),
        "mitre_techniques": techniques,
        "mitre_names": names,
    }


def score_event(event_type: str, event_data: dict[str, object]) -> dict[str, object]:
    """Unified event scorer combining command and auth-based TTP mapping.

    Routes to score_command() for command_exec events and score_auth_event()
    for login events, returning a merged risk annotation.
    """
    if event_type in ("cloudsentinel.login.failed", "cloudsentinel.login.success"):
        username = str(event_data.get("username", ""))
        try:
            attempt = int(event_data.get("attempt", 1))
        except (ValueError, TypeError):
            attempt = 1
        password = str(event_data.get("password", ""))
        return score_auth_event(username, attempt, password)

    if event_type in ("cloudsentinel.command.exec", "cloudsentinel.command.input"):
        command = str(event_data.get("input", ""))
        return score_command(command)

    return {"risk_score": 0, "mitre_techniques": [], "mitre_names": {}}
