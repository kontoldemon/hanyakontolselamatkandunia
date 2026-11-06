"""Final server helper branches and admin replay variants."""

from __future__ import annotations

import asyncio
import builtins
import sys
import types

import pytest

import cloudsentinel.server as server_module
from cloudsentinel.config import load_settings
from cloudsentinel.hassh import HASSHDNA
from cloudsentinel.server import CloudSentinelSSHServer, CloudSentinelSession, ConnectionLimiter, TTYLogger


class FakePipeline:
    async def emit(self, _envelope: object) -> None:
        return None


class FakeSoar:
    async def process_event(self, _session: str, event: dict) -> dict:
        return event


def _session() -> CloudSentinelSession:
    server = CloudSentinelSSHServer(
        load_settings("src/cloudsentinel/configs/usas-production.yaml", "src/cloudsentinel/.env"),
        FakePipeline(),  # type: ignore[arg-type]
        FakeSoar(),  # type: ignore[arg-type]
        HASSHDNA(),
        ConnectionLimiter(max_total=2),
    )
    return CloudSentinelSession(server)


def test_ttys_and_session_helpers(monkeypatch, tmp_path) -> None:
    logger = TTYLogger("tty-extra")
    logger._dir = tmp_path
    logger.record(b"x")
    fake_aiofiles = types.ModuleType("aiofiles")
    fake_aiofiles.open = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("aiofiles failed"))
    monkeypatch.setitem(sys.modules, "aiofiles", fake_aiofiles)

    async def run_save() -> None:
        await logger.save_async()

    import asyncio

    asyncio.run(run_save())

    def broken_open(*_args: object, **_kwargs: object) -> None:
        raise OSError("open failed")

    # keep the async failure path; sync fallback is covered separately

    session = _session()
    session.data_received("\r", None)
    session._handle_cd([])
    session._handle_cd([".."])
    session._handle_cd(["/tmp"])
    session._handle_cd(["~"])
    session._handle_cd(["work"])
    assert session._resolve_command("id")
    monkeypatch.setitem(sys.modules, "cloudsentinel.metrics", None)
    asyncio.run(session._execute("id"))


def test_setup_logging_import_error(monkeypatch) -> None:
    fake_structlog = types.ModuleType("structlog")

    def fail(**_kwargs: object) -> None:
        raise ImportError("no structlog")

    fake_structlog.configure = fail
    fake_structlog.get_logger = lambda _name=None: types.SimpleNamespace(debug=lambda *_a: None)
    fake_structlog.stdlib = types.SimpleNamespace(
        filter_by_level=lambda *_a: None,
        add_logger_name=lambda *_a: None,
        add_log_level=lambda *_a: None,
        PositionalArgumentsFormatter=lambda: None,
        LoggerFactory=lambda: None,
        BoundLogger=object,
    )
    fake_structlog.processors = types.SimpleNamespace(
        TimeStamper=lambda **_k: None,
        StackInfoRenderer=lambda: None,
        format_exc_info=None,
        UnicodeDecoder=lambda: None,
        JSONRenderer=lambda **_k: None,
    )
    fake_structlog.dev = types.SimpleNamespace(ConsoleRenderer=lambda: None)
    monkeypatch.setitem(sys.modules, "structlog", fake_structlog)
    server_module.setup_logging(False)


def test_admin_cert_path(monkeypatch, tmp_path) -> None:
    cert = tmp_path / "cert"
    key = tmp_path / "key"
    cert.write_text("cert")
    key.write_text("key")
    fake_uvicorn = types.ModuleType("uvicorn")
    fake_uvicorn.Config = lambda *_a, **_k: object()
    class FakeUvicornServer:
        def __init__(self, _config: object) -> None:
            pass

        async def serve(self) -> None:
            return None

    fake_uvicorn.Server = FakeUvicornServer
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    monkeypatch.setitem(sys.modules, "granian", None)
    monkeypatch.setenv("ADMIN_SERVER", "uvicorn")
    settings = load_settings("src/cloudsentinel/configs/usas-production.yaml", "src/cloudsentinel/.env")
    asyncio.run(server_module.start_admin_api(settings, FakePipeline(), None, str(cert), str(key)))
