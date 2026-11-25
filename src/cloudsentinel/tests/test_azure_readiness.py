"""Static Azure deployment readiness checks."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_nsg_dynamic_blocks_precede_allow_rules() -> None:
    bicep = (ROOT / "infra" / "main.bicep").read_text(encoding="utf-8")
    assert "priority: 200" in bicep
    assert "priority: 210" in bicep
    assert "priority: 220" in bicep
    assert "priority: 230" in bicep
    block_logic = (ROOT / "azure" / "function" / "block_logic.py").read_text(encoding="utf-8")
    assert "BLOCK_PRIORITY_MAX = 199" in block_logic


def test_event_grid_subscription_targets_block_function() -> None:
    bicep = (ROOT / "infra" / "event-subscription.bicep").read_text(encoding="utf-8")
    assert "Microsoft.EventGrid/topics/eventSubscriptions" in bicep
    assert "CloudSentinel.BlockRequested" in bicep
    assert "block_ip" in bicep


def test_key_vault_and_blob_are_private() -> None:
    bicep = (ROOT / "infra" / "main.bicep").read_text(encoding="utf-8")
    assert "publicNetworkAccess: 'Disabled'" in bicep
    assert "allowBlobPublicAccess: false" in bicep
    assert "privatelink.vaultcore.azure.net" in bicep


def test_no_active_digitalocean_provider_or_credentials() -> None:
    for path in (ROOT / "src" / "cloudsentinel").rglob("*.py"):
        if "tests" in path.parts or path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8").lower()
        assert "digitalocean" not in text, path
        assert "cloudsentinel_do_" not in text, path


def test_deploy_script_exposes_only_caddy_and_redirects_honeypot() -> None:
    deploy = (ROOT / "src" / "cloudsentinel" / "deploy.sh").read_text(encoding="utf-8")
    assert "reverse_proxy https://127.0.0.1:8080" in deploy
    assert "reverse_proxy 127.0.0.1:3001" in deploy
    assert "REDIRECT --to-ports ${SSH_PORT}" in deploy
    assert "ufw allow 443/tcp" in deploy
