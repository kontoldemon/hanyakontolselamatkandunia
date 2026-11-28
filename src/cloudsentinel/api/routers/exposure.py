"""Exposure pause/resume route and shared firewall toggle logic."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends

from ...config import Settings


async def apply_exposure_toggle(
    settings: Settings,
    enabled: bool,
    *,
    load_state: Callable[..., Any],
    persist_state: Callable[..., Any],
    provider_name: Callable[[], str],
    target_ports: Callable[[Settings], list[int]],
    target_udp_ports: Callable[[Settings], list[int]] | None = None,
    firewall_paths: Callable[[Settings], list[str]],
    run_command: Callable[[list[str]], Any],
    to_bool: Callable[[Any], bool],
    now_ms: Callable[[], int],
    as_int: Callable[[Any], int],
    toggle_cooldown_ms: int,
    rule_comment: str,
) -> dict[str, Any]:
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

    paths = firewall_paths(settings)
    ports = target_ports(settings)
    udp_ports = target_udp_ports(settings) if target_udp_ports else []
    targets = [(port, "tcp") for port in ports] + [(port, "udp") for port in udp_ports]
    actions: list[dict[str, Any]] = []
    if not targets:
        return {
            "ok": False,
            "enabled": enabled,
            "paused": not enabled,
            "provider": provider,
            "error": "no exposure target ports after admin safety filter",
            "actions": actions,
        }
    for port, protocol in targets:
        last_error = ""
        applied = False
        not_found_anywhere = True
        for firewall_path in paths:
            rule = [
                firewall_path,
                "-C",
                "INPUT",
                "-p",
                protocol,
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
                        actions.append({"port": port, "protocol": protocol, "action": "removed", "ok": True, "firewallPath": firewall_path})
                        applied = True
                        break
                    not_found_anywhere = False
                    last_error = stderr[:200]
                    continue
                if check_code == 1:
                    continue
                not_found_anywhere = False
                last_error = check_err[:200]
                continue
            if check_code == 0:
                actions.append({"port": port, "protocol": protocol, "action": "already_paused", "ok": True, "firewallPath": firewall_path})
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
                actions.append({"port": port, "protocol": protocol, "action": "paused", "ok": True, "firewallPath": firewall_path})
                applied = True
                break
            last_error = stderr[:200]
        if not applied and enabled and not_found_anywhere:
            actions.append({"port": port, "protocol": protocol, "action": "already_open", "ok": True, "firewallPath": paths[0]})
            applied = True
        if not applied:
            actions.append({"port": port, "protocol": protocol, "action": "failed", "ok": False, "error": last_error[:200]})
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


def build_exposure_router(
    settings: Settings,
    require_auth: Callable[..., Any],
    load_state: Callable[..., Any],
    persist_state: Callable[..., Any],
    provider_name: Callable[[], str],
    target_ports: Callable[[Settings], list[int]],
    firewall_paths: Callable[[Settings], list[str]],
    run_command: Callable[[list[str]], Any],
    to_bool: Callable[[Any], bool],
    now_ms: Callable[[], int],
    as_int: Callable[[Any], int],
    toggle_cooldown_ms: int,
    rule_comment: str,
    target_udp_ports: Callable[[Settings], list[int]] | None = None,
) -> APIRouter:
    router = APIRouter()

    @router.post("/admin/exposure", dependencies=[Depends(require_auth)])
    async def exposure(body: dict[str, Any]) -> dict[str, Any]:
        return await apply_exposure_toggle(
            settings,
            to_bool(body.get("enabled")),
            load_state=load_state,
            persist_state=persist_state,
            provider_name=provider_name,
            target_ports=target_ports,
            target_udp_ports=target_udp_ports,
            firewall_paths=firewall_paths,
            run_command=run_command,
            to_bool=to_bool,
            now_ms=now_ms,
            as_int=as_int,
            toggle_cooldown_ms=toggle_cooldown_ms,
            rule_comment=rule_comment,
        )

    return router
