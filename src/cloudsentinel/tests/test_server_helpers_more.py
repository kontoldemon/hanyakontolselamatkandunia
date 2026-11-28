"""Cover server helper parsing and connection limiter branches."""

from __future__ import annotations

import asyncio
import types

from cloudsentinel.server import (
    ConnectionLimiter,
    _decode_alg_list,
    _split_algorithms,
    extract_hassh,
)


def test_server_helpers() -> None:
    assert _split_algorithms(None) == []
    assert _split_algorithms(b"a,b") == ["a", "b"]
    assert _split_algorithms("a, b") == ["a", "b"]
    assert _split_algorithms(["a", 1]) == ["a", "1"]
    assert _split_algorithms(3) == ["3"]
    assert _decode_alg_list([b"aes", b"\xff", "hmac"]) == ["aes", "hmac"]

    limiter = ConnectionLimiter(max_total=2)
    assert limiter.acquire_nowait("8.8.8.8") is True
    limiter.release_nowait("8.8.8.8")
    assert limiter.total == 0

    class FakeConn:
        _kex = types.SimpleNamespace(algorithm=b"curve25519-sha256")

        def get_extra_info(self, name: str, default: object = None) -> object:
            values = {
                "recv_cipher": "aes128-ctr",
                "recv_mac": "hmac-sha2-256",
                "recv_compression": "none",
                "client_version": "SSH-2.0-unit",
                "server_version": "SSH-2.0-server",
            }
            return values.get(name, default)

    hassh, algorithms = extract_hassh(FakeConn())
    assert hassh
    assert "unknown-kex" not in algorithms

class FallbackConn:
    _kex = types.SimpleNamespace(algorithm=b"curve25519-sha256")

    def get_extra_info(self, name: str, default: object = None) -> object:
        if name in {"kex_algs", "client_kex_algs", "kex_algorithms"}:
            raise RuntimeError("missing kex")
        values = {
            "recv_cipher": "aes128-ctr",
            "recv_mac": "hmac-sha2-256",
            "recv_compression": "none",
        }
        return values.get(name, default)


def test_hassh_fallback_branches() -> None:
    hassh, algorithms = extract_hassh(FallbackConn())
    assert hassh
    assert "curve25519-sha256" in algorithms
    class LastResortConn:
        def get_extra_info(self, name: str, default: object = None) -> object:
            values = {"client_version": "SSH-2.0-client", "server_version": "SSH-2.0-server"}
            return values.get(name, default)

    hassh, algorithms = extract_hassh(LastResortConn())
    assert hassh
    assert "client:SSH-2.0-client" in algorithms

    class StringKexConn(FallbackConn):
        _kex = types.SimpleNamespace(algorithm="string-kex")

    hassh, algorithms = extract_hassh(StringKexConn())
    assert "string-kex" in algorithms


def test_extract_hassh_parses_client_kexinit() -> None:
    from cloudsentinel.hassh import calculate_hassh

    def namelist(value: str) -> bytes:
        data = value.encode()
        return len(data).to_bytes(4, 'big') + data

    raw = (
        b'\x14'
        + b'c' * 16
        + namelist('curve25519-sha256')
        + namelist('ssh-ed25519')
        + namelist('aes128-ctr')
        + namelist('aes128-ctr')
        + namelist('hmac-sha2-256')
        + namelist('hmac-sha2-256')
        + namelist('none')
        + namelist('none')
        + namelist('')
        + namelist('')
        + b'\x00'
        + b'\x00' * 4
    )

    class Conn:
        _client_kexinit = raw

        def get_extra_info(self, _name: str, default: object = None) -> object:
            return default

    hassh, algorithms = extract_hassh(Conn())  # type: ignore[arg-type]
    expected, _ = calculate_hassh(
        ['curve25519-sha256'],
        ['aes128-ctr'],
        ['hmac-sha2-256'],
        ['none'],
    )
    assert hassh == expected
    assert algorithms.startswith('curve25519-sha256;aes128-ctr;hmac-sha2-256;none')


def test_extract_hassh_ignores_malformed_kexinit() -> None:
    class Conn:
        _client_kexinit = b'\x14' + b'c' * 16 + b'\xff\xff\xff\xff'

        def get_extra_info(self, _name: str, default: object = None) -> object:
            return default

    hassh, algorithms = extract_hassh(Conn())  # type: ignore[arg-type]
    assert hassh is not None
    assert algorithms.startswith("client:")
