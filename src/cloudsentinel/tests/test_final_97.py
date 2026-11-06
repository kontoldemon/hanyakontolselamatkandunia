"""Final admin/server branches to clear 97%."""

from __future__ import annotations

import asyncio
import sys

import cloudsentinel.admin_api as admin_module
from cloudsentinel.attack_graph import AttackGraph
from cloudsentinel.config import load_settings
from cloudsentinel.hassh import HASSHDNA
from cloudsentinel.server import (
    CloudSentinelSSHServer,
    CloudSentinelSession,
    ConnectionLimiter,
)


def test_run_command_success() -> None:
    code, stdout, _stderr = asyncio.run(
        admin_module._run_command(
            [sys.executable, "-c", "print('unit')"],
            timeout=10.0,
        )
    )
    assert code == 0
    assert "unit" in stdout


def test_attack_graph_existing_target_edge() -> None:
    graph = AttackGraph()
    graph.add_event(
        {
            "src_ip": "1.1.1.1",
            "session": "s1",
            "eventid": "cloudsentinel.command.input",
            "input": "ssh root@2.2.2.2",
        }
    )
    graph.add_event(
        {
            "src_ip": "1.1.1.1",
            "session": "s2",
            "eventid": "cloudsentinel.command.input",
            "input": "ssh root@2.2.2.2",
            "cloudsentinel_mitre_techniques": ["T1021"],
        }
    )
    assert graph.get_subgraph("1.1.1.1")["edges"]


def test_host_key_chmod_failure(monkeypatch, tmp_path) -> None:
    import cloudsentinel.server as server_module

    class Key:
        def export_private_key(self) -> str:
            return "private"

    monkeypatch.setattr(server_module.asyncssh, "generate_private_key", lambda _kind: Key())
    monkeypatch.setattr("pathlib.Path.chmod", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("chmod")))
    assert server_module._load_or_create_host_key_sync(tmp_path / "host.key")


def test_session_resolution_and_write_failure() -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    server = CloudSentinelSSHServer(
        settings,
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        HASSHDNA(),
        ConnectionLimiter(max_total=1),
    )
    session = CloudSentinelSession(server)
    assert session._resolve_command("id") is not None

    class BrokenChannel:
        def write(self, _data: object) -> None:
            raise OSError("closed")

    session.chan = BrokenChannel()  # type: ignore[assignment]
    session._write("ignored")
