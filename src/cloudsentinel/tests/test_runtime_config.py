"""Runtime settings persistence and live wiring tests."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest
from cloudsentinel.admin_api import create_admin_app
from cloudsentinel.config import Settings, secret_to_str
from cloudsentinel.hassh import hassh_action_applies
from cloudsentinel.pipeline import EventPipeline
from cloudsentinel.runtime_config import RuntimeConfigStore
from cloudsentinel.soar import SOAREngine
from cloudsentinel.vfs import VirtualFileSystem
from fastapi.testclient import TestClient
from pydantic import SecretStr


def _soar(**kwargs) -> SOAREngine:
    defaults = {
        "risk_threshold": 70,
        "firewall_enabled": True,
        "firewall_dry_run": True,
        "allowlist": ["127.0.0.1"],
    }
    defaults.update(kwargs)
    return SOAREngine(**defaults)


def test_runtime_config_persists_and_applies(tmp_path: Path) -> None:
    settings = Settings()
    soar = _soar()
    path = tmp_path / "runtime.json"
    store = RuntimeConfigStore(settings, path=str(path), soar=soar)

    initial = store.snapshot()
    assert initial["deception"]["level"] == "full"
    assert initial["soar"]["trigger"] == "risk"
    assert initial["soar"]["risk_threshold"] == 70
    assert initial["soar"]["execution"] == "host"
    assert initial["llm"]["provider"] == settings.llm.provider

    updated = store.update(
        {
            "deception": {"level": "listener", "seed_canary_keys": False},
            "hassh": {"action": "drop", "threshold": 90},
            "soar": {"trigger": "mitre", "risk_threshold": 55, "execution": "eventgrid"},
            "llm": {
                "provider": "gemini",
                "model": "gemini/gemini-2.5-flash",
                "fallback_models": ["groq/llama-3.3-70b-versatile"],
                "hourly_limit": 50,
                "prompt_sanitization": False,
                "deception_mode": "deterministic",
            },
        }
    )
    assert updated["deception"]["level"] == "listener"
    assert settings.deception.level == "listener"
    assert settings.deception.seed_canary_keys is False
    assert settings.deception.hassh_action == "drop"
    assert settings.deception.hassh_threshold == 90
    assert soar.trigger == "mitre"
    assert soar.risk_threshold == 55
    assert soar.eventgrid_enabled is True
    assert settings.llm.provider == "gemini"
    assert settings.llm.model == "gemini/gemini-2.5-flash"
    assert settings.llm.fallback_models == ["groq/llama-3.3-70b-versatile"]
    assert settings.llm.global_hourly_limit == 50
    assert settings.llm.prompt_sanitization is False
    assert settings.llm.deception_mode == "deterministic"

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["soar"]["trigger"] == "mitre"
    assert "api_key" not in json.dumps(payload)

    reloaded_settings = Settings()
    reloaded_soar = _soar()
    reloaded = RuntimeConfigStore(reloaded_settings, path=str(path), soar=reloaded_soar)
    assert reloaded.snapshot()["deception"]["level"] == "listener"
    assert reloaded_settings.llm.model == "gemini/gemini-2.5-flash"
    assert reloaded_soar.trigger == "mitre"


def test_runtime_config_persists_api_key_and_restricts_file(tmp_path: Path) -> None:
    settings = Settings()
    path = tmp_path / "runtime.json"
    store = RuntimeConfigStore(settings, path=str(path))

    store.update({"llm": {"api_key": "sk-secret"}})

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["llm"]["api_key"] == "sk-secret"
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    reloaded = RuntimeConfigStore(Settings(), path=str(path))
    assert secret_to_str(reloaded.settings.llm.api_key) == "sk-secret"


def test_runtime_config_save_survives_chmod_error(tmp_path: Path, monkeypatch) -> None:
    def fail_chmod(*args, **kwargs) -> None:
        raise OSError("chmod not supported")

    monkeypatch.setattr("cloudsentinel.runtime_config.os.chmod", fail_chmod)
    path = tmp_path / "runtime.json"
    store = RuntimeConfigStore(Settings(), path=str(path))
    store.update({"llm": {"api_key": "sk-chmod"}})
    assert json.loads(path.read_text(encoding="utf-8"))["llm"]["api_key"] == "sk-chmod"


def test_runtime_config_rejects_unknown_values(tmp_path: Path) -> None:
    store = RuntimeConfigStore(Settings(), path=str(tmp_path / "runtime.json"))
    with pytest.raises(ValueError, match="deception.level"):
        store.update({"deception": {"level": "off"}})
    with pytest.raises(ValueError, match="hassh.threshold"):
        store.update({"hassh": {"threshold": 101}})
    with pytest.raises(ValueError, match="soar.trigger"):
        store.update({"soar": {"trigger": "sometimes"}})
    with pytest.raises(ValueError, match="llm.provider"):
        store.update({"llm": {"provider": "bogus"}})
    with pytest.raises(ValueError, match="unknown config section"):
        store.update({"unknown_section": {}})


def test_runtime_config_and_llm_endpoints(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_RUNTIME_CONFIG_PATH", str(tmp_path / "runtime.json"))
    settings = Settings()
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    settings.stream.enabled = False
    app = create_admin_app(settings, EventPipeline(settings.redis))
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-token"}

    assert client.get("/runtime-config").status_code == 401
    response = client.get("/runtime-config", headers=headers)
    assert response.status_code == 200
    assert response.json()["config"]["deception"]["level"] == "full"

    saved = client.post(
        "/runtime-config",
        headers=headers,
        json={"soar": {"trigger": "auth_spike", "risk_threshold": 40}},
    )
    assert saved.status_code == 200
    assert saved.json()["config"]["soar"]["trigger"] == "auth_spike"

    llm = client.post(
        "/llm/config",
        headers=headers,
        json={"api_key": "sk-test-key", "provider": "gemini", "model": "gemini/test"},
    )
    assert llm.status_code == 200
    assert llm.json()["has_api_key"] is True

    fetched = client.get("/llm/config", headers=headers)
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["model"] == "gemini/test"
    assert body["has_api_key"] is True
    assert body["api_key"] == "sk-test-key"  # admin-authenticated: prefills settings input

    rejected = client.post("/runtime-config", headers=headers, json={"deception": {"level": "off"}})
    assert rejected.status_code == 400
    assert system_settings_untouched(settings)

    bad_llm = client.post("/llm/config", headers=headers, json={"provider": "bogus"})
    assert bad_llm.status_code == 400


def system_settings_untouched(settings: Settings) -> bool:
    return settings.deception.level == "full"


def test_vfs_deception_levels_and_canary_toggle() -> None:
    full = VirtualFileSystem.for_deception("full", seed_canary_keys=True)
    assert full.exists("/root/.aws/credentials")
    assert full.exists("/var/www/html/config.php")

    no_canary = VirtualFileSystem.for_deception("full", seed_canary_keys=False)
    assert not no_canary.exists("/root/.aws/credentials")
    assert no_canary.exists("/etc/passwd")

    restricted = VirtualFileSystem.for_deception("restricted", seed_canary_keys=True)
    assert restricted.exists("/etc/passwd")
    assert not restricted.exists("/root/.aws/credentials")
    assert not restricted.exists("/var/www/html/config.php")

    listener = VirtualFileSystem.for_deception("listener", seed_canary_keys=True)
    assert listener.exists("/etc/passwd")
    assert not listener.exists("/root/.bash_history")
    assert not listener.exists("/root/.aws/credentials")


async def test_soar_mitre_trigger_blocks_without_risk_score() -> None:
    soar = _soar(trigger="mitre", risk_threshold=1000)
    blocked = await soar.process_event(
        "s-mitre",
        {
            "eventid": "cloudsentinel.command.input",
            "src_ip": "185.220.101.42",
            "input": "",
            "cloudsentinel_mitre_techniques": ["T1059", "T1082"],
        },
    )
    assert blocked["cloudsentinel_soar_action"] == "dry_run_block"

    single = await soar.process_event(
        "s-single",
        {
            "eventid": "cloudsentinel.command.input",
            "src_ip": "185.220.101.43",
            "input": "",
            "cloudsentinel_mitre_techniques": ["T1059"],
        },
    )
    assert single["cloudsentinel_soar_action"] == "none"


async def test_soar_auth_spike_trigger_blocks_on_repeated_failures() -> None:
    soar = _soar(trigger="auth_spike", risk_threshold=1000)
    actions = []
    for _ in range(10):
        event = await soar.process_event(
            "s-spike",
            {
                "eventid": "cloudsentinel.login.failed",
                "src_ip": "185.220.101.44",
                "input": "",
            },
        )
        actions.append(event["cloudsentinel_soar_action"])
    assert actions[:-1] == ["none"] * 9
    assert actions[-1] == "dry_run_block"


async def test_soar_any_input_trigger_blocks_first_command() -> None:
    soar = _soar(trigger="any_input", risk_threshold=1000)
    blocked = await soar.process_event(
        "s-any",
        {
            "eventid": "cloudsentinel.command.input",
            "src_ip": "185.220.101.45",
            "input": "id",
        },
    )
    assert blocked["cloudsentinel_soar_action"] == "dry_run_block"

    failed = await soar.process_event(
        "s-any-2",
        {
            "eventid": "cloudsentinel.login.failed",
            "src_ip": "185.220.101.46",
            "input": "",
        },
    )
    assert failed["cloudsentinel_soar_action"] == "none"


def test_hassh_action_threshold_mapping() -> None:
    critical = {"threat_level": "critical"}
    high = {"threat_level": "high"}
    assert hassh_action_applies("drop", 85, critical) is True
    assert hassh_action_applies("drop", 85, high) is False
    assert hassh_action_applies("drop", 80, high) is True
    assert hassh_action_applies("monitor", 0, critical) is False
    assert hassh_action_applies("drop", 0, {"threat_level": "unknown"}) is False

class _FakeAnomaly:
    stats = {
        "total_commands_analyzed": 42,
        "model_ready": True,
        "window_size": 100,
        "recent_count": 17,
    }


def test_anomaly_stats_reports_detector_metrics(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_RUNTIME_CONFIG_PATH", str(tmp_path / "runtime.json"))
    settings = Settings()
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    settings.stream.enabled = False
    client = TestClient(create_admin_app(settings, EventPipeline(settings.redis), anomaly=_FakeAnomaly()))
    headers = {"Authorization": "Bearer test-token"}

    response = client.get("/anomaly-stats", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["total_commands_analyzed"] == 42
    assert body["model_ready"] is True


def test_decoys_endpoint_reflects_deception_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_RUNTIME_CONFIG_PATH", str(tmp_path / "runtime.json"))
    settings = Settings()
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    settings.stream.enabled = False
    client = TestClient(create_admin_app(settings, EventPipeline(settings.redis)))
    headers = {"Authorization": "Bearer test-token"}

    armed = client.get("/decoys", headers=headers)
    assert armed.status_code == 200
    paths = {item["path"] for item in armed.json()["decoys"]}
    assert "/root/.aws/credentials" in paths
    assert armed.json()["count"] == len(paths)

    client.post("/runtime-config", headers=headers, json={"deception": {"seed_canary_keys": False}})
    disarmed = client.get("/decoys", headers=headers)
    paths = {item["path"] for item in disarmed.json()["decoys"]}
    assert "/root/.aws/credentials" not in paths


def test_readiness_reports_live_sensor_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_RUNTIME_CONFIG_PATH", str(tmp_path / "runtime.json"))
    settings = Settings()
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    settings.stream.enabled = False
    client = TestClient(create_admin_app(settings, EventPipeline(settings.redis)))
    headers = {"Authorization": "Bearer test-token"}

    body = client.get("/readiness", headers=headers).json()
    assert body["ssh_port"] == settings.honeypot.ssh_port
    assert body["deception_level"] == settings.deception.level
    assert body["deception_mode"] == settings.llm.deception_mode


def test_runtime_config_handles_bad_files_and_invalid_types(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    assert RuntimeConfigStore(Settings(), path=str(bad)).snapshot()["deception"]["level"] == "full"

    not_object = tmp_path / "list.json"
    not_object.write_text("[]", encoding="utf-8")
    assert RuntimeConfigStore(Settings(), path=str(not_object)).snapshot()["soar"]["trigger"] == "risk"

    store = RuntimeConfigStore(Settings(), path=str(tmp_path / "ok.json"))
    with pytest.raises(ValueError, match="payload must be an object"):
        store.update([])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must be an object"):
        store.update({"soar": "x"})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match="seed_canary_keys must be a boolean"):
        store.update({"deception": {"seed_canary_keys": "yes"}})
    with pytest.raises(ValueError, match="risk_threshold must be an integer"):
        store.update({"soar": {"risk_threshold": "70"}})
    with pytest.raises(ValueError, match="model must not be empty"):
        store.update({"llm": {"model": "  "}})
    with pytest.raises(ValueError, match="fallback_models must be a list"):
        store.update({"llm": {"fallback_models": "a,b"}})
    with pytest.raises(ValueError, match="unknown llm key"):
        store.update({"llm": {"nope": 1}})


async def test_ssh_hassh_drop_action(monkeypatch) -> None:
    from cloudsentinel.hassh import HASSHDNA
    from cloudsentinel.sensor import ssh as ssh_module
    from cloudsentinel.sensor.ssh import CloudSentinelSSHServer

    settings = Settings()
    settings.fingerprinting.enable_hassh = True
    settings.fingerprinting.enable_ja4s = False
    settings.deception.hassh_action = "drop"
    settings.deception.hassh_threshold = 85

    class Conn:
        closed = False

        def close(self) -> None:
            self.closed = True

        def get_extra_info(self, _name: str, default: object = None) -> object:
            return default

    class Limiter:
        total = 0
        max_total = 100

    server = CloudSentinelSSHServer(
        settings,
        pipeline=None,  # type: ignore[arg-type]
        soar=None,  # type: ignore[arg-type]
        hassh_dna=HASSHDNA(),
        limiter=Limiter(),  # type: ignore[arg-type]
    )
    server.conn = Conn()  # type: ignore[assignment]
    server.src_ip = "1.2.3.4"
    server._accepted = True

    async def no_emit(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(server, "_emit_event", no_emit)
    monkeypatch.setattr(
        ssh_module,
        "extract_hassh",
        lambda _conn: ("8ba2faa57b1f0332fa12cc96bdf3e1be", "kex"),
    )

    assert server.begin_auth("root") is False
    assert server.conn.closed is True


async def test_ssh_hassh_monitor_keeps_connection(monkeypatch) -> None:
    from cloudsentinel.hassh import HASSHDNA
    from cloudsentinel.sensor import ssh as ssh_module
    from cloudsentinel.sensor.ssh import CloudSentinelSSHServer

    settings = Settings()
    settings.fingerprinting.enable_hassh = True
    settings.fingerprinting.enable_ja4s = False
    settings.deception.hassh_action = "monitor"

    class Conn:
        closed = False

        def close(self) -> None:
            self.closed = True

        def get_extra_info(self, _name: str, default: object = None) -> object:
            return default

    class Limiter:
        total = 0
        max_total = 100

    server = CloudSentinelSSHServer(
        settings,
        pipeline=None,  # type: ignore[arg-type]
        soar=None,  # type: ignore[arg-type]
        hassh_dna=HASSHDNA(),
        limiter=Limiter(),  # type: ignore[arg-type]
    )
    server.conn = Conn()  # type: ignore[assignment]
    server.src_ip = "5.6.7.8"
    server._accepted = True
    monkeypatch.setattr(
        ssh_module,
        "extract_hassh",
        lambda _conn: ("8ba2faa57b1f0332fa12cc96bdf3e1be", "kex"),
    )

    assert server.begin_auth("root") is True
    assert server.conn.closed is False


async def test_vfs_routes_non_openai_providers_through_litellm(monkeypatch) -> None:
    import cloudsentinel.vfs_agent as vfs_module

    calls: list[str] = []

    def make_agent(provider: str):
        settings = vfs_module.LLMSettings()
        settings.provider = provider
        settings.model = f"{provider}/test-model"
        settings.api_key = __import__("pydantic").SecretStr("test-key")
        agent = vfs_module.VFSAgent(settings, vfs_module.VFSContext(hostname="test-host", os_version="Ubuntu 22.04"))
        return agent

    async def fake_litellm(_self, _prompt):
        calls.append("litellm")
        return "ok\n"

    async def fail_openai(_self, _prompt):
        calls.append("openai")
        raise AssertionError("openai-compatible path must not be used")

    monkeypatch.setattr(vfs_module.VFSAgent, "_call_litellm", fake_litellm)
    monkeypatch.setattr(vfs_module.VFSAgent, "_call_openai_compatible", fail_openai)

    for provider in ("groq", "anthropic"):
        agent = make_agent(provider)
        output, mode = await agent.run_command_with_mode("uptime")
        await agent.close()
        assert output == "ok"
        assert mode == "llm"

    assert calls == ["litellm", "litellm"]


async def test_litellm_fallbacks_use_their_own_credentials(monkeypatch) -> None:
    import sys
    import types

    import cloudsentinel.vfs_agent as vfs_module

    captured: dict = {}

    class FakeResponse:
        class Choice:
            class Message:
                content = "done"

            message = Message()

        choices = [Choice()]

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return FakeResponse()

    module = types.ModuleType("litellm")
    module.acompletion = fake_acompletion
    monkeypatch.setitem(sys.modules, "litellm", module)

    settings = vfs_module.LLMSettings()
    settings.model = "gemini/primary"
    settings.fallback_models = ["groq/fallback"]
    settings.api_key = __import__("pydantic").SecretStr("primary-key")
    agent = vfs_module.VFSAgent(settings, vfs_module.VFSContext(hostname="test-host", os_version="Ubuntu 22.04"))
    try:
        assert await agent._call_litellm("prompt") == "done"
    finally:
        await agent.close()

    assert captured["api_key"] == "primary-key"
    assert "api_key" not in captured["fallbacks"][0]


def test_admin_docs_are_opt_in(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_RUNTIME_CONFIG_PATH", str(tmp_path / "runtime.json"))
    monkeypatch.delenv("CLOUDSENTINEL_ENABLE_DOCS", raising=False)
    settings = Settings()
    settings.admin.enabled = True
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    settings.stream.enabled = False
    closed = TestClient(create_admin_app(settings, EventPipeline(settings.redis)))
    assert closed.get("/docs").status_code == 404
    assert closed.get("/openapi.json").status_code == 404

    monkeypatch.setenv("CLOUDSENTINEL_ENABLE_DOCS", "1")
    opened = TestClient(create_admin_app(settings, EventPipeline(settings.redis)))
    assert opened.get("/docs").status_code == 200
    assert opened.get("/openapi.json").status_code == 200


def test_runtime_config_ignores_invalid_persisted_values(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(
        '{"soar": {"trigger": "bogus", "risk_threshold": 55}, "llm": {"provider": "bogus"}}',
        encoding="utf-8",
    )
    settings = Settings()
    store = RuntimeConfigStore(settings, path=str(path))
    snapshot = store.snapshot()
    assert snapshot["soar"]["trigger"] == "risk"
    assert snapshot["soar"]["risk_threshold"] == 70
    assert snapshot["llm"]["provider"] == "litellm"


def test_known_botnet_variants_are_top_level_hassh_entries() -> None:
    from cloudsentinel.hassh import HASSHDNA

    dna = HASSHDNA()
    for hassh, family in (
        ("98d6137982cb17ddabecfff564aa0dd9", "Mirai"),
        ("c0af774d6b5fab3468ac2a34f3e763d8", "Gafgyt"),
        ("35ded6dbd38f6b576e39ac0ca0380155", "Scanner"),
    ):
        intel = dna.lookup(hassh)
        assert intel["botnet_family"] == family, hassh
        assert intel["threat_level"] != "unknown", hassh
        assert intel["client_software"] != "unknown", hassh


def test_hassh_known_table_has_no_duplicate_or_nested_entries() -> None:
    import ast
    from collections import Counter
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "hassh.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    checked = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict) or len(node.keys) < 20:
            continue
        checked = True
        keys = [key.value for key in node.keys if isinstance(key, ast.Constant)]
        duplicates = [key for key, count in Counter(keys).items() if count > 1]
        assert duplicates == [], duplicates
        assert all(isinstance(value, ast.Dict) for value in node.values)
    assert checked
