"""
CloudSentinel JWT Authentication — admin API + dashboard protection.
Uses HS256 with configurable secret, token expiry, and refresh.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("cloudsentinel.auth")


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
            enabled=bool(os.getenv("CLOUDSENTINEL_AUTH_ENABLED", "")),
        )


class JWTAuth:
    """Minimal HS256 JWT implementation — zero external dependencies."""

    def __init__(self, config: AuthConfig | None = None) -> None:
        self.config = config or AuthConfig.from_env()
        if not self.config.secret and self.config.enabled:
            self.config.secret = hashlib.sha256(os.urandom(64)).hexdigest()
            logger.warning("No AUTH_SECRET set — generated random: %s...", self.config.secret[:8])

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
    global _auth
    if _auth is None:
        _auth = JWTAuth()
    return _auth
