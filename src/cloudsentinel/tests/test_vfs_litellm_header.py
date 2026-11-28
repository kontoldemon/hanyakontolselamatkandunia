import asyncio
import sys
import types

from cloudsentinel.vfs_agent import LLMSettings, VFSAgent, VFSContext


def _settings(**kwargs):
    defaults = {
        "provider": "litellm",
        "endpoint": "https://opencode.ai/inference/go/openai/v1",
        "model": "openai/deepseek-v4.1-flash",
        "api_key": "unit-key",
    }
    defaults.update(kwargs)
    return LLMSettings(**defaults)


def _install_fake_litellm(monkeypatch, fake_acompletion) -> None:
    module = types.ModuleType("litellm")
    module.acompletion = fake_acompletion
    monkeypatch.setitem(sys.modules, "litellm", module)


def _fake_acompletion(captured):
    async def fake(**kwargs):
        captured.update(kwargs)

        class Message:
            content = "ok"

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]

        return Response()

    return fake


def test_vfs_litellm_sends_opencode_session_header(monkeypatch) -> None:
    captured = {}
    _install_fake_litellm(monkeypatch, _fake_acompletion(captured))
    agent = VFSAgent(_settings(), VFSContext("h", "Ubuntu"))
    assert asyncio.run(agent._call_litellm("prompt")) == "ok"
    assert captured["api_base"] == "https://opencode.ai/inference/go/openai/v1"
    assert captured["api_key"] == "unit-key"
    assert captured["extra_headers"]["x-opencode-session"]
    assert captured["extra_body"]["reasoning_effort"] == "none"
    assert captured["max_tokens"] == 1600
    assert captured["timeout"] == 8.0


def test_vfs_litellm_omits_header_for_other_providers(monkeypatch) -> None:
    captured = {}
    _install_fake_litellm(monkeypatch, _fake_acompletion(captured))
    agent = VFSAgent(_settings(endpoint="https://api.deepseek.com"), VFSContext("h", "Ubuntu"))
    assert asyncio.run(agent._call_litellm("prompt")) == "ok"
    assert "extra_headers" not in captured
    assert "extra_body" not in captured


def test_vfs_openai_compatible_sends_opencode_session_header(monkeypatch) -> None:
    captured = {}

    async def fake_post(_self, url, **kwargs):
        captured["url"] = str(url)
        captured["headers"] = kwargs["headers"]
        captured["json"] = kwargs["json"]

        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"choices": [{"message": {"content": "ok"}}]}

        return Response()

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    agent = VFSAgent(_settings(provider="openai"), VFSContext("h", "Ubuntu"))
    assert asyncio.run(agent._call_openai_compatible("prompt")) == "ok"
    assert captured["headers"]["x-opencode-session"]
    assert captured["json"]["reasoning_effort"] == "none"
