#!/usr/bin/env bash
# Load runtime secrets from Azure Key Vault into the sensor .env file.
# Run on the sensor VM after "az login --identity" (or let this script do it).
#
# Usage:
#   sudo KEY_VAULT_NAME=<vault> ./load_secrets.sh

set -euo pipefail

: "${KEY_VAULT_NAME:?Set KEY_VAULT_NAME to the Key Vault name}"
ENV_FILE="${ENV_FILE:-/opt/cloudsentinel/.env}"
SENSOR_USER="${SENSOR_USER:-cloudsentinel}"
SECRETS="${SECRETS:-admin-token:ADMIN_TOKEN llm-api-key:LLM_API_KEY clickhouse-password:CLICKHOUSE_PASSWORD auth-secret:CLOUDSENTINEL_AUTH_SECRET admin-pass:CLOUDSENTINEL_ADMIN_PASS eventgrid-topic-endpoint:EVENTGRID_TOPIC_ENDPOINT eventgrid-topic-key:EVENTGRID_TOPIC_KEY storage-account-name:AZURE_STORAGE_ACCOUNT backup-container-name:AZURE_STORAGE_CONTAINER}"

if ! command -v az >/dev/null 2>&1; then
    echo "Azure CLI (az) is required." >&2
    exit 1
fi

az account show >/dev/null 2>&1 || az login --identity --only-show-errors >/dev/null

umask 077
touch "${ENV_FILE}"
chmod 600 "${ENV_FILE}"
chown "${SENSOR_USER}:${SENSOR_USER}" "${ENV_FILE}"

for pair in ${SECRETS}; do
    name="${pair%%:*}"
    env_name="${pair#*:}"
    value=$(az keyvault secret show \
        --vault-name "${KEY_VAULT_NAME}" \
        --name "${name}" \
        --query value \
        -o tsv 2>/dev/null || true)
    if [ -z "${value}" ]; then
        continue
    fi
    if grep -q "^${env_name}=" "${ENV_FILE}"; then
        sed -i "s|^${env_name}=.*|${env_name}=${value}|" "${ENV_FILE}"
    else
        printf '%s=%s\n' "${env_name}" "${value}" >> "${ENV_FILE}"
    fi
done

if grep -q '^EVENTGRID_TOPIC_ENDPOINT=.' "${ENV_FILE}" && \
    grep -q '^EVENTGRID_TOPIC_KEY=.' "${ENV_FILE}"; then
    if grep -q '^EVENTGRID_ENABLED=' "${ENV_FILE}"; then
        sed -i 's|^EVENTGRID_ENABLED=.*|EVENTGRID_ENABLED=true|' "${ENV_FILE}"
    else
        printf 'EVENTGRID_ENABLED=true\n' >> "${ENV_FILE}"
    fi
fi

chmod 600 "${ENV_FILE}"
chown "${SENSOR_USER}:${SENSOR_USER}" "${ENV_FILE}"
echo "Secrets loaded into ${ENV_FILE}"
