from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cloudsentinel.api import queries


def _settings(enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        clickhouse=SimpleNamespace(
            enabled=enabled,
            host="clickhouse",
            port=8123,
            username="default",
            password="secret",
            database="default",
            table="cloudsentinel_events",
        )
    )


def test_record_manual_block_writes_truth_row(monkeypatch) -> None:
    client = Mock()
    monkeypatch.setattr("clickhouse_connect.get_client", lambda **_kwargs: client)

    queries.record_manual_block(
        _settings(),
        ip="93.123.16.89",
        reason="manual-dashboard",
        action="eventgrid_published",
        mttb_ms=178.7,
        started_at=1_795_846_000.0,
    )

    table, rows = client.insert.call_args.args
    columns = client.insert.call_args.kwargs["column_names"]
    row = dict(zip(columns, rows[0], strict=True))
    assert table == "cloudsentinel_events"
    assert row["eventid"] == "cloudsentinel.block.manual"
    assert row["src_ip"] == "93.123.16.89"
    assert row["cloudsentinel_soar_action"] == "eventgrid_published"
    assert row["mttb_ms"] == pytest.approx(178.7)
    assert row["reason"] == "manual-dashboard"
    client.close.assert_called_once()


def test_record_manual_block_skips_when_clickhouse_disabled(monkeypatch) -> None:
    get_client = Mock()
    monkeypatch.setattr("clickhouse_connect.get_client", get_client)

    queries.record_manual_block(
        _settings(False),
        ip="8.8.8.8",
        reason="unit",
        action="eventgrid_published",
        mttb_ms=1.0,
        started_at=0.0,
    )

    get_client.assert_not_called()
