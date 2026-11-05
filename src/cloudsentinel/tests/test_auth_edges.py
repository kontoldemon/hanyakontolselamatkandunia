"""Edge cases for PyJWT and the manual JWT fallback."""

from __future__ import annotations

import sys
import time

import pytest

import cloudsentinel.auth as auth_module
from cloudsentinel.auth import AuthConfig, JWTAuth, PyJWTAuth, get_auth


def test_pyjwt_round_trip() -> None:
    jwt = pytest.importorskip("jwt")
    config = AuthConfig(secret="unit-secret", enabled=True, token_expiry_seconds=60)
    auth = PyJWTAuth(config)
    token = auth.create_token("alice")
    assert token
    assert auth.validate_token(token)["sub"] == "alice"
    refresh = auth.create_refresh_token("alice")
    assert refresh
    assert auth.validate_token(refresh)["type"] == "refresh"

    expired = jwt.encode(
        {"sub": "alice", "exp": int(time.time()) - 10},
        "unit-secret",
        algorithm="HS256",
    )
    assert auth.validate_token(expired) is None
    assert auth.validate_token("not-a-token") is None


def test_pyjwt_without_library(monkeypatch: pytest.MonkeyPatch) -> None:
    auth = PyJWTAuth(AuthConfig(secret="unit-secret", enabled=True))
    monkeypatch.setitem(sys.modules, "jwt", None)
    assert auth.create_token("alice") is None
    assert auth.validate_token("token") is None
    assert auth.create_refresh_token("alice") is None


def test_manual_jwt_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    auth = JWTAuth(AuthConfig(secret="unit-secret", enabled=True))
    token = auth.create_token({"sub": "alice", "type": "access"})
    assert auth.validate_token(token)["sub"] == "alice"
    assert auth.validate_token(token + "tampered") is None
    assert auth.validate_token("one.two") is None
    expired = auth.create_token({"sub": "alice"}, expiry=-10)
    assert auth.validate_token(expired) is None
    pair = auth.create_login_token("alice")
    assert pair["access_token"] and pair["refresh_token"]

    generated = JWTAuth(AuthConfig(secret="", enabled=True))
    assert generated.config.secret

    monkeypatch.setitem(sys.modules, "jwt", None)
    monkeypatch.setattr(auth_module, "_auth", None)
    manual = get_auth()
    assert isinstance(manual, JWTAuth)
