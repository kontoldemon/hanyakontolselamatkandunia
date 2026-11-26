"""Connection rate limiting for the SSH sensor."""

from __future__ import annotations

import time
from collections import defaultdict


class ConnectionLimiter:
    """Sliding-window rate limiter: per-IP and global caps."""

    def __init__(
        self,
        max_per_ip: int = 30,
        max_total: int = 500,
        window: float = 60.0,
        max_entries: int = 10000,
    ) -> None:
        self.max_per_ip = max_per_ip
        self.max_total = max_total
        self.window = window
        self.max_entries = max(1, max_entries)
        self._ips: defaultdict[str, list[float]] = defaultdict(list)
        self._total = 0

    def acquire_nowait(self, ip: str) -> bool:
        now = time.monotonic()
        self._ips[ip] = [t for t in self._ips[ip] if now - t < self.window]
        if len(self._ips[ip]) >= self.max_per_ip or self._total >= self.max_total:
            return False
        self._ips[ip].append(now)
        self._total += 1
        if len(self._ips) > self.max_entries:
            keep = sorted(
                self._ips.items(),
                key=lambda item: item[1][-1] if item[1] else 0.0,
                reverse=True,
            )[: self.max_entries]
            self._ips = defaultdict(list, keep)
        return True

    def release_nowait(self, ip: str) -> None:
        self._total = max(0, self._total - 1)

    @property
    def total(self) -> int:
        return self._total
