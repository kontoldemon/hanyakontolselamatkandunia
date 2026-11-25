"""Exposure pause/resume route."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends

from ...config import Settings


def build_exposure_router(
    settings: Settings,
    require_auth: Callable[..., Any],
    load_state: Callable[..., Any],
    persist_state: Callable[..., Any],
    provider_name: Callable[[], str],
    target_ports: Callable[[Settings], list[int]],
    firewall_paths: Callable[[Settings], list[str]],
    run_command: Callable[[list[str]], Any],
    toggle_digitalocean: Callable[[bool, Settings], Any],
    to_bool: Callable[[Any], bool],
    now_ms: Callable[[], int],
    as_int: Callable[[Any], int],
    toggle_cooldown_ms: int,
    rule_comment: str,
) -> APIRouter:
    router = APIRouter()

    @router.post("/admin/exposure", dependencies=[Depends(require_auth)])
    async def exposure(body: dict[str, Any]) -> dict[str, Any]:
        enabled = to_bool(body.get("enabled"))
        current_ms = now_ms()
        existing_exposure = await load_state()
        existing_effective_enabled = to_bool(existing_exposure.get("effective_enabled", True))
        existing_last_toggle = as_int(existing_exposure.get("last_toggle_at"))
        elapsed_since_toggle = current_ms - existing_last_toggle if existing_last_toggle > 0 else toggle_cooldown_ms
        if enabled != existing_effective_enabled and elapsed_since_toggle < toggle_cooldown_ms:
            remaining = max(0, toggle_cooldown_ms - elapsed_since_toggle)
            return {
                "ok": False,
                "error": "cooldown_active",
                "cooldownRemainingMs": remaining,
                "enabled": existing_effective_enabled,
                "paused": not existing_effective_enabled,
                "provider": str(existing_exposure.get("provider") or provider_name()),
            }
        provider = provider_name()
        if provider == "digitalocean":
            result = await toggle_digitalocean(enabled, settings)
            paused = not bool(result.get("effective_enabled", enabled))
            if result.get("ok"):
                try:
                    await persist_state(
                        provider=provider,
                        desired_enabled=enabled,
                        effective_enabled=not paused,
                        updated_at_ms=current_ms,
                        last_toggle_at_ms=current_ms,
                    )
                except Exception:
                    pass
            result["enabled"] = not paused
            result["paused"] = paused
            return result

        paths = firewall_paths(settings)
        ports = target_ports(settings)
        actions: list[dict[str, Any]] = []
        if not ports:
            return {
                "ok": False,
                "enabled": enabled,
                "paused": not enabled,
                "provider": provider,
                "error": "no exposure target ports after admin safety filter",
                "actions": actions,
            }
        for port in ports:
            last_error = ""
            applied = False
            for firewall_path in paths:
                rule = [
                    firewall_path,
                    "-C",
                    "INPUT",
                    "-p",
                    "tcp",
                    "--dport",
                    str(port),
                    "-m",
                    "comment",
                    "--comment",
                    rule_comment,
                    "-j",
                    "DROP",
                ]
                check_code, _, check_err = await run_command(rule)
                if enabled:
                    if check_code == 0:
                        delete = rule.copy()
                        delete[1] = "-D"
                        code, _, stderr = await run_command(delete)
                        if code == 0:
                            actions.append({"port": port, "action": "removed", "ok": True, "firewallPath": firewall_path})
                            applied = True
                            break
                        last_error = stderr[:200]
                        continue
                    if check_code == 1:
                        actions.append({"port": port, "action": "already_open", "ok": True, "firewallPath": firewall_path})
                        applied = True
                        break
                    last_error = check_err[:200]
                    continue
                if check_code == 0:
                    actions.append({"port": port, "action": "already_paused", "ok": True, "firewallPath": firewall_path})
                    applied = True
                    break
                if check_code != 1:
                    last_error = check_err[:200]
                    continue
                add = rule.copy()
                add[1] = "-I"
                add.insert(3, "1")
                code, _, stderr = await run_command(add)
                if code == 0:
                    actions.append({"port": port, "action": "paused", "ok": True, "firewallPath": firewall_path})
                    applied = True
                    break
                last_error = stderr[:200]
            if not applied:
                actions.append({"port": port, "action": "failed", "ok": False, "error": last_error[:200]})
        paused = not enabled
        if all(item.get("ok") for item in actions):
            try:
                await persist_state(
                    provider=provider,
                    desired_enabled=enabled,
                    effective_enabled=enabled,
                    updated_at_ms=current_ms,
                    last_toggle_at_ms=current_ms,
                )
            except Exception:
                pass
        return {
            "ok": all(item["ok"] for item in actions),
            "enabled": enabled,
            "paused": paused,
            "provider": provider,
            "actions": actions,
        }

    return router
