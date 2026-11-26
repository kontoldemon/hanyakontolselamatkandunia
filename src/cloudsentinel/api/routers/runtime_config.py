"""Runtime configuration routes shared by the dashboard settings page."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ...runtime_config import RuntimeConfigStore
from ...vfs import VirtualFileSystem

DECOY_META: dict[str, tuple[str, str, bool]] = {
    "/root/.aws/credentials": ("AWS IAM Canary", "API Credential", True),
    "/root/usas_backup_credentials.txt": ("Backup Credentials", "Honeytoken", True),
    "/root/.ssh/id_rsa": ("SSH Private Key", "RSA Key", False),
    "/var/www/html/config.php": ("App Database Config", "Connection String", False),
    "/root/.mysql_history": ("MySQL History", "Command Trace", False),
    "/root/backup.sh": ("Backup Script", "Script", False),
    "/tmp/.hidden_miner_config": ("Crypto Miner Config", "Honeytoken", False),
    "/etc/shadow": ("Shadow Password File", "Password Hash", False),
}


def build_runtime_config_router(
    require_auth: Callable[..., Any],
    store: RuntimeConfigStore,
) -> APIRouter:
    router = APIRouter()

    @router.get("/runtime-config", dependencies=[Depends(require_auth)])
    async def get_runtime_config() -> dict[str, Any]:
        return {"ok": True, "config": store.snapshot()}

    @router.post("/runtime-config", dependencies=[Depends(require_auth)])
    async def update_runtime_config(body: dict[str, Any]) -> dict[str, Any]:
        try:
            config = store.update(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "config": config}

    @router.get("/decoys", dependencies=[Depends(require_auth)])
    async def list_decoys() -> dict[str, Any]:
        deception = store.settings.deception
        vfs = VirtualFileSystem.for_deception(deception.level, deception.seed_canary_keys)
        decoys = []
        for path, (label, kind, canary) in DECOY_META.items():
            entry = vfs.stat(path)
            if entry is None or entry.get("type") != "file":
                continue
            decoys.append({
                "path": path,
                "label": label,
                "type": kind,
                "canary": canary,
                "size_bytes": int(entry.get("size") or 0),
            })
        return {
            "ok": True,
            "count": len(decoys),
            "decoys": decoys,
            "deception_level": deception.level,
            "seed_canary_keys": deception.seed_canary_keys,
        }

    return router
