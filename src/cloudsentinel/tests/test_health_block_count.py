import pytest

from cloudsentinel.api.block_state import count_active_blocks


class FakeClient:
    def __init__(
        self,
        keys: list[str] | None = None,
        fail: bool = False,
        close_fail: bool = False,
    ) -> None:
        self._keys = keys or []
        self._fail = fail
        self._close_fail = close_fail
        self.closed = False

    def scan_iter(self, match: str | None = None):
        async def gen():
            if self._fail:
                raise RuntimeError("redis unavailable")
            for key in self._keys:
                yield key

        return gen()

    async def aclose(self) -> None:
        self.closed = True
        if self._close_fail:
            raise RuntimeError("close failed")


@pytest.mark.asyncio
async def test_count_active_blocks_prefers_live_keys(monkeypatch) -> None:
    client = FakeClient(["soar:block:1.1.1.1", "soar:block:8.8.8.8"])
    monkeypatch.setattr("redis.asyncio.from_url", lambda *_args, **_kwargs: client)

    assert await count_active_blocks("redis://unit", 9) == 2
    assert client.closed is True


@pytest.mark.asyncio
async def test_count_active_blocks_falls_back_on_scan_error(monkeypatch) -> None:
    client = FakeClient(fail=True)
    monkeypatch.setattr("redis.asyncio.from_url", lambda *_args, **_kwargs: client)

    assert await count_active_blocks("redis://unit", 5) == 5
    assert client.closed is True


@pytest.mark.asyncio
async def test_count_active_blocks_falls_back_on_client_error(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise RuntimeError("cannot connect")

    monkeypatch.setattr("redis.asyncio.from_url", boom)

    assert await count_active_blocks("redis://unit", 4) == 4


@pytest.mark.asyncio
async def test_count_active_blocks_ignores_close_error(monkeypatch) -> None:
    client = FakeClient(["soar:block:1.1.1.1"], close_fail=True)
    monkeypatch.setattr("redis.asyncio.from_url", lambda *_args, **_kwargs: client)

    assert await count_active_blocks("redis://unit", 9) == 1
    assert client.closed is True
