"""
CloudSentinel Stage 1 configuration loader.

Pydantic models validate the YAML profile, while pydantic-settings reads
runtime overrides from `.env` and real environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PACKAGE_ROOT / "configs" / "usas-production.yaml"
DEFAULT_ENV_PATH = PACKAGE_ROOT / ".env"


class HoneypotSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hostname: str = "usas-prod-srv-01"
    os_version: str = "Ubuntu 22.04 LTS"
    ssh_port: int = Field(default=2222, ge=1, le=65535)
    listen_host: str = "0.0.0.0"
    server_version: str = "SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.6"
    banner: str = "Ubuntu 22.04 LTS"
    prompt_user: str = "root"
    prompt_path: str = "~"
    http_port: int = Field(default=8080, ge=1, le=65535)
    http_enabled: bool = False
    dns_enabled: bool = False
    dns_port: int = Field(default=53, ge=1, le=65535)
    tls_cert_file: str = ""
    tls_key_file: str = ""

    @property
    def tls_enabled(self) -> bool:
        return bool(self.tls_cert_file and self.tls_key_file)


class LLMSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider: str = "mock"
    endpoint: str = ""
    model: str = "gpt-4o-mini"
    timeout_seconds: float = Field(default=8.0, gt=0)
    max_output_chars: int = Field(default=4000, ge=100, le=20000)
    api_key: SecretStr = SecretStr("")


class RedisSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str = "redis://redis:6379/0"
    stream: str = "cloudsentinel.events"
    maxlen: int = Field(default=10000, ge=100)


class NATSSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    url: str = "nats://nats:4222"
    subject: str = "cloudsentinel.events"
    stream: str = "CLOUDSENTINEL"


class KafkaSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    bootstrap_servers: str = "redpanda:9092"
    topic: str = "cloudsentinel.events"


class ClickHouseSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    host: str = "clickhouse"
    port: int = Field(default=8123, ge=1, le=65535)
    database: str = "default"
    table: str = "cloudsentinel_events"
    username: str = "default"
    password: SecretStr = SecretStr("")
    batch_size: int = Field(default=100, ge=1)
    flush_interval_seconds: float = Field(default=5.0, gt=0)


class FingerprintSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enable_hassh: bool = True
    enable_ja4s: bool = True


class ObservabilitySettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    service_name: str = "cloudsentinel"
    otlp_endpoint: str = ""
    console_exporter: bool = False


class SOARSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    risk_threshold: int = Field(default=70, ge=1, le=100)
    firewall_enabled: bool = True
    firewall_dry_run: bool = True
    firewall_path: str = "/sbin/iptables"
    block_ttl: int = Field(default=86400, ge=0)
    decay_rate: float = Field(default=1.0, ge=0)
    allowlist: list[str] = Field(default_factory=lambda: [
        "127.0.0.1",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.169.254",
    ])
    active_profile: str = "local"
    mttb_target_ms: int = Field(default=100, ge=1)




class ElasticsearchSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    url: str = ""
    index_prefix: str = "cloudsentinel"
    api_key: SecretStr = SecretStr("")


class MISPSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    url: str = ""
    api_key: SecretStr = SecretStr("")
    refresh_seconds: int = Field(default=3600, ge=60)


class AbuseIPDBSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    api_key: SecretStr = SecretStr("")


class SandboxSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    runtime: str = "docker"
    memory: str = "128m"
    cpus: str = "0.5"
    timeout_seconds: float = Field(default=30.0, gt=0)

class StreamSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = Field(default=3001, ge=1, le=65535)
    cors_origin: str = "*"
    public_read_only: bool = True


class AdminSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = Field(default=8080, ge=1, le=65535)
    token: SecretStr = SecretStr("")


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    honeypot: HoneypotSettings = Field(default_factory=HoneypotSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    nats: NATSSettings = Field(default_factory=NATSSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    clickhouse: ClickHouseSettings = Field(default_factory=ClickHouseSettings)
    fingerprinting: FingerprintSettings = Field(default_factory=FingerprintSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    soar: SOARSettings = Field(default_factory=SOARSettings)
    elasticsearch: ElasticsearchSettings = Field(default_factory=ElasticsearchSettings)
    misp: MISPSettings = Field(default_factory=MISPSettings)
    abuseipdb: AbuseIPDBSettings = Field(default_factory=AbuseIPDBSettings)
    sandbox: SandboxSettings = Field(default_factory=SandboxSettings)
    stream: StreamSettings = Field(default_factory=StreamSettings)
    admin: AdminSettings = Field(default_factory=AdminSettings)


class EnvOverrides(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(DEFAULT_ENV_PATH), extra="ignore")

    cloudsentinel_listen_host: str | None = None
    cloudsentinel_ssh_port: int | None = None
    cloudsentinel_http_enabled: bool | None = None
    cloudsentinel_http_port: int | None = None
    llm_api_key: SecretStr | None = None
    llm_provider: str | None = None
    llm_endpoint: str | None = None
    llm_model: str | None = None
    redis_url: str | None = None
    nats_enabled: bool | None = None
    nats_url: str | None = None
    kafka_enabled: bool | None = None
    kafka_bootstrap_servers: str | None = None
    clickhouse_enabled: bool | None = None
    clickhouse_host: str | None = None
    clickhouse_port: int | None = None
    clickhouse_database: str | None = None
    clickhouse_table: str | None = None
    clickhouse_username: str | None = None
    clickhouse_password: SecretStr | None = None
    otel_enabled: bool | None = None
    otel_exporter_otlp_endpoint: str | None = None
    soar_firewall_enabled: bool | None = None
    soar_firewall_dry_run: bool | None = None
    soar_risk_threshold: int | None = None
    soar_block_ttl: int | None = None
    soar_allowlist: str | None = None
    soar_active_profile: str | None = None
    soar_mttb_target_ms: int | None = None
    stream_enabled: bool | None = None
    stream_host: str | None = None
    stream_port: int | None = None
    stream_cors_origin: str | None = None
    stream_public_read_only: bool | None = None
    admin_enabled: bool | None = None
    admin_port: int | None = None
    admin_token: SecretStr | None = None


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a mapping: {path}")
    return data


def _set_if_present(target: BaseModel, option: str, value: Any) -> None:
    if value is not None:
        setattr(target, option, value)


def _split_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def load_settings(
    config_path: str | os.PathLike[str] | None = None,
    env_path: str | os.PathLike[str] | None = None,
) -> Settings:
    raw = _read_yaml(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)
    settings = Settings.model_validate(raw)
    env = EnvOverrides(_env_file=str(env_path or DEFAULT_ENV_PATH))

    _set_if_present(settings.honeypot, "listen_host", env.cloudsentinel_listen_host)
    _set_if_present(settings.honeypot, "ssh_port", env.cloudsentinel_ssh_port)
    _set_if_present(settings.honeypot, "http_enabled", env.cloudsentinel_http_enabled)
    _set_if_present(settings.honeypot, "http_port", env.cloudsentinel_http_port)
    _set_if_present(settings.llm, "api_key", env.llm_api_key)
    _set_if_present(settings.llm, "provider", env.llm_provider)
    _set_if_present(settings.llm, "endpoint", env.llm_endpoint)
    _set_if_present(settings.llm, "model", env.llm_model)
    _set_if_present(settings.redis, "url", env.redis_url)
    _set_if_present(settings.nats, "enabled", env.nats_enabled)
    _set_if_present(settings.nats, "url", env.nats_url)
    _set_if_present(settings.kafka, "enabled", env.kafka_enabled)
    _set_if_present(settings.kafka, "bootstrap_servers", env.kafka_bootstrap_servers)
    _set_if_present(settings.clickhouse, "enabled", env.clickhouse_enabled)
    _set_if_present(settings.clickhouse, "host", env.clickhouse_host)
    _set_if_present(settings.clickhouse, "port", env.clickhouse_port)
    _set_if_present(settings.clickhouse, "database", env.clickhouse_database)
    _set_if_present(settings.clickhouse, "table", env.clickhouse_table)
    _set_if_present(settings.clickhouse, "username", env.clickhouse_username)
    _set_if_present(settings.clickhouse, "password", env.clickhouse_password)
    _set_if_present(settings.observability, "enabled", env.otel_enabled)
    _set_if_present(settings.observability, "otlp_endpoint", env.otel_exporter_otlp_endpoint)
    _set_if_present(settings.soar, "firewall_enabled", env.soar_firewall_enabled)
    _set_if_present(settings.soar, "firewall_dry_run", env.soar_firewall_dry_run)
    _set_if_present(settings.soar, "risk_threshold", env.soar_risk_threshold)
    _set_if_present(settings.soar, "block_ttl", env.soar_block_ttl)
    _set_if_present(settings.soar, "allowlist", _split_csv(env.soar_allowlist))
    _set_if_present(settings.soar, "active_profile", env.soar_active_profile)
    _set_if_present(settings.soar, "mttb_target_ms", env.soar_mttb_target_ms)
    _set_if_present(settings.stream, "enabled", env.stream_enabled)
    _set_if_present(settings.stream, "host", env.stream_host)
    _set_if_present(settings.stream, "port", env.stream_port)
    _set_if_present(settings.stream, "cors_origin", env.stream_cors_origin)
    _set_if_present(settings.stream, "public_read_only", env.stream_public_read_only)
    _set_if_present(settings.admin, "enabled", env.admin_enabled)
    _set_if_present(settings.admin, "port", env.admin_port)
    _set_if_present(settings.admin, "token", env.admin_token)

    return settings


_SETTINGS_CACHE: Settings | None = None


def get_settings() -> Settings:
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is None:
        _SETTINGS_CACHE = load_settings()
    return _SETTINGS_CACHE


def secret_to_str(value: SecretStr | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return str(value)


def _section_value(section: str, option: str, fallback: Any = None) -> Any:
    target = getattr(get_settings(), section, None)
    if target is None:
        return fallback
    return getattr(target, option, fallback)


def get(section: str, option: str, fallback: str | None = None) -> str:
    value = _section_value(section, option, fallback)
    if value is None:
        raise KeyError(f"{section}.{option}")
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return str(value)


def getint(section: str, option: str, fallback: int | None = None) -> int:
    value = _section_value(section, option, fallback)
    if value is None:
        raise KeyError(f"{section}.{option}")
    return int(value)


def getfloat(section: str, option: str, fallback: float | None = None) -> float:
    value = _section_value(section, option, fallback)
    if value is None:
        raise KeyError(f"{section}.{option}")
    return float(value)


def getboolean(section: str, option: str, fallback: bool | None = None) -> bool:
    value = _section_value(section, option, fallback)
    if value is None:
        raise KeyError(f"{section}.{option}")
    return bool(value)


def has_section(section: str) -> bool:
    return hasattr(get_settings(), section)


def has_option(section: str, option: str) -> bool:
    return hasattr(getattr(get_settings(), section, object()), option)
