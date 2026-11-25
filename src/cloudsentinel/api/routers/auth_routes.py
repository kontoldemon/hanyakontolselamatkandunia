"""Admin API login route."""

from __future__ import annotations

import hmac
import os
from typing import Any

from fastapi import APIRouter, HTTPException


def build_auth_router() -> APIRouter:
    router = APIRouter()

    @router.post("/auth/login")
    async def login(body: dict[str, str]) -> dict[str, Any]:
        try:
            from ...auth import get_auth

            auth = get_auth()
            if not auth.config.enabled:
                return {"message": "Auth not enabled", "token": "dev-mode"}
            username = body.get("username", "")
            password = body.get("password", "")
            expected_user = os.getenv("CLOUDSENTINEL_ADMIN_USER", "admin")
            expected_pass = os.getenv("CLOUDSENTINEL_ADMIN_PASS", "")
            if not expected_pass:
                raise HTTPException(status_code=503, detail="Admin login is not configured")
            if not hmac.compare_digest(username.encode(), expected_user.encode()) or not hmac.compare_digest(
                password.encode(), expected_pass.encode()
            ):
                raise HTTPException(status_code=401, detail="Invalid credentials")
            return auth.create_login_token(username)
        except HTTPException:
            raise
        except Exception:
            return {"message": "Auth module unavailable", "token": "dev-mode"}

    return router
