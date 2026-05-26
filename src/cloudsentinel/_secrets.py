"""
CloudSentinel Secrets Provider — unified interface for Infisical / Vault / env.

Supports three backends:
  - env:     Read from environment variables (default, zero-dependency)
  - infisical: Infisical API (MIT-licensed, cloud-native secrets)
  - vault:   HashiCorp Vault / OpenBao via hvac (already in requirements)

Usage:
    from cloudsentinel.secrets import get_secret, SecretsProvider
    provider = SecretsProvider.create("infisical")
    redis_pass = await provider.get("REDIS_PASSWORD")
"""

from __future__ import annotations

import asyncio
import structlog
import os
from abc import ABC, abstractmethod
from typing import Any

logger = structlog.get_logger("cloudsentinel.secrets")

SECRETS_PROVIDER = os.getenv("CLOUDSENTINEL_SECRETS_PROVIDER", "env")


class SecretsProvider(ABC):
    """Abstract secrets provider."""

    @abstractmethod
    async def get(self, key: str, default: str = "") -> str: ...

    @abstractmethod
    async def get_all(self, prefix: str = "") -> dict[str, str]: ...

    @abstractmethod
    async def close(self) -> None: ...

    @staticmethod
    def create(provider: str | None = None) -> "SecretsProvider":
        """Factory: return the configured secrets backend."""
        backend = (provider or SECRETS_PROVIDER).lower()
        if backend == "infisical":
            return InfisicalProvider()
        elif backend == "vault":
            return VaultProvider()
        else:
            return EnvProvider()


class EnvProvider(SecretsProvider):
    """Read secrets from os.environ. Zero dependencies."""

    async def get(self, key: str, default: str = "") -> str:
        return os.getenv(key, default)

    async def get_all(self, prefix: str = "") -> dict[str, str]:
        result: dict[str, str] = {}
        for k, v in os.environ.items():
            if k.startswith(prefix):
                result[k] = v
        return result

    async def close(self) -> None:
        pass


class InfisicalProvider(SecretsProvider):
    """Infisical secrets provider — MIT-licensed, cloud-native.

    Docs: https://infisical.com/docs/documentation/getting-started/introduction
    """

    def __init__(self) -> None:
        self._client_id = os.getenv("INFISICAL_CLIENT_ID", "")
        self._client_secret = os.getenv("INFISICAL_CLIENT_SECRET", "")
        self._project_id = os.getenv("INFISICAL_PROJECT_ID", "")
        self._token: str | None = None
        self._last_fetch: float = 0.0
        self._available = bool(self._client_id and self._client_secret)

    async def _ensure_authenticated(self) -> None:
        """Authenticate with Infisical Universal Auth and cache token."""
        if not self._available:
            return
        if self._token and (asyncio.get_event_loop().time() - self._last_fetch) < 240:
            return

        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://app.infisical.com/api/v1/auth/universal-auth/login",
                    json={
                        "clientId": self._client_id,
                        "clientSecret": self._client_secret,
                    },
                )
                resp.raise_for_status()
                self._token = resp.json()["accessToken"]
                logger.debug("Infisical: authenticated")
        except Exception as exc:
            logger.warning("Infisical auth failed: %s — falling back to env", exc)
            self._available = False

    async def get(self, key: str, default: str = "") -> str:
        if not self._available:
            return os.getenv(key, default)
        await self._ensure_authenticated()
        if not self._token:
            return os.getenv(key, default)

        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"https://app.infisical.com/api/v3/secrets/raw/{key}",
                    headers={"Authorization": f"Bearer {self._token}"},
                    params={"workspaceId": self._project_id},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("secret", {}).get("secretValue", default)
                return os.getenv(key, default)
        except Exception:
            return os.getenv(key, default)

    async def get_all(self, prefix: str = "") -> dict[str, str]:
        if not self._available:
            envs: dict[str, str] = {}
            for k, v in os.environ.items():
                if k.startswith(prefix):
                    envs[k] = v
            return envs
        await self._ensure_authenticated()

        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://app.infisical.com/api/v3/secrets",
                    headers={"Authorization": f"Bearer {self._token}"},
                    params={"workspaceId": self._project_id, "environment": "prod"},
                )
                if resp.status_code == 200:
                    secrets = resp.json().get("secrets", [])
                    return {
                        s["secretKey"]: s.get("secretValue", "")
                        for s in secrets
                        if s["secretKey"].startswith(prefix)
                    }
        except Exception:
            pass
        return {}

    async def close(self) -> None:
        pass


class VaultProvider(SecretsProvider):
    """HashiCorp Vault / OpenBao provider via hvac.

    Works with both Vault (BSL) and OpenBao (MPL 2.0).
    hvac is already in requirements.txt.
    """

    def __init__(self) -> None:
        self._addr = os.getenv("VAULT_ADDR", "")
        self._token = os.getenv("VAULT_TOKEN", "")
        self._available = bool(self._addr and self._token)
        self._client: Any = None

    async def _ensure_client(self) -> None:
        if self._client is not None:
            return
        try:
            import hvac

            self._client = hvac.AsyncClient(url=self._addr, token=self._token)
            if not await self._client.is_authenticated():
                self._available = False
                logger.warning("Vault: token invalid")
        except ImportError:
            self._available = False
            logger.warning("hvac not installed — Vault disabled")
        except Exception as exc:
            self._available = False
            logger.warning("Vault connection failed: %s", exc)

    async def get(self, key: str, default: str = "") -> str:
        if not self._available:
            return os.getenv(key, default)
        await self._ensure_client()
        if not self._client:
            return os.getenv(key, default)
        try:
            secret_path = f"cloudsentinel/data/{key.lower()}"
            resp = await self._client.secrets.kv.v2.read_secret_version(
                path=secret_path, mount_point="secret",
            )
            data = resp.get("data", {}).get("data", {})
            return data.get("value", os.getenv(key, default))
        except Exception:
            return os.getenv(key, default)

    async def get_all(self, prefix: str = "") -> dict[str, str]:
        if not self._available:
            envs: dict[str, str] = {}
            for k, v in os.environ.items():
                if k.startswith(prefix):
                    envs[k] = v
            return envs
        await self._ensure_client()
        try:
            resp = await self._client.secrets.kv.v2.list_secrets(
                path="cloudsentinel", mount_point="secret",
            )
            keys = resp.get("data", {}).get("keys", [])
            result: dict[str, str] = {}
            for key in keys:
                if key.startswith(prefix):
                    val = await self.get(key)
                    result[key] = val
            return result
        except Exception:
            return {}

    async def close(self) -> None:
        if self._client:
            await self._client.close()


# ── Singleton ────────────────────────────────────────────────────────

_provider: SecretsProvider | None = None


async def get_secrets_provider() -> SecretsProvider:
    global _provider
    if _provider is None:
        _provider = SecretsProvider.create()
    return _provider


async def get_secret(key: str, default: str = "") -> str:
    provider = await get_secrets_provider()
    return await provider.get(key, default)
