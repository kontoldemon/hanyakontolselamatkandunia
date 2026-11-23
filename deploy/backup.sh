#!/usr/bin/env bash
# CloudSentinel backup script.
# Usage: sudo ./backup.sh [backup|restore <file>]
# Cron:  0 3 * * * root /opt/cloudsentinel/backup.sh backup
#
# BACKUP_MODE=auto|docker|native. Auto uses Docker when a Redis container is
# running, otherwise the native Redis/ClickHouse services installed by deploy.sh.
# The optional Azure Blob upload refreshes the VM managed identity first.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/cloudsentinel/backups}"
SENSOR_HOME="${SENSOR_HOME:-/opt/cloudsentinel}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="${BACKUP_DIR}/cloudsentinel_${TIMESTAMP}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
BACKUP_MODE="${BACKUP_MODE:-auto}"
ENV_FILE="${ENV_FILE:-${SENSOR_HOME}/.env}"

REDIS_CONTAINER="${REDIS_CONTAINER:-cloudsentinel-redis-plain-1}"
CLICKHOUSE_CONTAINER="${CLICKHOUSE_CONTAINER:-cloudsentinel-clickhouse-1}"
REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
REDIS_DATA_DIR="${REDIS_DATA_DIR:-/var/lib/redis}"
CLICKHOUSE_HOST="${CLICKHOUSE_HOST:-127.0.0.1}"
CLICKHOUSE_PORT="${CLICKHOUSE_PORT:-9000}"
CLICKHOUSE_DATABASE="${CLICKHOUSE_DATABASE:-default}"
CLICKHOUSE_TABLE="${CLICKHOUSE_TABLE:-cloudsentinel_events}"
CLICKHOUSE_USER="${CLICKHOUSE_USER:-default}"
CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-}"

AZURE_STORAGE_ACCOUNT="${AZURE_STORAGE_ACCOUNT:-}"
AZURE_STORAGE_CONTAINER="${AZURE_STORAGE_CONTAINER:-cloudsentinel-backups}"

if [ -f "${ENV_FILE}" ]; then
    set -a
    # shellcheck disable=SC1090
    . "${ENV_FILE}"
    set +a
fi

# The same .env serves Docker and native installs. Map Docker service names
# back to localhost for native backups.
case "${REDIS_URL}" in
    redis://redis:*|redis://redis-plain:*)
        REDIS_URL="redis://127.0.0.1:6379/0"
        ;;
esac
if [ "${CLICKHOUSE_HOST}" = "clickhouse" ]; then
    CLICKHOUSE_HOST="127.0.0.1"
fi
if [ -z "${REDIS_PASSWORD:-}" ] && [ -f /root/cloudsentinel-redis-password ]; then
    REDIS_PASSWORD="$(cat /root/cloudsentinel-redis-password)"
fi
if [ -z "${CLICKHOUSE_PASSWORD:-}" ] && [ -f /root/cloudsentinel-clickhouse-password ]; then
    CLICKHOUSE_PASSWORD="$(cat /root/cloudsentinel-clickhouse-password)"
fi

mode() {
    if [ "${BACKUP_MODE}" != "auto" ]; then
        printf '%s\n' "${BACKUP_MODE}"
        return
    fi
    if command -v docker >/dev/null 2>&1 && \
        docker ps --format '{{.Names}}' 2>/dev/null | grep -q "${REDIS_CONTAINER}"; then
        printf '%s\n' "docker"
    else
        printf '%s\n' "native"
    fi
}

backup_redis() {
    local target="$1"
    if [ "$(mode)" = "docker" ]; then
        docker exec "${REDIS_CONTAINER}" redis-cli --no-auth-warning \
            -a "${REDIS_PASSWORD:-cloudsentinel_redis}" BGSAVE
        sleep 2
        docker cp "${REDIS_CONTAINER}:/data/dump.rdb" "${target}/redis_dump.rdb"
    elif [ -n "${REDIS_PASSWORD:-}" ]; then
        REDISCLI_AUTH="${REDIS_PASSWORD}" redis-cli -u "${REDIS_URL}" --rdb "${target}/redis_dump.rdb"
    else
        redis-cli -u "${REDIS_URL}" --rdb "${target}/redis_dump.rdb"
    fi
}

backup_clickhouse() {
    local target="$1"
    if [ "$(mode)" = "docker" ]; then
        docker exec "${CLICKHOUSE_CONTAINER}" clickhouse-client \
            --user "${CLICKHOUSE_USER}" \
            --password "${CLICKHOUSE_PASSWORD:-cloudsentinel_ch_pass}" \
            --database "${CLICKHOUSE_DATABASE}" \
            --query "SELECT * FROM ${CLICKHOUSE_TABLE} FORMAT Native" \
            > "${target}/clickhouse_events.native"
        return
    fi

    local args=(
        --host "${CLICKHOUSE_HOST}"
        --port "${CLICKHOUSE_PORT}"
        --user "${CLICKHOUSE_USER}"
        --database "${CLICKHOUSE_DATABASE}"
    )
    if [ -n "${CLICKHOUSE_PASSWORD}" ]; then
        args+=(--password "${CLICKHOUSE_PASSWORD}")
    fi
    clickhouse-client "${args[@]}" \
        --query "SELECT * FROM ${CLICKHOUSE_TABLE} FORMAT Native" \
        > "${target}/clickhouse_events.native"
}

backup() {
    mkdir -p "${BACKUP_PATH}"

    echo "[1/4] Backing up Redis..."
    backup_redis "${BACKUP_PATH}"

    echo "[2/4] Backing up ClickHouse..."
    backup_clickhouse "${BACKUP_PATH}"

    echo "[3/4] Backing up TTY logs and buffers..."
    if [ -d "${SENSOR_HOME}/var/lib/cloudsentinel/tty" ]; then
        cp -r "${SENSOR_HOME}/var/lib/cloudsentinel/tty" "${BACKUP_PATH}/tty/"
    fi
    mkdir -p "${BACKUP_PATH}/buffers"
    for file in wal/events.jsonl clickhouse_spill.jsonl; do
        if [ -f "${SENSOR_HOME}/var/lib/cloudsentinel/${file}" ]; then
            cp "${SENSOR_HOME}/var/lib/cloudsentinel/${file}" "${BACKUP_PATH}/buffers/"
        fi
    done

    echo "[4/4] Compressing..."
    tar -czf "${BACKUP_PATH}.tar.gz" -C "${BACKUP_DIR}" "cloudsentinel_${TIMESTAMP}"
    chmod 600 "${BACKUP_PATH}.tar.gz"
    rm -rf "${BACKUP_PATH}"
    echo "Backup complete: ${BACKUP_PATH}.tar.gz ($(du -h "${BACKUP_PATH}.tar.gz" | cut -f1))"

    if [ -n "${AZURE_STORAGE_ACCOUNT}" ] && command -v az >/dev/null 2>&1; then
        echo "Uploading to Azure Blob Storage..."
        if ! az login --identity --only-show-errors >/dev/null 2>&1; then
            echo "Azure managed-identity login failed; skipping offsite upload." >&2
        else
            az storage blob upload \
                --account-name "${AZURE_STORAGE_ACCOUNT}" \
                --container-name "${AZURE_STORAGE_CONTAINER}" \
                --name "$(basename "${BACKUP_PATH}.tar.gz")" \
                --file "${BACKUP_PATH}.tar.gz" \
                --auth-mode login \
                --overwrite \
                --only-show-errors
        fi
    else
        echo "Offsite upload skipped (set AZURE_STORAGE_ACCOUNT and install az)."
    fi

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
    if [ "$(mode)" = "docker" ]; then
        docker cp "${TEMP_DIR}/${RESTORE_DIR}/redis_dump.rdb" "${REDIS_CONTAINER}:/data/dump.rdb"
        docker restart "${REDIS_CONTAINER}"
    else
        systemctl stop redis-server
        install -m 0640 -o redis -g redis \
            "${TEMP_DIR}/${RESTORE_DIR}/redis_dump.rdb" "${REDIS_DATA_DIR}/dump.rdb"
        systemctl start redis-server
    fi

    echo "[2/3] Restoring ClickHouse..."
    if [ "$(mode)" = "docker" ]; then
        cat "${TEMP_DIR}/${RESTORE_DIR}/clickhouse_events.native" | docker exec -i \
            "${CLICKHOUSE_CONTAINER}" clickhouse-client \
            --user "${CLICKHOUSE_USER}" \
            --password "${CLICKHOUSE_PASSWORD:-cloudsentinel_ch_pass}" \
            --database "${CLICKHOUSE_DATABASE}" \
            --query "INSERT INTO ${CLICKHOUSE_TABLE} FORMAT Native"
    else
        local args=(
            --host "${CLICKHOUSE_HOST}"
            --port "${CLICKHOUSE_PORT}"
            --user "${CLICKHOUSE_USER}"
            --database "${CLICKHOUSE_DATABASE}"
        )
        if [ -n "${CLICKHOUSE_PASSWORD}" ]; then
            args+=(--password "${CLICKHOUSE_PASSWORD}")
        fi
        cat "${TEMP_DIR}/${RESTORE_DIR}/clickhouse_events.native" | clickhouse-client "${args[@]}" \
            --query "INSERT INTO ${CLICKHOUSE_TABLE} FORMAT Native"
    fi

    echo "[3/3] Restoring TTY logs..."
    if [ -d "${TEMP_DIR}/${RESTORE_DIR}/tty" ]; then
        cp -r "${TEMP_DIR}/${RESTORE_DIR}/tty/" "${SENSOR_HOME}/var/lib/cloudsentinel/tty/"
    fi

    rm -rf "${TEMP_DIR}"
    echo "Restore complete"
}

case "${1:-backup}" in
    backup) backup ;;
    restore) restore "${2:-}" ;;
    *) echo "Usage: $0 [backup|restore <file>]" ;;
esac
