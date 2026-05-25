"""
CloudSentinel MITRE ATT&CK - Real-time TTP mapping engine.
MITRE ATT&CK v18 Enterprise Matrix.
"""

from __future__ import annotations

import re
from typing import ClassVar

MITRE_TECHNIQUES: dict[str, dict[str, str | int]] = {
    "T1059.004": {"name": "Command and Scripting Interpreter: Unix Shell", "tactic": "Execution", "severity": "high"},
    "T1105": {"name": "Ingress Tool Transfer", "tactic": "Command and Control", "severity": "high"},
    "T1082": {"name": "System Information Discovery", "tactic": "Discovery", "severity": "low"},
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
    (re.compile(r"\b(?:gpg|openssl)\b.*\b(?:-c|enc)\b"), 25, "T1486"),
    (re.compile(r"\bcat\s+(?:~|/root)/(?:\.aws/credentials|\.docker/config\.json|\.ssh/id_rsa)\b"), 25, "T1555"),
    (re.compile(r"\b(?:nc|ncat|socat)\b.*\b(?:-l|-p|listen)\b.*\b[0-9]{4,5}\b"), 10, "T1571"),
]


def deobfuscate_bash(command: str) -> str:
    """Remove basic bash obfuscation to improve regex matching."""
    # Remove quotes
    cmd = command.replace("'", "").replace('"', "")
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
