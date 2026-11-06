"""Final observability import fallback and VFS LLM error branch."""

from __future__ import annotations

import asyncio
import builtins
import sys
from pathlib import Path

import pytest

import cloudsentinel.observability as observability
import cloudsentinel.vfs_agent as vfs_agent_module
from cloudsentinel.config import LLMSettings
from cloudsentinel.vfs_agent import VFSContext, VFSAgent


def test_observability_orjson_fallback(monkeypatch) -> None:
    path = Path(observability.__file__)
    source = path.read_text(encoding="utf-8")
    code = compile(source, str(path), "exec")
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "orjson" or name.startswith("orjson."):
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    namespace = {
        "__name__": "cloudsentinel.observability_fallback",
        "__package__": "cloudsentinel",
        "__file__": str(path),
    }
    monkeypatch.setattr(builtins, "__import__", fake_import)
    exec(code, namespace)
    monkeypatch.undo()
    assert namespace["setup_structlog"]() is not None


@pytest.mark.asyncio
async def test_vfs_llm_failure(monkeypatch) -> None:
    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(vfs_agent_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(vfs_agent_module.random, "uniform", lambda *_args: 0.0)
    monkeypatch.setattr(vfs_agent_module, "_reserve_global_llm_call", lambda _limit: True)

    async def fail(_prompt: str) -> str:
        raise RuntimeError("llm failed")

    agent = VFSAgent(
        LLMSettings(provider="litellm", api_key="key"),
        VFSContext("unit-host", "Ubuntu"),
    )
    try:
        monkeypatch.setattr(agent, "_call_litellm", fail)
        output, mode = await agent.run_command_with_mode("id")
        assert mode == "deterministic"
        assert output
    finally:
        await agent.close()
