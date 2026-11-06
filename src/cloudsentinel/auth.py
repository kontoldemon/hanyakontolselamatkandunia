"""
CloudSentinel JWT Authentication — admin API + dashboard protection.
Uses HS256 with configurable secret, token expiry, and refresh.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger("cloudsentinel.auth")


@dataclass
class AuthConfig:
    """JWT auth configuration loaded from environment."""

    secret: str = ""
    token_expiry_seconds: int = 3600  # 1 hour
    refresh_expiry_seconds: int = 86400  # 24 hours
    enabled: bool = False

    @classmethod
    def from_env(cls) -> AuthConfig:
        return cls(
            secret=os.getenv("CLOUDSENTINEL_AUTH_SECRET", ""),
            token_expiry_seconds=int(os.getenv("CLOUDSENTINEL_TOKEN_EXPIRY", "3600")),
            refresh_expiry_seconds=int(os.getenv("CLOUDSENTINEL_REFRESH_EXPIRY", "86400")),
            enabled=os.getenv("CLOUDSENTINEL_AUTH_ENABLED", "").lower() in ("true", "1", "yes"),
        )



class PyJWTAuth:
    """Standard JWT implementation using PyJWT (RFC 7519).

    Replaces the manual HMAC implementation with a verified, audited
    library that handles algorithm selection, expiry, and claims correctly.
    """

    def __init__(self, config: AuthConfig | None = None) -> None:
        self.config = config or AuthConfig.from_env()

    def create_token(self, username: str, role: str = "admin") -> str | None:
        try:
            import jwt
            now = int(time.time())
            payload = {
                "sub": username,
                "role": role,
                "iat": now,
                "exp": now + self.config.token_expiry_seconds,
                "iss": "cloudsentinel",
            }
            return jwt.encode(payload, self.config.secret, algorithm="HS256")
        except ImportError:
            return None
        except Exception as exc:
            logger.error("PyJWT token creation failed: %s", exc)
            return None

    def validate_token(self, token: str) -> dict | None:
        try:
            import jwt
            return jwt.decode(
                token,
                self.config.secret,
                algorithms=["HS256"],
                options={"require": ["exp", "sub"]},
            )
        except ImportError:
            return None
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError as exc:
            logger.warning("JWT token invalid: %s", exc)
            return None
        except Exception as exc:
            logger.error("JWT validation error: %s", exc)
            return None

    def create_refresh_token(self, username: str) -> str | None:
        try:
            import jwt
            now = int(time.time())
            payload = {
                "sub": username,
                "type": "refresh",
                "iat": now,
                "exp": now + self.config.refresh_expiry_seconds,
            }
            return jwt.encode(payload, self.config.secret, algorithm="HS256")
        except ImportError:
            return None

    def create_login_token(self, username: str) -> dict[str, str | None]:
        return {
            "access_token": self.create_token(username),
            "refresh_token": self.create_refresh_token(username),
            "token_type": "bearer",
        }


class JWTAuth:
    """Minimal HS256 JWT implementation — zero external dependencies."""

    def __init__(self, config: AuthConfig | None = None) -> None:
        self.config = config or AuthConfig.from_env()
        if not self.config.secret and self.config.enabled:
            self.config.secret = hashlib.sha256(os.urandom(64)).hexdigest()
            logger.warning("No AUTH_SECRET set — generated random secret. Set CLOUDSENTINEL_AUTH_SECRET in production.")

    @staticmethod
    def _b64url_encode(data: bytes) -> str:
        import base64
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    @staticmethod
    def _b64url_decode(data: str) -> bytes:
        import base64
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data)

    def create_token(self, payload: dict[str, Any], expiry: int | None = None) -> str:
        """Create a signed JWT token."""
        import json
        expiry = expiry or self.config.token_expiry_seconds
        header = {"alg": "HS256", "typ": "JWT"}
        body = {**payload, "exp": int(time.time()) + expiry, "iat": int(time.time())}

        header_b64 = self._b64url_encode(json.dumps(header, separators=(",", ":")).encode())
        body_b64 = self._b64url_encode(json.dumps(body, separators=(",", ":")).encode())
        signing_input = f"{header_b64}.{body_b64}"

        signature = hmac.new(
            self.config.secret.encode(), signing_input.encode(), hashlib.sha256
        ).digest()
        sig_b64 = self._b64url_encode(signature)

        return f"{signing_input}.{sig_b64}"

    def validate_token(self, token: str) -> dict[str, Any] | None:
        """Validate a JWT token and return payload if valid."""
        import json
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None

            signing_input = f"{parts[0]}.{parts[1]}"
            expected_sig = hmac.new(
                self.config.secret.encode(), signing_input.encode(), hashlib.sha256
            ).digest()

            actual_sig = self._b64url_decode(parts[2])
            if not hmac.compare_digest(expected_sig, actual_sig):
                return None

            payload = json.loads(self._b64url_decode(parts[1]))
            if payload.get("exp", 0) < time.time():
                return None

            return payload
        except Exception:
            return None

    def create_login_token(self, username: str) -> dict[str, str]:
        """Create access + refresh token pair for a user."""
        access = self.create_token({"sub": username, "type": "access"})
        refresh = self.create_token(
            {"sub": username, "type": "refresh"}, self.config.refresh_expiry_seconds
        )
        return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


# Singleton
_auth: JWTAuth | None = None


def get_auth() -> JWTAuth:
    """Get the best available auth backend (PyJWT > manual)."""
    try:
        import jwt  # noqa: F401
        _pyjwt = PyJWTAuth()
        if _pyjwt.config.secret:
            logger.debug("Using PyJWT (RFC 7519) for auth")
            # Return wrapper that delegates to PyJWT
            return _pyjwt  # type: ignore[return-value]
    except ImportError:
        pass
    return _get_manual_auth()


def _get_manual_auth() -> JWTAuth:
    global _auth
    if _auth is None:
        _auth = JWTAuth()
    return _auth
