"""
CloudSentinel Centralized Configuration — single source of truth.

All modules should import settings from here instead of calling os.getenv().
This ensures consistent defaults, validation, and secrets provider integration.

Usage:
    from cloudsentinel.settings import get_settings
    settings = get_settings()
    api_key = settings.abuseipdb_api_key
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class CentralSettings:
    """All CloudSentinel configuration in one place — no more os.getenv() sprawl."""

    # ── Honeypot ──
    listen_host: str = "0.0.0.0"
    ssh_port: int = 2222
    hostname: str = "usas-prod-srv-01"

    # ── LLM ──
    llm_api_key: str = ""
    llm_model: str = "gemini/gemini-2.0-flash"
    llm_provider: str = "litellm"

    # ── Redis ──
    redis_url: str = "redis://redis:6379/0"
    redis_password: str = ""

    # ── ClickHouse ──
    clickhouse_host: str = "clickhouse"
    clickhouse_port: int = 8123
    clickhouse_username: str = "cloudsentinel"
    clickhouse_password: str = ""

    # ── Auth ──
    auth_enabled: bool = False
    auth_secret: str = ""
    admin_user: str = "admin"
    admin_pass: str = ""

    # ── SOAR ──
    soar_firewall_enabled: bool = True
    soar_firewall_dry_run: bool = True
    soar_risk_threshold: int = 70
    soar_block_ttl: int = 86400
    soar_active_profile: str = "local"
    firewall_backend: str = "nftables"
    firewall_path: str = "/usr/sbin/nft"

    # ── Webhooks ──
    slack_webhook: str = ""
    discord_webhook: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    webhooks_enabled: bool = False
    alert_threshold: int = 70
    alert_cooldown: float = 300.0

    # ── Threat Intel ──
    abuseipdb_api_key: str = ""
    misp_url: str = ""
    misp_api_key: str = ""

    # ── Observability ──
    sentry_dsn: str = ""
    otel_enabled: bool = False
    otel_endpoint: str = ""

    # ── Sandbox ──
    sandbox_runtime: str = "gvisor"
    sandbox_memory: str = "128m"
    sandbox_cpus: str = "0.5"
    sandbox_timeout: float = 30.0

    # ── Stream ──
    stream_host: str = "0.0.0.0"
    stream_port: int = 3001
    stream_cors_origin: str = "*"

    # ── Admin ──
    admin_port: int = 8080
    admin_token: str = ""

    # ── Secrets Provider ──
    secrets_provider: str = "env"
    vault_addr: str = ""
    vault_token: str = ""
    infisical_client_id: str = ""
    infisical_client_secret: str = ""
    infisical_project_id: str = ""

    @classmethod
    def from_env(cls) -> CentralSettings:
        """Load all settings from environment variables."""
        def _str(key: str, default: str = "") -> str:
            return os.getenv(key, default)
        def _bool(key: str, default: bool = False) -> bool:
            val = os.getenv(key, "")
            return val.lower() in ("true", "1", "yes") if val else default
        def _int(key: str, default: int = 0) -> int:
            try:
                return int(os.getenv(key, str(default)))
            except (ValueError, TypeError):
                return default
        def _float(key: str, default: float = 0.0) -> float:
            try:
                return float(os.getenv(key, str(default)))
            except (ValueError, TypeError):
                return default

        return cls(
            listen_host=_str("CLOUDSENTINEL_LISTEN_HOST", "0.0.0.0"),
            ssh_port=_int("CLOUDSENTINEL_SSH_PORT", 2222),
            hostname=_str("CLOUDSENTINEL_HOSTNAME", "usas-prod-srv-01"),
            llm_api_key=_str("LLM_API_KEY"),
            llm_model=_str("LLM_MODEL", "gemini/gemini-2.0-flash"),
            llm_provider=_str("LLM_PROVIDER", "litellm"),
            redis_url=_str("REDIS_URL", "redis://redis:6379/0"),
            clickhouse_host=_str("CLICKHOUSE_HOST", "clickhouse"),
            clickhouse_port=_int("CLICKHOUSE_PORT", 8123),
            clickhouse_username=_str("CLICKHOUSE_USERNAME", "cloudsentinel"),
            clickhouse_password=_str("CLICKHOUSE_PASSWORD"),
            auth_enabled=_bool("CLOUDSENTINEL_AUTH_ENABLED"),
            auth_secret=_str("CLOUDSENTINEL_AUTH_SECRET"),
            admin_user=_str("CLOUDSENTINEL_ADMIN_USER", "admin"),
            admin_pass=_str("CLOUDSENTINEL_ADMIN_PASS"),
            soar_firewall_enabled=_bool("SOAR_FIREWALL_ENABLED", True),
            soar_firewall_dry_run=_bool("SOAR_FIREWALL_DRY_RUN", True),
            soar_risk_threshold=_int("SOAR_RISK_THRESHOLD", 70),
            soar_block_ttl=_int("SOAR_BLOCK_TTL", 86400),
            soar_active_profile=_str("SOAR_ACTIVE_PROFILE", "local"),
            firewall_backend=_str("CLOUDSENTINEL_FIREWALL_BACKEND", "nftables"),
            slack_webhook=_str("CLOUDSENTINEL_SLACK_WEBHOOK"),
            discord_webhook=_str("CLOUDSENTINEL_DISCORD_WEBHOOK"),
            telegram_bot_token=_str("CLOUDSENTINEL_TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_str("CLOUDSENTINEL_TELEGRAM_CHAT_ID"),
            webhooks_enabled=_bool("CLOUDSENTINEL_WEBHOOKS_ENABLED"),
            alert_threshold=_int("CLOUDSENTINEL_ALERT_THRESHOLD", 70),
            alert_cooldown=_float("CLOUDSENTINEL_ALERT_COOLDOWN", 300.0),
            abuseipdb_api_key=_str("CLOUDSENTINEL_ABUSEIPDB_KEY"),
            misp_url=_str("CLOUDSENTINEL_MISP_URL"),
            misp_api_key=_str("CLOUDSENTINEL_MISP_API_KEY"),
            sentry_dsn=_str("SENTRY_DSN"),
            otel_enabled=_bool("OTEL_ENABLED"),
            otel_endpoint=_str("OTEL_EXPORTER_OTLP_ENDPOINT"),
            sandbox_runtime=_str("CLOUDSENTINEL_SANDBOX_RUNTIME", "gvisor"),
            sandbox_memory=_str("CLOUDSENTINEL_SANDBOX_MEMORY", "128m"),
            sandbox_cpus=_str("CLOUDSENTINEL_SANDBOX_CPUS", "0.5"),
            sandbox_timeout=_float("CLOUDSENTINEL_SANDBOX_TIMEOUT", 30.0),
            stream_host=_str("STREAM_HOST", "0.0.0.0"),
            stream_port=_int("STREAM_PORT", 3001),
            stream_cors_origin=_str("STREAM_CORS_ORIGIN", "*"),
            admin_port=_int("ADMIN_PORT", 8080),
            admin_token=_str("ADMIN_TOKEN"),
            secrets_provider=_str("CLOUDSENTINEL_SECRETS_PROVIDER", "env"),
            vault_addr=_str("VAULT_ADDR"),
            vault_token=_str("VAULT_TOKEN"),
            infisical_client_id=_str("INFISICAL_CLIENT_ID"),
            infisical_client_secret=_str("INFISICAL_CLIENT_SECRET"),
            infisical_project_id=_str("INFISICAL_PROJECT_ID"),
        )


@lru_cache(maxsize=1)
def get_settings() -> CentralSettings:
    """Get cached centralized settings. Single source of truth."""
    return CentralSettings.from_env()


# Backward compatibility alias
def get_central_config() -> CentralSettings:
    return get_settings()
