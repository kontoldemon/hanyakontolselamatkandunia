"""
DEPRECATED — All features merged into server.py.

This module is kept for reference only. The ConnectionLimiter, fuzz detection,
SOAR integration, TTY logging, and HoneyPotInteractiveProtocol have been
merged into the unified server.py entrypoint.

DO NOT IMPORT — use server.py instead.

Features merged:
  - ConnectionLimiter (sliding-window rate limiting)
  - Fuzz detection (oversized packet / null flood detection)
  - SOAR engine per-session integration
  - TTY logging (tty.log + tty.raw per session)
  - Auth attempt tracking
  - HASSH DNA botnet lookups
  - Event callback pipeline
"""

from __future__ import annotations

import warnings

warnings.warn(
    "cloudsentinel.ssh_server is deprecated. Use cloudsentinel.server instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export stubs for backward compat
from .server import ConnectionLimiter  # noqa: F401
