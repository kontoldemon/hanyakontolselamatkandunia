"""TTY transcript persistence and fuzz detection."""

from __future__ import annotations

import time
from pathlib import Path

import structlog

logger = structlog.get_logger("cloudsentinel.sensor.tty")


class TTYLogger:
    """Persist full TTY session transcripts to disk (async I/O via aiofiles)."""

    def __init__(self, session_id: str, max_log_bytes: int = 1_000_000) -> None:
        self.session_id = session_id
        self._dir: Path | None = None
        self._log: list[tuple[float, bytes]] = []
        self._log_bytes = 0
        self.max_log_bytes = max(1, max_log_bytes)
        try:
            self._dir = Path(f"var/lib/cloudsentinel/tty/{session_id}")
            self._dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            self._dir = None

    def record(self, data: bytes) -> None:
        data = bytes(data)
        self._log.append((time.time(), data))
        self._log_bytes += len(data)
        while self._log and self._log_bytes > self.max_log_bytes:
            _, old = self._log.pop(0)
            self._log_bytes -= len(old)

    async def save_async(self) -> None:
        """Save TTY logs using async I/O (non-blocking on event loop)."""
        if not self._dir:
            return
        try:
            import aiofiles
            async with aiofiles.open(self._dir / "tty.log", "wb") as fh:
                for ts, data in self._log:
                    await fh.write(f"[{ts:.3f}] ".encode() + data + b"\n")
            async with aiofiles.open(self._dir / "tty.raw", "wb") as fh:
                for _, data in self._log:
                    await fh.write(data)
        except ImportError:
            # Fallback to sync I/O if aiofiles not installed
            logger.debug("aiofiles not available, using sync fallback")
            try:
                with open(self._dir / "tty.log", "wb") as fh:
                    for ts, data in self._log:
                        fh.write(f"[{ts:.3f}] ".encode() + data + b"\n")
                with open(self._dir / "tty.raw", "wb") as fh:
                    for _, data in self._log:
                        fh.write(data)
            except Exception as exc:
                logger.debug("TTY save failed: %s", exc)
        except Exception as exc:
            logger.debug("TTY save failed: %s", exc)

    def save(self) -> None:
        """Synchronous save wrapper (called from connection_lost)."""
        if not self._dir:
            return
        import asyncio as _asyncio
        try:
            loop = _asyncio.get_running_loop()
            loop.create_task(self.save_async())
        except RuntimeError:
            # No running loop, use sync fallback
            try:
                with open(self._dir / "tty.log", "wb") as fh:
                    for ts, data in self._log:
                        fh.write(f"[{ts:.3f}] ".encode() + data + b"\n")
                with open(self._dir / "tty.raw", "wb") as fh:
                    for _, data in self._log:
                        fh.write(data)
            except Exception as exc:
                logger.debug("TTY save failed: %s", exc)


def detect_fuzz(data: bytes, src_ip: str) -> bool:
    """Heuristic fuzz/DoS detection for SSH data streams."""
    if len(data) > 65536:
        logger.warning("Fuzz: oversized packet %db from %s", len(data), src_ip)
        return True
    if b"\x00" * 100 in data:
        logger.warning("Fuzz: null flood from %s", src_ip)
        return True
    return False
