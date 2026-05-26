"""
CloudSentinel Secret Management — HashiCorp Vault + Infisical integration.
Provides secure secret retrieval with automatic fallback to env vars.
"""

from __future__ import annotations

import structlog
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = structlog.get_logger("cloudsentinel.vault")

VAULT_ADDR = os.getenv("VAULT_ADDR", "")
VAULT_TOKEN = os.getenv("VAULT_TOKEN", "")
VAULT_MOUNT = os.getenv("VAULT_MOUNT", "secret")
INFISICAL_CLIENT_ID = os.getenv("INFISICAL_CLIENT_ID", "")
INFISICAL_CLIENT_SECRET = os.getenv("INFISICAL_CLIENT_SECRET", "")
INFISICAL_PROJECT_ID = os.getenv("INFISICAL_PROJECT_ID", "")


@dataclass
class SecretStore:
    """Unified secret retrieval across Vault, Infisical, and env fallback."""

    provider: str = "env"  # "vault", "infisical", "env"
    _cache: dict[str, str] = field(default_factory=dict)
    _client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        if VAULT_ADDR and VAULT_TOKEN:
            self.provider = "vault"
            self._client = httpx.AsyncClient(
                base_url=VAULT_ADDR.rstrip("/"),
                headers={"X-Vault-Token": VAULT_TOKEN},
                timeout=10.0,
            )
            logger.info("Secret store: HashiCorp Vault at %s", VAULT_ADDR)
        elif INFISICAL_CLIENT_ID and INFISICAL_CLIENT_SECRET:
            self.provider = "infisical"
            self._client = httpx.AsyncClient(
                base_url="https://app.infisical.com",
                timeout=10.0,
            )
            logger.info("Secret store: Infisical (project %s)", INFISICAL_PROJECT_ID)
        else:
            logger.info("Secret store: environment variables (no Vault/Infisical detected)")

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()

    async def get(self, key: str, default: str = "") -> str:
        """Retrieve a secret with cache + fallback chain."""
        if key in self._cache:
            return self._cache[key]

        value = ""
        if self.provider == "vault":
            value = await self._get_vault(key)
        elif self.provider == "infisical":
            value = await self._get_infisical(key)

        if not value:
            value = os.getenv(key, default)

        if value:
            self._cache[key] = value
        return value

    async def _get_vault(self, key: str) -> str:
        try:
            path = f"/v1/{VAULT_MOUNT}/data/{key.lower()}"
            resp = await self._client.get(path)  # type: ignore[union-attr]
            resp.raise_for_status()
            data = resp.json()
            return str(data.get("data", {}).get("data", {}).get(key, ""))
        except Exception as exc:
            logger.debug("Vault read '%s' failed: %s", key, exc)
            return ""

    async def _get_infisical(self, key: str) -> str:
        try:
            # Get access token
            token_resp = await self._client.post(  # type: ignore[union-attr]
                "/api/v1/auth/universal-auth/login",
                json={
                    "clientId": INFISICAL_CLIENT_ID,
                    "clientSecret": INFISICAL_CLIENT_SECRET,
                },
            )
            token_resp.raise_for_status()
            access_token = token_resp.json()["accessToken"]

            # Get secret
            secret_resp = await self._client.get(  # type: ignore[union-attr]
                f"/api/v3/secrets/raw/{key}",
                params={
                    "workspaceId": INFISICAL_PROJECT_ID,
                    "environment": os.getenv("INFISICAL_ENV", "prod"),
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )
            secret_resp.raise_for_status()
            return secret_resp.json().get("secret", {}).get("value", "")
        except Exception as exc:
            logger.debug("Infisical read '%s' failed: %s", key, exc)
            return ""

    def get_sync(self, key: str, default: str = "") -> str:
        """Synchronous fallback for bootstrap."""
        return os.getenv(key, default)


# Singleton
_secret_store: SecretStore | None = None


def get_secret_store() -> SecretStore:
    global _secret_store
    if _secret_store is None:
        _secret_store = SecretStore()
    return _secret_store
