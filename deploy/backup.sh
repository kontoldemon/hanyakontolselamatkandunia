#!/usr/bin/env bash
# CloudSentinel backup script.
# Usage: sudo ./backup.sh [backup|restore <file>]
# Cron:  0 3 * * * cd /opt/cloudsentinel && ./deploy/backup.sh backup
#
# Container names and credentials can be overridden with environment variables.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/cloudsentinel/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="${BACKUP_DIR}/cloudsentinel_${TIMESTAMP}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
REDIS_CONTAINER="${REDIS_CONTAINER:-cloudsentinel-redis-plain-1}"
CLICKHOUSE_CONTAINER="${CLICKHOUSE_CONTAINER:-cloudsentinel-clickhouse-1}"
ENV_FILE="${ENV_FILE:-/opt/cloudsentinel/.env}"

if [ -f "${ENV_FILE}" ]; then
    set -a
    # shellcheck disable=SC1090
    . "${ENV_FILE}"
    set +a
fi

REDIS_PASSWORD="${REDIS_PASSWORD:-cloudsentinel_redis}"
CLICKHOUSE_USER="${CLICKHOUSE_USER:-cloudsentinel}"
CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-cloudsentinel_ch_pass}"
CLICKHOUSE_TABLE="${CLICKHOUSE_TABLE:-cloudsentinel_events}"

backup() {
    mkdir -p "${BACKUP_PATH}"

    echo "[1/4] Backing up Redis..."
    docker exec "${REDIS_CONTAINER}" redis-cli --no-auth-warning -a "${REDIS_PASSWORD}" BGSAVE
    sleep 2
    docker cp "${REDIS_CONTAINER}:/data/dump.rdb" "${BACKUP_PATH}/redis_dump.rdb"

    echo "[2/4] Backing up ClickHouse..."
    docker exec "${CLICKHOUSE_CONTAINER}" clickhouse-client \
        --user "${CLICKHOUSE_USER}" \
        --password "${CLICKHOUSE_PASSWORD}" \
        --query "SELECT * FROM ${CLICKHOUSE_TABLE} FORMAT Native" \
        > "${BACKUP_PATH}/clickhouse_events.native"

    echo "[3/4] Backing up TTY logs and buffers..."
    if [ -d /opt/cloudsentinel/var/lib/cloudsentinel/tty ]; then
        cp -r /opt/cloudsentinel/var/lib/cloudsentinel/tty "${BACKUP_PATH}/tty/"
    fi
    mkdir -p "${BACKUP_PATH}/buffers"
    if [ -f /opt/cloudsentinel/var/lib/cloudsentinel/wal/events.jsonl ]; then
        cp /opt/cloudsentinel/var/lib/cloudsentinel/wal/events.jsonl "${BACKUP_PATH}/buffers/"
    fi
    if [ -f /opt/cloudsentinel/var/lib/cloudsentinel/clickhouse_spill.jsonl ]; then
        cp /opt/cloudsentinel/var/lib/cloudsentinel/clickhouse_spill.jsonl "${BACKUP_PATH}/buffers/"
    fi

    echo "[4/4] Compressing..."
    tar -czf "${BACKUP_PATH}.tar.gz" -C "${BACKUP_DIR}" "cloudsentinel_${TIMESTAMP}"
    rm -rf "${BACKUP_PATH}"

    echo "Backup complete: ${BACKUP_PATH}.tar.gz ($(du -h "${BACKUP_PATH}.tar.gz" | cut -f1))"

    find "${BACKUP_DIR}" -name "cloudsentinel_*.tar.gz" -mtime +"${RETENTION_DAYS}" -delete
    echo "Cleaned backups older than ${RETENTION_DAYS} days"
}

restore() {
    RESTORE_PATH="$1"
    if [ ! -f "${RESTORE_PATH}" ]; then
        echo "Backup file not found: ${RESTORE_PATH}"
        exit 1
    fi

    echo "Restoring from: ${RESTORE_PATH}"
    TEMP_DIR=$(mktemp -d)
    tar -xzf "${RESTORE_PATH}" -C "${TEMP_DIR}"
    RESTORE_DIR=$(ls "${TEMP_DIR}")

    echo "[1/3] Restoring Redis..."
    docker cp "${TEMP_DIR}/${RESTORE_DIR}/redis_dump.rdb" "${REDIS_CONTAINER}:/data/dump.rdb"
    docker restart "${REDIS_CONTAINER}"

    echo "[2/3] Restoring ClickHouse..."
    cat "${TEMP_DIR}/${RESTORE_DIR}/clickhouse_events.native" | docker exec -i "${CLICKHOUSE_CONTAINER}" \
        clickhouse-client \
        --user "${CLICKHOUSE_USER}" \
        --password "${CLICKHOUSE_PASSWORD}" \
        --query "INSERT INTO ${CLICKHOUSE_TABLE} FORMAT Native"

    echo "[3/3] Restoring TTY logs..."
    if [ -d "${TEMP_DIR}/${RESTORE_DIR}/tty" ]; then
        cp -r "${TEMP_DIR}/${RESTORE_DIR}/tty/" /opt/cloudsentinel/var/lib/cloudsentinel/tty/
    fi

    rm -rf "${TEMP_DIR}"
    echo "Restore complete"
}

case "${1:-backup}" in
    backup) backup ;;
    restore) restore "${2:-}" ;;
    *) echo "Usage: $0 [backup|restore <file>]" ;;
esac
