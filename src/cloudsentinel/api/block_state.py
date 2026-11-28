"""Live block-state helpers shared by the admin API routers."""

from __future__ import annotations

import structlog

logger = structlog.get_logger("cloudsentinel.api.block_state")


async def count_active_blocks(redis_url: str, fallback: int) -> int:
    """Count live TTL block keys in Redis, falling back to in-process state."""
    import redis.asyncio as aioredis

    client = None
    try:
        client = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
        return len([key async for key in client.scan_iter(match="soar:block:*")])
    except Exception as exc:
        logger.warning("redis_block_scan_failed", error=str(exc))
        return fallback
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass
