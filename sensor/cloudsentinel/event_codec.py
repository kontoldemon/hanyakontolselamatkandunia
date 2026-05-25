"""Fast event serialization helpers using msgspec."""

from __future__ import annotations

from typing import Any

import msgspec


def dumps_text(value: Any) -> str:
    return msgspec.json.encode(value).decode("utf-8")


def dumps_bytes(value: Any) -> bytes:
    return msgspec.json.encode(value)


def loads_text(value: str | bytes) -> Any:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return msgspec.json.decode(value)
