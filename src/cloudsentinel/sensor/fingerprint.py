"""SSH client finger printing and host-key helpers for the sensor."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

import asyncssh
import structlog

from ..hassh import calculate_hassh

logger = structlog.get_logger("cloudsentinel.sensor.fingerprint")


def _split_algorithms(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, bytes):
        value = value.decode("utf-8", "ignore")
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple)):
        return [str(part) for part in value if str(part)]
    return [str(value)]


def _decode_alg_list(values: Any) -> list[str]:
    items: list[str] = []
    for value in (values or []):
        if isinstance(value, bytes):
            try:
                items.append(value.decode("ascii"))
            except Exception:
                items.append(value.decode("utf-8", "ignore"))
        else:
            items.append(str(value))
    return [item for item in items if item]


def extract_hassh(conn: asyncssh.SSHServerConnection) -> tuple[str | None, str | None]:
    """Best-effort HASSH extraction from AsyncSSH connection metadata."""

    # Primary path: parse AsyncSSH's cached client KEXINIT payload.
    # This contains the real client-offered algorithm lists required by HASSH.
    try:
        raw = getattr(conn, "_client_kexinit", b"")
        if isinstance(raw, bytes) and raw:
            from asyncssh.packet import SSHPacket

            pkt = SSHPacket(raw)
            _ = pkt.get_bytes(16)  # cookie
            client_kex = _decode_alg_list(pkt.get_namelist())
            _ = pkt.get_namelist()  # host key algs
            enc_cs = _decode_alg_list(pkt.get_namelist())
            _ = pkt.get_namelist()  # enc sc
            mac_cs = _decode_alg_list(pkt.get_namelist())
            _ = pkt.get_namelist()  # mac sc
            cmp_cs = _decode_alg_list(pkt.get_namelist())
            _ = pkt.get_namelist()  # cmp sc
            if client_kex:
                return calculate_hassh(
                    client_kex,
                    enc_cs or ["unknown"],
                    mac_cs or ["unknown"],
                    cmp_cs or ["none"],
                )
    except Exception:
        pass

    lookup_names = {
        "kex": ("kex_algs", "client_kex_algs", "kex_algorithms"),
        "enc": ("enc_algs", "client_enc_algs", "encryption_algs"),
        "mac": ("mac_algs", "client_mac_algs"),
        "cmp": ("cmp_algs", "client_cmp_algs", "compression_algs"),
    }

    found: dict[str, list[str]] = {}
    for key, names in lookup_names.items():
        values: list[str] = []
        for name in names:
            try:
                values = _split_algorithms(conn.get_extra_info(name))
            except Exception:
                values = []
            if values:
                break
        found[key] = values

    if not found["kex"]:
        # Fallback: build stable fingerprint from negotiated values if client
        # algorithm lists are unavailable.
        negotiated = [
            _split_algorithms(conn.get_extra_info("recv_cipher")),
            _split_algorithms(conn.get_extra_info("recv_mac")),
            _split_algorithms(conn.get_extra_info("recv_compression")),
        ]
        if any(negotiated):
            kex_name = "unknown-kex"
            try:
                kex_obj = getattr(conn, "_kex", None)
                algorithm = getattr(kex_obj, "algorithm", b"")
                if isinstance(algorithm, bytes):
                    kex_name = algorithm.decode("ascii", "ignore") or kex_name
                elif algorithm:
                    kex_name = str(algorithm)
            except Exception:
                pass
            return calculate_hassh(
                [kex_name],
                negotiated[0] or ["unknown"],
                negotiated[1] or ["unknown"],
                negotiated[2] or ["none"],
            )
        # Last-resort deterministic surrogate so dashboard never loses identity.
        try:
            client_version = str(conn.get_extra_info("client_version", "") or "unknown-client")
            server_version = str(conn.get_extra_info("server_version", "") or "unknown-server")
            return calculate_hassh(
                [f"client:{client_version}"],
                [f"server:{server_version}"],
                ["unknown"],
                ["none"],
            )
        except Exception:
            pass
        return None, None

    return calculate_hassh(
        found["kex"],
        found["enc"] or ["unknown"],
        found["mac"] or ["unknown"],
        found["cmp"] or ["none"],
    )


def extract_ja4s(conn: asyncssh.SSHServerConnection, hassh_algorithms: str | None) -> str | None:
    """Produce a JA4S-like SSH server profile from negotiated SSH metadata."""

    try:
        import ja4plus  # noqa: F401
    except Exception:
        pass

    try:
        server_version = str(conn.get_extra_info("server_version", ""))
        cipher = str(conn.get_extra_info("send_cipher", ""))
        mac = str(conn.get_extra_info("send_mac", ""))
        compression = str(conn.get_extra_info("send_compression", "none"))
        seed = "|".join(["ssh", server_version, cipher, mac, compression, hassh_algorithms or ""])
        return "ja4s_ssh_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    except Exception as exc:
        logger.debug("JA4S extraction failed: %s", exc)
        return None


def _load_or_create_host_key_sync(path: Path) -> asyncssh.SSHKey:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return asyncssh.read_private_key(str(path))

    key = asyncssh.generate_private_key("ssh-rsa")
    private_key = key.export_private_key()
    if isinstance(private_key, str):
        private_key = private_key.encode("utf-8")
    path.write_bytes(private_key)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return key


async def load_or_create_host_key(path: Path) -> asyncssh.SSHKey:
    return await asyncio.to_thread(_load_or_create_host_key_sync, path)
