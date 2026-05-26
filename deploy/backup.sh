#!/usr/bin/env bash
# CloudSentinel Backup Script — DO Droplet daily backup
# Usage: sudo ./backup.sh [backup|restore <dir>]

set -euo pipefail
BACKUP_DIR="${BACKUP_DIR:-/opt/cloudsentinel/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="${BACKUP_DIR}/cloudsentinel_${TIMESTAMP}"
RETENTION_DAYS=7

backup() {
    mkdir -p "${BACKUP_PATH}"

    echo "[1/4] Backing up Redis..."
    docker exec cloudsentinel-redis-plain-1 redis-cli BGSAVE
    sleep 2
    docker cp cloudsentinel-redis-plain-1:/data/dump.rdb "${BACKUP_PATH}/redis_dump.rdb"

    echo "[2/4] Backing up ClickHouse..."
    docker exec cloudsentinel-clickhouse-1 clickhouse-client --query "BACKUP DATABASE default TO Disk('backups', '${TIMESTAMP}')"
    docker cp cloudsentinel-clickhouse-1:/var/lib/clickhouse/backups/"${TIMESTAMP}" "${BACKUP_PATH}/clickhouse/"

    echo "[3/4] Backing up TTY logs..."
    if [ -d /opt/cloudsentinel/var/lib/cloudsentinel/tty ]; then
        cp -r /opt/cloudsentinel/var/lib/cloudsentinel/tty "${BACKUP_PATH}/tty/"
    fi

    echo "[4/4] Compressing..."
    tar -czf "${BACKUP_PATH}.tar.gz" -C "${BACKUP_DIR}" "cloudsentinel_${TIMESTAMP}"
    rm -rf "${BACKUP_PATH}"

    echo "Backup complete: ${BACKUP_PATH}.tar.gz ($(du -h ${BACKUP_PATH}.tar.gz | cut -f1))"

    # Cleanup old backups
    find "${BACKUP_DIR}" -name "cloudsentinel_*.tar.gz" -mtime +${RETENTION_DAYS} -delete
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
    docker cp "${TEMP_DIR}/${RESTORE_DIR}/redis_dump.rdb" cloudsentinel-redis-plain-1:/data/dump.rdb
    docker restart cloudsentinel-redis-plain-1

    echo "[2/3] Restoring ClickHouse..."
    docker cp "${TEMP_DIR}/${RESTORE_DIR}/clickhouse/" cloudsentinel-clickhouse-1:/var/lib/clickhouse/backups/
    docker exec cloudsentinel-clickhouse-1 clickhouse-client --query "RESTORE DATABASE default FROM Disk('backups', '${RESTORE_DIR}')"

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
