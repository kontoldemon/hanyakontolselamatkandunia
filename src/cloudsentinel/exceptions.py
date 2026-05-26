"""CloudSentinel custom exception hierarchy."""

from __future__ import annotations


class CloudSentinelError(Exception):
    """Base exception for all CloudSentinel errors."""
    def __init__(self, message: str = "", *, code: str = "CS000") -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


# -- Sensor Errors --

class SensorError(CloudSentinelError):
    """Base for sensor-level errors."""


class ConnectionRejectedError(SensorError):
    """Connection rejected by rate limiter or allowlist."""
    def __init__(self, ip: str, reason: str = "") -> None:
        super().__init__(f"Connection rejected: {ip} ({reason})", code="CS401")


class SessionLimitExceededError(SensorError):
    """Global or per-IP session limit reached."""
    def __init__(self, current: int, maximum: int) -> None:
        super().__init__(f"Session limit: {current}/{maximum}", code="CS402")


class FuzzDetectedError(SensorError):
    """Fuzzing or DoS pattern detected in SSH data."""
    def __init__(self, ip: str, details: str = "") -> None:
        super().__init__(f"Fuzz detected from {ip}: {details}", code="CS403")


class AuthLimitExceededError(SensorError):
    """Too many authentication attempts."""
    def __init__(self, ip: str, attempts: int) -> None:
        super().__init__(f"Auth limit exceeded for {ip}: {attempts} attempts", code="CS404")


class SessionTimeoutError(SensorError):
    """Session idle timeout reached."""
    def __init__(self, session_id: str, elapsed: float) -> None:
        super().__init__(f"Session {session_id[:12]} timed out after {elapsed:.0f}s", code="CS405")


class ProtocolViolationError(SensorError):
    """SSH protocol violation or malformed packet."""
    def __init__(self, ip: str, detail: str = "") -> None:
        super().__init__(f"Protocol violation from {ip}: {detail}", code="CS406")


# -- SOAR Errors --

class SOARError(CloudSentinelError):
    """Base for SOAR pipeline errors."""


class BlockFailedError(SOARError):
    """Firewall block command failed."""
    def __init__(self, ip: str, stderr: str = "") -> None:
        super().__init__(f"Block failed for {ip}: {stderr[:200]}", code="CS501")


class BlockTimeoutError(SOARError):
    """Firewall block command timed out."""
    def __init__(self, ip: str) -> None:
        super().__init__(f"Block timeout for {ip}", code="CS502")


class RedisUnavailableError(SOARError):
    """Redis connection lost during SOAR operation."""
    def __init__(self, detail: str = "") -> None:
        super().__init__(f"Redis unavailable: {detail}", code="CS503")


class AllowlistBlockError(SOARError):
    """Attempted to block an allowlisted IP."""
    def __init__(self, ip: str) -> None:
        super().__init__(f"Cannot block allowlisted IP: {ip}", code="CS504")


# -- Pipeline Errors --

class PipelineError(CloudSentinelError):
    """Base for event pipeline errors."""


class ClickHouseWriteError(PipelineError):
    """ClickHouse batch insert failed."""
    def __init__(self, batch_size: int, detail: str = "") -> None:
        super().__init__(f"ClickHouse write failed ({batch_size} events): {detail}", code="CS601")


class WALCorruptionError(PipelineError):
    """Write-Ahead Log is corrupted."""
    def __init__(self, path: str = "") -> None:
        super().__init__(f"WAL corrupted: {path}", code="CS602")


class KafkaPublishError(PipelineError):
    """Kafka/Redpanda publish failed."""
    def __init__(self, topic: str, detail: str = "") -> None:
        super().__init__(f"Kafka publish to {topic} failed: {detail}", code="CS603")


class NATSPublishError(PipelineError):
    """NATS JetStream publish failed."""
    def __init__(self, subject: str, detail: str = "") -> None:
        super().__init__(f"NATS publish to {subject} failed: {detail}", code="CS604")


# -- Config Errors --

class ConfigError(CloudSentinelError):
    """Configuration validation error."""
    def __init__(self, field: str, detail: str = "") -> None:
        super().__init__(f"Config [{field}]: {detail}", code="CS701")


class MissingSecretError(ConfigError):
    """Required secret not found."""
    def __init__(self, key: str) -> None:
        super().__init__(key, f"Required secret '{key}' is not set", )


# -- HASSH Errors --

class HASSHError(CloudSentinelError):
    """HASSH fingerprinting error."""


class HASSHParseError(HASSHError):
    """Failed to parse SSH algorithm negotiation for HASSH."""
    def __init__(self, detail: str = "") -> None:
        super().__init__(f"HASSH parse error: {detail}", code="CS801")


# -- Sandbox Errors --

class SandboxError(CloudSentinelError):
    """Sandbox execution error."""


class SandboxTimeoutError(SandboxError):
    """Command execution exceeded sandbox timeout."""
    def __init__(self, command: str, timeout: float) -> None:
        super().__init__(f"Sandbox timeout after {timeout}s: {command[:100]}", code="CS901")


class SandboxOOMError(SandboxError):
    """Sandbox container ran out of memory."""
    def __init__(self, limit: str) -> None:
        super().__init__(f"Sandbox OOM (limit={limit})", code="CS902")
