"""Cover LiveStream authentication, replay, emit, and lifecycle."""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

from cloudsentinel.stream import LiveStream


class FakeSio:
    def __init__(self, **_kwargs: object) -> None:
        self.handlers: dict = {}
        self.emitted: list[tuple] = []
        self.disconnected: list[str] = []

    def event(self, func):
        self.handlers[func.__name__] = func
        return func

    def attach(self, app: object) -> None:
        self.app = app

    async def emit(self, event: str, data: dict, to: str | None = None) -> None:
        self.emitted.append((event, data, to))

    async def disconnect(self, sid: str) -> None:
        self.disconnected.append(sid)


@pytest.mark.asyncio
async def test_live_stream(monkeypatch) -> None:
    socketio = types.ModuleType("socketio")
    socketio.AsyncServer = FakeSio
    monkeypatch.setitem(sys.modules, "socketio", socketio)

    aiohttp = types.ModuleType("aiohttp")
    web = types.ModuleType("aiohttp.web")

    class Application:
        pass

    class Runner:
        def __init__(self, app: object) -> None:
            self.app = app

        async def setup(self) -> None:
            return None

        async def cleanup(self) -> None:
            return None

    class Site:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def start(self) -> None:
            return None

    web.Application = Application
    web.AppRunner = Runner
    web.TCPSite = Site
    aiohttp.web = web
    monkeypatch.setitem(sys.modules, "aiohttp", aiohttp)
    monkeypatch.setitem(sys.modules, "aiohttp.web", web)

    stream = LiveStream(auth_token="secret", cors_origin="*")
    await stream.start()
    assert stream._started
    sio = stream._sio

    await sio.handlers["connect"](
        "sid-1",
        {"HTTP_AUTHORIZATION": "Bearer secret", "QUERY_STRING": ""},
    )
    assert "sid-1" in stream._auth_clients

    await sio.handlers["connect"](
        "sid-2",
        {"HTTP_AUTHORIZATION": "", "QUERY_STRING": "token=secret"},
    )
    assert "sid-2" in stream._auth_clients

    await sio.handlers["connect"](
        "sid-3",
        {"HTTP_AUTHORIZATION": "Bearer wrong", "QUERY_STRING": ""},
    )
    assert "sid-3" not in stream._auth_clients
    assert "sid-3" in sio.disconnected

    await sio.handlers["subscribe"]("sid-1", {"types": ["login"]})
    await sio.handlers["subscribe"]("sid-unknown", {"types": ["login"]})
    await sio.handlers["disconnect"]("sid-1")
    assert "sid-1" not in stream._auth_clients

    stream.emit({"eventid": "evt", "system": "raw", "log_secret": "x"})
    await asyncio.sleep(0)
    assert stream._buffer[-1] == {"eventid": "evt"}
    assert sio.emitted

    await stream.emit_coro({"eventid": "evt2"})
    await stream.stop()
    assert not stream._started

    idle = LiveStream()
    idle.emit({"eventid": "dropped"})
    await idle.emit_coro({"eventid": "dropped"})
    assert not idle._buffer
