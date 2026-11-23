"""Tests for the Event Grid block-request publisher."""

from __future__ import annotations

import json

import pytest

import cloudsentinel.eventgrid as eventgrid


class FakeResponse:
    def __init__(self, status_code: int = 202, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


class FakeClient:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.calls: list[tuple[str, bytes, dict[str, str]]] = []
        self.failure: Exception | None = None
        self.response = FakeResponse()

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    async def post(
        self,
        url: str,
        content: bytes,
        headers: dict[str, str],
        **_kwargs: object,
    ) -> FakeResponse:
        if self.failure is not None:
            raise self.failure
        self.calls.append((url, content, headers))
        return self.response


def _install_client(monkeypatch: pytest.MonkeyPatch) -> list[FakeClient]:
    instances: list[FakeClient] = []

    def factory(**kwargs: object) -> FakeClient:
        client = FakeClient(**kwargs)
        instances.append(client)
        return client

    monkeypatch.setattr(eventgrid.httpx, "AsyncClient", factory)
    return instances


@pytest.mark.asyncio
async def test_publish_block_posts_cloudevent(monkeypatch) -> None:
    instances = _install_client(monkeypatch)
    ok, error = await eventgrid.publish_block(
        endpoint="https://topic.example.com/api/events",
        key="topic-key",
        ip="8.8.8.8",
        ttl=60,
        reason="unit-test",
        risk_score=90,
        session_id="s1",
    )

    assert ok is True
    assert error == ""
    client = instances[0]
    assert client.kwargs["timeout"] == 5.0
    url, content, headers = client.calls[0]
    assert url == "https://topic.example.com/api/events"
    assert headers["aeg-sas-key"] == "topic-key"
    assert headers["Content-Type"] == "application/cloudevents+json"
    event = json.loads(content)
    assert event["type"] == "CloudSentinel.BlockRequested"
    assert event["source"] == "cloudsentinel.sensor"
    assert event["specversion"] == "1.0"
    assert event["data"]["ip"] == "8.8.8.8"
    assert event["data"]["ttl"] == 60
    assert event["data"]["reason"] == "unit-test"
    assert event["data"]["risk_score"] == 90
    assert event["data"]["session_id"] == "s1"


@pytest.mark.asyncio
async def test_publish_block_rejects_bad_input(monkeypatch) -> None:
    instances = _install_client(monkeypatch)

    ok, error = await eventgrid.publish_block(
        endpoint="https://topic.example.com/api/events",
        key="topic-key",
        ip="not-an-ip",
        ttl=60,
        reason="unit",
        risk_score=1,
        session_id="s",
    )
    assert ok is False
    assert "invalid" in error.lower()

    ok, error = await eventgrid.publish_block(
        endpoint="http://topic.example.com/api/events",
        key="topic-key",
        ip="8.8.8.8",
        ttl=60,
        reason="unit",
        risk_score=1,
        session_id="s",
    )
    assert ok is False
    assert "https" in error.lower()

    ok, error = await eventgrid.publish_block(
        endpoint="https://topic.example.com/api/events",
        key="",
        ip="8.8.8.8",
        ttl=60,
        reason="unit",
        risk_score=1,
        session_id="s",
    )
    assert ok is False
    assert "key" in error.lower()
    assert instances == []


@pytest.mark.asyncio
async def test_publish_block_reports_http_and_transport_errors(monkeypatch) -> None:
    client = FakeClient(timeout=5.0)
    monkeypatch.setattr(eventgrid.httpx, "AsyncClient", lambda **_kwargs: client)

    async def publish() -> tuple[bool, str]:
        return await eventgrid.publish_block(
            endpoint="https://topic.example.com/api/events",
            key="topic-key",
            ip="8.8.8.8",
            ttl=60,
            reason="unit",
            risk_score=1,
            session_id="s",
        )

    ok, error = await publish()
    assert ok is True
    assert error == ""

    client.response = FakeResponse(500, "boom")
    ok, error = await publish()
    assert ok is False
    assert "500" in error
    assert "boom" in error

    client.failure = RuntimeError("network down")
    ok, error = await publish()
    assert ok is False
    assert "network down" in error
