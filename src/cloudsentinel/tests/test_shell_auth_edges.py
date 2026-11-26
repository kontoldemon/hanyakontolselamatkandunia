"""Cover shell error branches and JWT validation edge cases."""

from __future__ import annotations

import sys
import types

import pytest

import cloudsentinel.auth as auth_module
from cloudsentinel.auth import AuthConfig, JWTAuth, PyJWTAuth


def test_jwt_validation_errors(monkeypatch) -> None:
    auth = PyJWTAuth(AuthConfig(secret="secret", enabled=True))
    fake_jwt = types.ModuleType("jwt")

    def decode(*_args: object, **_kwargs: object) -> dict:
        raise RuntimeError("generic jwt error")

    fake_jwt.decode = decode
    fake_jwt.ExpiredSignatureError = type("ExpiredSignatureError", (Exception,), {})
    fake_jwt.InvalidTokenError = type("InvalidTokenError", (Exception,), {})
    fake_jwt.encode = lambda *_args, **_kwargs: "token"
    monkeypatch.setitem(sys.modules, "jwt", fake_jwt)
    assert auth.validate_token("token") is None

    manual = JWTAuth(AuthConfig(secret="secret", enabled=True))
    monkeypatch.setattr(auth_module.hmac, "compare_digest", lambda *_args: True)
    monkeypatch.setattr(
        JWTAuth,
        "_b64url_decode",
        staticmethod(lambda _data: b"not-json"),
    )
    assert manual.validate_token("a.b.c") is None
