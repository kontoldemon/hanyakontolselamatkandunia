"""Live stream authentication wiring tests."""

from __future__ import annotations

from cloudsentinel.config import load_settings, secret_to_str
from cloudsentinel.stream import LiveStream


def test_stream_accepts_token_from_all_supported_sources() -> None:
    stream = LiveStream(auth_token="stream-secret")
    assert stream._authorized({}, {"token": "stream-secret"}) is True
    assert stream._authorized({"QUERY_STRING": "token=stream-secret"}, None) is True
    assert stream._authorized({"HTTP_AUTHORIZATION": "Bearer stream-secret"}, None) is True


def test_stream_rejects_missing_or_wrong_token() -> None:
    stream = LiveStream(auth_token="stream-secret")
    assert stream._authorized({}, None) is False
    assert stream._authorized({}, {"token": "wrong"}) is False
    assert stream._authorized({"QUERY_STRING": "token=wrong"}, None) is False


def test_stream_is_open_when_no_token_configured() -> None:
    assert LiveStream()._authorized({}, None) is True


def test_stream_auth_token_loads_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("STREAM_AUTH_TOKEN", "env-secret")
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    assert secret_to_str(settings.stream.auth_token) == "env-secret"
