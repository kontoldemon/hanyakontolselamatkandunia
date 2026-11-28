import asyncio

import pytest

import cloudsentinel.server as server


class _FakeLogger:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def error(self, *args, **kwargs) -> None:
        self.calls.append(args)


def test_report_honeypot_failure_logs_only_real_errors(monkeypatch) -> None:
    fake = _FakeLogger()
    monkeypatch.setattr(server, "logger", fake)

    async def scenario() -> None:
        async def boom() -> None:
            raise RuntimeError("boom")

        failed = asyncio.create_task(boom())
        with pytest.raises(RuntimeError):
            await failed
        server.report_honeypot_failure("HTTP")(failed)

        async def ok() -> None:
            return None

        done = asyncio.create_task(ok())
        await done
        server.report_honeypot_failure("HTTP")(done)

        cancelled = asyncio.create_task(ok())
        cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled
        server.report_honeypot_failure("DNS")(cancelled)

    asyncio.run(scenario())

    assert len(fake.calls) == 1
    assert fake.calls[0][0] == "%s honeypot stopped: %s"
    assert fake.calls[0][1] == "HTTP"
    assert "boom" in str(fake.calls[0][2])
