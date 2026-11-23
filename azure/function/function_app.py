"""Azure Function: create and remove CloudSentinel NSG block rules."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import SecurityRule
from azure.storage.queue import QueueClient

from block_logic import choose_priority, rule_name, validate_request

app = func.FunctionApp()

UNBLOCK_QUEUE = os.environ.get("UNBLOCK_QUEUE", "cloudsentinel-unblock")


def _network_client() -> NetworkManagementClient:
    return NetworkManagementClient(
        DefaultAzureCredential(),
        os.environ["AZURE_SUBSCRIPTION_ID"],
    )


def _queue_client() -> QueueClient:
    return QueueClient.from_connection_string(
        os.environ["AzureWebJobsStorage"],
        queue_name=UNBLOCK_QUEUE,
    )


def _create_block(ip: str, ttl: int, reason: str) -> str:
    client = _network_client()
    resource_group = os.environ["NSG_RESOURCE_GROUP"]
    nsg_name = os.environ["NSG_NAME"]
    name = rule_name(ip)
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl)
    used = {
        int(rule.priority)
        for rule in client.security_rules.list(resource_group, nsg_name)
        if rule.priority is not None
    }
    rule = SecurityRule(
        priority=choose_priority(used),
        direction="Inbound",
        access="Deny",
        protocol="*",
        source_address_prefix=ip,
        source_port_range="*",
        destination_address_prefix="*",
        destination_port_range="*",
        description=f"CloudSentinel block until {expires_at:%Y-%m-%dT%H:%M:%SZ} ({reason[:60]})",
    )
    client.security_rules.begin_create_or_update(
        resource_group,
        nsg_name,
        name,
        rule,
    ).result()

    _queue_client().send_message(
        json.dumps({"rule": name, "ip": ip}),
        visibility_timeout=ttl,
    )
    logging.info("Created NSG rule %s for %s until %s", name, ip, expires_at.isoformat())
    return name


@app.event_grid_trigger(arg_name="event")
def block_ip(event: func.EventGridEvent) -> None:
    data = event.get_json()
    ip, ttl, reason = validate_request(
        data,
        os.environ.get("CLOUDSENTINEL_ALLOWLIST", ""),
    )
    _create_block(ip, ttl, reason)


@app.queue_trigger(
    arg_name="msg",
    queue_name=UNBLOCK_QUEUE,
    connection="AzureWebJobsStorage",
)
def unblock_ip(msg: func.QueueMessage) -> None:
    data = json.loads(msg.get_body().decode("utf-8"))
    name = str(data["rule"])
    client = _network_client()
    resource_group = os.environ["NSG_RESOURCE_GROUP"]
    nsg_name = os.environ["NSG_NAME"]
    try:
        client.security_rules.begin_delete(resource_group, nsg_name, name).result()
        logging.info("Deleted NSG rule %s", name)
    except Exception as exc:
        logging.warning("NSG rule delete failed for %s: %s", name, exc)
