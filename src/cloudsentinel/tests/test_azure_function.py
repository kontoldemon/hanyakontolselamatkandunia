"""Integration test for the Azure Function control flow with fake SDKs."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FUNCTION_DIR = REPO_ROOT / "azure" / "function"
FUNCTION_PATH = FUNCTION_DIR / "function_app.py"


class FakePoller:
    def result(self) -> None:
        return None


class FakeSecurityRule:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


class FakeExistingRule:
    def __init__(self, name: str, priority: int, description: str = "") -> None:
        self.name = name
        self.priority = priority
        self.description = description


class FakeNetworkClient:
    instances: list[FakeNetworkClient] = []
    rules: list[FakeExistingRule] = []

    def __init__(self, credential: object, subscription_id: str) -> None:
        self.credential = credential
        self.subscription_id = subscription_id
        self.created: list[tuple[str, FakeSecurityRule]] = []
        self.deleted: list[str] = []
        self.security_rules = self
        FakeNetworkClient.instances.append(self)

    def list(self, _resource_group: str, _nsg_name: str) -> list[FakeExistingRule]:
        return list(FakeNetworkClient.rules)

    def begin_create_or_update(
        self,
        _resource_group: str,
        _nsg_name: str,
        name: str,
        rule: FakeSecurityRule,
    ) -> FakePoller:
        self.created.append((name, rule))
        return FakePoller()

    def begin_delete(self, _resource_group: str, _nsg_name: str, name: str) -> FakePoller:
        self.deleted.append(name)
        return FakePoller()


class FakeQueueClient:
    instances: list[FakeQueueClient] = []

    def __init__(self) -> None:
        self.messages: list[tuple[str, int | None]] = []

    @classmethod
    def from_connection_string(cls, connection: str, queue_name: str) -> FakeQueueClient:
        client = cls()
        client.connection = connection
        client.queue_name = queue_name
        cls.instances.append(client)
        return client

    def send_message(self, content: str, visibility_timeout: int | None = None) -> None:
        self.messages.append((content, visibility_timeout))


class FakeFunctionApp:
    def event_grid_trigger(self, **_kwargs: object):
        return lambda func: func

    def queue_trigger(self, **_kwargs: object):
        return lambda func: func

    def timer_trigger(self, **_kwargs: object):
        return lambda func: func


class FakeEventGridEvent:
    def __init__(self, data: dict) -> None:
        self.data = data

    def get_json(self) -> dict:
        return self.data


class FakeQueueMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def get_body(self) -> bytes:
        return self.body


class FakeTimerRequest:
    pass


class FakeCredential:
    pass


def _install_fake_modules(monkeypatch) -> None:
    azure = types.ModuleType("azure")
    azure.__path__ = []
    functions = types.ModuleType("azure.functions")
    functions.FunctionApp = FakeFunctionApp
    functions.EventGridEvent = FakeEventGridEvent
    functions.QueueMessage = FakeQueueMessage
    functions.TimerRequest = FakeTimerRequest
    identity = types.ModuleType("azure.identity")
    identity.DefaultAzureCredential = FakeCredential
    mgmt = types.ModuleType("azure.mgmt")
    mgmt.__path__ = []
    network = types.ModuleType("azure.mgmt.network")
    network.NetworkManagementClient = FakeNetworkClient
    models = types.ModuleType("azure.mgmt.network.models")
    models.SecurityRule = FakeSecurityRule
    network.models = models
    storage = types.ModuleType("azure.storage")
    storage.__path__ = []
    queue = types.ModuleType("azure.storage.queue")
    queue.QueueClient = FakeQueueClient
    storage.queue = queue
    azure.functions = functions
    azure.identity = identity
    azure.mgmt = mgmt
    mgmt.network = network
    azure.storage = storage
    for name, module in {
        "azure": azure,
        "azure.functions": functions,
        "azure.identity": identity,
        "azure.mgmt": mgmt,
        "azure.mgmt.network": network,
        "azure.mgmt.network.models": models,
        "azure.storage": storage,
        "azure.storage.queue": queue,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.syspath_prepend(str(FUNCTION_DIR))


def _load_function_app(monkeypatch):
    _install_fake_modules(monkeypatch)
    spec = importlib.util.spec_from_file_location(
        "cloudsentinel_function_app",
        FUNCTION_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _set_env(monkeypatch) -> None:
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub")
    monkeypatch.setenv("NSG_RESOURCE_GROUP", "rg")
    monkeypatch.setenv("NSG_NAME", "nsg")
    monkeypatch.setenv("AzureWebJobsStorage", "UseDevelopmentStorage=true")
    monkeypatch.setenv("UNBLOCK_QUEUE", "unblock")
    monkeypatch.setenv("CLOUDSENTINEL_ALLOWLIST", "127.0.0.0/8")


def test_block_ip_creates_rule_and_queue_message(monkeypatch) -> None:
    _set_env(monkeypatch)
    module = _load_function_app(monkeypatch)
    FakeNetworkClient.instances.clear()
    FakeQueueClient.instances.clear()
    FakeNetworkClient.rules = [FakeExistingRule("Allow-Honeypot-SSH", 100)]

    module.block_ip(FakeEventGridEvent({"ip": "8.8.8.8", "ttl": 60, "reason": "unit"}))

    client = FakeNetworkClient.instances[-1]
    assert client.created
    name, rule = client.created[0]
    assert name.startswith("cs-block-")
    assert rule.priority == 200
    assert rule.source_address_prefix == "8.8.8.8"
    assert rule.access == "Deny"
    queue = FakeQueueClient.instances[-1]
    assert queue.messages
    content, visibility = queue.messages[0]
    assert json.loads(content)["rule"] == name
    assert visibility == 60


def test_unblock_ip_deletes_rule(monkeypatch) -> None:
    _set_env(monkeypatch)
    module = _load_function_app(monkeypatch)
    FakeNetworkClient.instances.clear()
    message = FakeQueueMessage(json.dumps({"rule": "cs-block-x", "ip": "8.8.8.8"}).encode())
    module.unblock_ip(message)
    client = FakeNetworkClient.instances[-1]
    assert client.deleted == ["cs-block-x"]


def test_cleanup_expired_deletes_old_rule(monkeypatch) -> None:
    _set_env(monkeypatch)
    module = _load_function_app(monkeypatch)
    FakeNetworkClient.instances.clear()
    FakeNetworkClient.rules = [
        FakeExistingRule("Allow-Honeypot-SSH", 100),
        FakeExistingRule(
            "cs-block-old",
            200,
            "CloudSentinel block until 2020-01-01T00:00:00Z (old)",
        ),
        FakeExistingRule(
            "cs-block-future",
            201,
            "CloudSentinel block until 2999-01-01T00:00:00Z (future)",
        ),
    ]
    module.cleanup_expired(FakeTimerRequest())
    client = FakeNetworkClient.instances[-1]
    assert client.deleted == ["cs-block-old"]
