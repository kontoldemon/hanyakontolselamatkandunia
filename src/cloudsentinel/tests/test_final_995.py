"""Final small branches for AbuseIPDB, VFS Gemini, pipeline, and secrets."""

from __future__ import annotations

import asyncio
import sys
import types

try:
    import hishel  # noqa: F401
except ModuleNotFoundError:
    _hishel = types.ModuleType("hishel")
    _hishel.AsyncCacheClient = type("AsyncCacheClient", (), {})
    sys.modules["hishel"] = _hishel

try:
    import tenacity  # noqa: F401
except ModuleNotFoundError:
    _tenacity = types.ModuleType("tenacity")
    _tenacity.retry = lambda *_a, **_k: (lambda f: f)
    _tenacity.retry_if_exception_type = lambda *_a, **_k: None
    _tenacity.stop_after_attempt = lambda *_a, **_k: None
    _tenacity.wait_exponential = lambda *_a, **_k: None
    sys.modules["tenacity"] = _tenacity

import cloudsentinel.pipeline as pipeline_module
import cloudsentinel.vfs_agent as vfs_agent_module
from cloudsentinel.abuseipdb import AbuseIPDBClient
from cloudsentinel._secrets import InfisicalProvider
from cloudsentinel.config import LLMSettings
from cloudsentinel.pipeline import EventEnvelope
from cloudsentinel.vfs_agent import VFSContext, VFSAgent


def test_abuseipdb_without_client() -> None:
    client = AbuseIPDBClient(api_key="key")
    result = asyncio.run(client._fetch_report("8.8.8.8", 90))
    assert result["abuse_confidence_score"] == 0


def test_pipeline_command_output_reason() -> None:
    envelope = EventEnvelope(
        "cloudsentinel.command.output",
        "s",
        "8.8.8.8",
        22,
        1.0,
        {"eventid": "cloudsentinel.command.output", "output": "root\n"},
    )
    row = pipeline_module.ClickHouseForwarder.envelope_to_row(envelope)
    assert row["reason"] == "root\n"


def test_vfs_gemini_branch(monkeypatch) -> None:
    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(vfs_agent_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(vfs_agent_module.random, "uniform", lambda *_args: 0.0)
    monkeypatch.setattr(vfs_agent_module, "_reserve_global_llm_call", lambda _limit: True)
    agent = VFSAgent(
        LLMSettings(provider="gemini", api_key="key"),
        VFSContext("host", "Ubuntu"),
    )

    async def gemini(_prompt: str) -> str:
        return "gemini output"

    monkeypatch.setattr(agent, "_call_gemini", gemini)
    try:
        output, mode = asyncio.run(agent.run_command_with_mode("unknown"))
        assert output == "gemini output"
        assert mode == "llm"
    finally:
        asyncio.run(agent.close())


def test_infisical_non_200(monkeypatch) -> None:
    provider = InfisicalProvider()
    provider._available = True
    provider._token = "token"
    provider._last_fetch = 10**18

    class Response:
        status_code = 500

        def json(self) -> dict:
            return {}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, *_args, **_kwargs):
            return Response()

    fake = types.ModuleType("httpx")
    fake.AsyncClient = Client
    monkeypatch.setitem(sys.modules, "httpx", fake)
    assert asyncio.run(provider.get("UNIT_KEY", "fallback")) == "fallback"
