"""Cover VFS agent routing, cache, local state, and LLM transports."""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

import cloudsentinel.vfs_agent as vfs_agent_module
from cloudsentinel.config import LLMSettings
from cloudsentinel.vfs_agent import VFSContext, VFSAgent


def _agent(**overrides) -> VFSAgent:
    settings = LLMSettings(**overrides)
    return VFSAgent(settings, VFSContext("unit-host", "Ubuntu 22.04", cwd="~"))


@pytest.fixture(autouse=True)
def fast_agent(monkeypatch):
    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(vfs_agent_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(vfs_agent_module.random, "uniform", lambda *_args: 0.0)


@pytest.mark.asyncio
async def test_vfs_agent_mock_and_local_state() -> None:
    agent = _agent(provider="mock")
    try:
        assert await agent.run_command_with_mode("") == ("", "deterministic")
        assert (await agent.run_command_with_mode("cd /tmp"))[1] == "deterministic"
        assert agent.context.cwd == "/tmp"
        await agent.run_command_with_mode("cd ..")
        assert agent.context.cwd == "/"
        await agent.run_command_with_mode("cd /etc")
        assert agent.context.cwd == "/etc"
        await agent.run_command_with_mode("cd")
        assert agent.context.cwd == "~"
        await agent.run_command_with_mode("cd work")
        assert agent.context.cwd == "~/work"
        assert (await agent.run_command_with_mode("export A=1"))[0] == ""

        assert (await agent.run_command_with_mode("systemctl status"))[1] == "blocked"
        assert (await agent.run_command_with_mode("ps"))[1] == "templated"
        assert await agent.run_command("whoami") == "root\n"
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_vfs_agent_sandbox_cache_and_bounds() -> None:
    agent = _agent(provider="mock", response_template_max_lines=2)
    try:
        class FakeSandbox:
            async def execute(self, _command: str, _cwd: str) -> tuple[int, str]:
                return 0, "sandbox output\nline2\nline3"

        agent._sandbox = FakeSandbox()
        output, mode = await agent.run_command_with_mode("./payload")
        assert "sandbox output" in output
        assert mode == "templated"

        agent._set_cache("ls", "cached")
        assert await agent.run_command_with_mode("ls") == ("cached", "deterministic")
        agent._cache["ls"] = (0.0, "expired")
        assert agent._get_cache("ls") is None
        agent._max_cache_entries = 1
        agent._set_cache("one", "1")
        agent._set_cache("two", "2")
        assert "one" not in agent._cache

        assert agent._bounded("a\nb\nc") == "a\nb"
        assert agent._is_complex_or_binary("./x")
        assert agent._is_complex_or_binary("/tmp/x")
        assert agent._is_complex_or_binary("/dev/shm/x")
        assert agent._is_complex_or_binary("echo x | sh")
        assert agent._is_complex_or_binary("wget http://x")
        assert agent._is_complex_or_binary("curl http://x")
        assert agent._is_complex_or_binary("chmod +x x")
        assert not agent._is_complex_or_binary("ls")
        assert not agent._is_blocked_command("")
        assert agent._is_blocked_command("systemctl status")
        assert agent._is_templated_command("ps")
        assert agent._is_templated_command("free")
        assert agent._is_templated_command("df")
        assert agent._is_templated_command("netstat -an")
        assert agent._is_templated_command("ss -t")
        assert agent._is_templated_command("find /")
        assert agent._is_templated_command("history")
        assert agent._is_templated_command("env")
        assert not agent._is_templated_command("ls")
        assert agent._parse_args("echo 'a b'") == ["echo", "a b"]
        assert agent._parse_args("echo 'unterminated") == ["echo", "'unterminated"]
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_vfs_agent_mock_responses() -> None:
    agent = _agent(provider="mock")
    try:
        assert agent._mock_response("") == ""
        assert agent._mock_response("hostname") == "unit-host"
        assert agent._mock_response("whoami") == "root\n"
        assert agent._mock_response("pwd") == "/root"
        agent.context.cwd = "/etc"
        assert agent._mock_response("pwd") == "/etc"
        assert "uid=0" in agent._mock_response("id")
        assert agent._mock_response("uname").startswith("Linux")
        assert "passwd" in agent._mock_response("ls")
        assert "Mon May" in agent._mock_response("date")
        assert "load average" in agent._mock_response("uptime")
        assert "PID" in agent._mock_response("ps")
        assert "Mem:" in agent._mock_response("free")
        assert "Filesystem" in agent._mock_response("df")
        assert "root:x" in agent._mock_response("cat /etc/passwd")
        assert agent._mock_response("cat /missing").startswith("cat:")
        assert agent._mock_response("echo hello") == "hello\n"
        assert "command not found" in agent._mock_response("nope")
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_vfs_agent_llm_transports(monkeypatch) -> None:
    agent = _agent(provider="litellm", api_key="key", model="unit-model", endpoint="http://llm")
    try:
        fake_litellm = types.ModuleType("litellm")

        async def acompletion(**_kwargs: object) -> object:
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="llm out"))]
            )

        fake_litellm.acompletion = acompletion
        monkeypatch.setitem(sys.modules, "litellm", fake_litellm)
        assert await agent._call_litellm("prompt") == "llm out"

        class FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"choices": [{"message": {"content": "openai out"}}]}

        class FakeClient:
            async def post(self, *_args: object, **_kwargs: object) -> FakeResponse:
                return FakeResponse()

            async def aclose(self) -> None:
                return None

        agent._client = FakeClient()
        assert await agent._call_openai_compatible("prompt") == "openai out"

        class GeminiResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"candidates": [{"content": {"parts": [{"text": "gemini "}, {"text": "out"}]}}]}

        class GeminiClient:
            async def post(self, *_args: object, **_kwargs: object) -> GeminiResponse:
                return GeminiResponse()

            async def aclose(self) -> None:
                return None

        agent._client = GeminiClient()
        assert await agent._call_gemini("prompt") == "gemini out"
        assert agent._extract_gemini_text({}) == ""
        assert agent._extract_gemini_text({"candidates": []}) == ""

        assert await agent.run_command_with_mode("ls") == ("llm out", "llm")
        assert await agent.run_command_with_mode("ls") == ("llm out", "deterministic")
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_vfs_agent_budgets(monkeypatch) -> None:
    agent = _agent(provider="litellm", api_key="key", session_call_limit=1)
    try:
        async def fake_llm(_prompt: str) -> str:
            return "llm"

        monkeypatch.setattr(agent, "_call_litellm", fake_llm)
        assert (await agent.run_command_with_mode("id"))[0] == "llm"
        assert (await agent.run_command_with_mode("id"))[1] == "deterministic"
    finally:
        await agent.close()

    global_limited = _agent(provider="litellm", api_key="key", session_call_limit=0)
    try:
        monkeypatch.setattr(vfs_agent_module, "_reserve_global_llm_call", lambda _limit: False)
        assert (await global_limited.run_command_with_mode("id"))[1] == "deterministic"
    finally:
        await global_limited.close()

    failed = _agent(provider="litellm", api_key="key")
    try:
        async def broken(_prompt: str) -> str:
            raise RuntimeError("llm down")

        monkeypatch.setattr(failed, "_call_litellm", broken)
        assert (await failed.run_command_with_mode("id"))[1] == "deterministic"
    finally:
        await failed.close()
