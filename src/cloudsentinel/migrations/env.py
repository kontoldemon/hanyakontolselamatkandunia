"""
CloudSentinel Alembic migrations environment for ClickHouse.

ClickHouse doesn't support transactional DDL, so we use a
simple versioned migration approach with raw SQL files.

Usage:
    alembic upgrade head     # Apply all pending migrations
    alembic downgrade -1     # Rollback one version
    alembic current          # Show current version
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("cloudsentinel.migrations")

# ClickHouse connection
CH_HOST = "clickhouse"
CH_PORT = 8123
CH_DATABASE = "default"
CH_USERNAME = "cloudsentinel"
CH_PASSWORD = "cloudsentinel_ch_pass"


def run_migrations() -> None:
    """Apply pending ClickHouse migrations from the versions/ directory."""
    versions_dir = Path(__file__).parent / "versions"
    if not versions_dir.is_dir():
        logger.info("No migrations directory found")
        return

    sql_files = sorted(versions_dir.glob("*.sql"))
    if not sql_files:
        logger.info("No pending migrations")
        return

    import clickhouse_connect
    client = clickhouse_connect.get_client(
        host=CH_HOST, port=CH_PORT, database=CH_DATABASE,
        username=CH_USERNAME, password=CH_PASSWORD,
    )

    # Ensure migration tracking table exists
    client.command("""
        CREATE TABLE IF NOT EXISTS _cloudsentinel_migrations (
            version String,
            applied_at DateTime DEFAULT now(),
            checksum String DEFAULT ''
        ) ENGINE = MergeTree() ORDER BY version
    """)

    # Get already-applied versions
    applied = {row[0] for row in client.query("SELECT version FROM _cloudsentinel_migrations").result_rows}

    for sql_file in sql_files:
        version = sql_file.stem
        if version in applied:
            continue

        logger.info("Applying migration: %s", version)
        sql = sql_file.read_text(encoding="utf-8")

        try:
            client.command(sql)
            client.command(
                "INSERT INTO _cloudsentinel_migrations (version) VALUES",
                [[version]],
            )
            logger.info("Migration applied: %s", version)
        except Exception as exc:
            logger.error("Migration failed %s: %s", version, exc)
            raise

    client.close()
    logger.info("Migrations complete: %d applied", len(sql_files) - len(applied))
