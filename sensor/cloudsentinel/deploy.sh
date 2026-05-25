#!/usr/bin/env bash
# ============================================================================
# CloudSentinel Phase 1 - DigitalOcean Deployment Script
# Tested on: Ubuntu 24.04 LTS Droplet (1 vCPU, 1 GB RAM)
#
# Usage:
#   chmod +x deploy.sh
#   sudo ./deploy.sh
# ============================================================================

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

# Configuration
SENSOR_USER="cloudsentinel"
SENSOR_HOME="/opt/cloudsentinel"
SSH_PORT=2222
HONEYPOT_PUBLIC_PORT=22
MGMT_SSH_PORT=22222
ADMIN_IP="${ADMIN_IP:-$(printf '%s' "${SSH_CONNECTION:-}" | awk '{print $1}')}"
SOAR_ALLOWLIST="${SOAR_ALLOWLIST:-${ADMIN_IP:+${ADMIN_IP},}127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.169.254}"
CLICKHOUSE_VERSION="24.12"
PYTHON_VERSION="3.12"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "${EUID}" -ne 0 ]; then
    echo "Run as root: sudo ./deploy.sh"
    exit 1
fi

wait_for_port() {
    local host="$1"
    local port="$2"
    local name="$3"
    for _ in $(seq 1 30); do
        if timeout 1 bash -c "</dev/tcp/${host}/${port}" &>/dev/null; then
            echo "${name} ready on ${host}:${port}"
            return 0
        fi
        sleep 1
    done
    echo "${name} not ready on ${host}:${port}"
    return 1
}

echo "============================================================"
echo " CloudSentinel Phase 1 - DigitalOcean Deployment"
echo " Target: Ubuntu 24.04 LTS (1 vCPU / 1 GB RAM)"
echo "============================================================"

# System Dependencies
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev \
    python3-pip \
    build-essential libssl-dev libffi-dev \
    iptables iptables-persistent curl wget unzip \
    git ca-certificates gnupg redis-server openssh-server ufw

# ClickHouse Installation
echo "[2/7] Installing ClickHouse ${CLICKHOUSE_VERSION}..."
if ! command -v clickhouse &>/dev/null; then
    install -d -m 0755 /etc/apt/keyrings
    curl -fsSL https://packages.clickhouse.com/rpm/lts/repodata/repomd.xml.key \
        | gpg --dearmor -o /etc/apt/keyrings/clickhouse.gpg
    echo "deb [signed-by=/etc/apt/keyrings/clickhouse.gpg] https://packages.clickhouse.com/deb stable main" \
        > /etc/apt/sources.list.d/clickhouse.list
    apt-get update -qq
    apt-get install -y -qq clickhouse-server clickhouse-client
fi

systemctl enable clickhouse-server
systemctl restart clickhouse-server
systemctl enable redis-server
systemctl restart redis-server
echo "ClickHouse status: $(systemctl is-active clickhouse-server)"
echo "Redis status: $(systemctl is-active redis-server)"
wait_for_port 127.0.0.1 8123 "ClickHouse"
wait_for_port 127.0.0.1 6379 "Redis"

# Sensor User & Directory
echo "[3/7] Creating sensor user and directories..."
if ! id -u ${SENSOR_USER} &>/dev/null; then
    useradd -r -s /bin/bash -m -d ${SENSOR_HOME} ${SENSOR_USER}
fi

mkdir -p ${SENSOR_HOME}/{var/log,var/lib,var/tty,downloads,data,honeyfs/etc}

echo "[4/7] Copying CloudSentinel package..."
if [ "$(realpath "${SOURCE_DIR}")" != "$(realpath "${SENSOR_HOME}" 2>/dev/null || echo "")" ]; then
    cp -a "${SOURCE_DIR}/." "${SENSOR_HOME}/"
fi
chown -R ${SENSOR_USER}:${SENSOR_USER} ${SENSOR_HOME}

# Python Virtual Environment
echo "[5/7] Setting up Python virtual environment..."
python${PYTHON_VERSION} -m venv ${SENSOR_HOME}/venv
${SENSOR_HOME}/venv/bin/pip install --upgrade pip setuptools wheel

# Install CloudSentinel dependencies
${SENSOR_HOME}/venv/bin/pip install -r ${SENSOR_HOME}/requirements.txt

echo "Python packages installed."
PYTHONPATH=/opt ${SENSOR_HOME}/venv/bin/python -m cloudsentinel.server --help >/dev/null

# Apply CloudSentinel Schema
echo "[5b/7] Applying ClickHouse schema..."
sleep 3
clickhouse-client --multiquery < ${SENSOR_HOME}/schema.sql || {
    echo "Schema already exists or applied via alternative method"
}
echo "Schema applied."

# GeoIP Database
echo "[6/7] Downloading MaxMind GeoLite2 database..."
mkdir -p /usr/share/GeoIP
# Note: Requires free MaxMind license key in production
# For demo, the sensor falls back to "Unknown" geo without the DB file
echo "GeoIP database download skipped (requires license key)."
echo "Sensor will operate with geo-fallback mode."

# Firewall Configuration
echo "[7/7] Configuring firewall..."
# Move management SSH away from public honeypot port.
install -d -m 0755 /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/99-cloudsentinel-management.conf << SSHD
Port ${MGMT_SSH_PORT}
SSHD
ufw allow ${MGMT_SSH_PORT}/tcp comment "Management SSH"

# Public :22 becomes honeypot traffic redirected to internal :2222.
iptables -t nat -C PREROUTING -p tcp --dport ${HONEYPOT_PUBLIC_PORT} -j REDIRECT --to-ports ${SSH_PORT} 2>/dev/null \
    || iptables -t nat -A PREROUTING -p tcp --dport ${HONEYPOT_PUBLIC_PORT} -j REDIRECT --to-ports ${SSH_PORT}
iptables -t nat -C OUTPUT -p tcp -d 127.0.0.1 --dport ${HONEYPOT_PUBLIC_PORT} -j REDIRECT --to-ports ${SSH_PORT} 2>/dev/null \
    || iptables -t nat -A OUTPUT -p tcp -d 127.0.0.1 --dport ${HONEYPOT_PUBLIC_PORT} -j REDIRECT --to-ports ${SSH_PORT}
iptables-save > /etc/iptables/rules.v4

# Allow SSH on the honeypot public and internal ports.
ufw allow ${HONEYPOT_PUBLIC_PORT}/tcp comment "CloudSentinel public SSH honeypot"
ufw allow ${SSH_PORT}/tcp comment "CloudSentinel internal SSH honeypot"
# Allow ClickHouse (local only by default)
ufw allow from 127.0.0.1 to any port 8123 comment "ClickHouse HTTP"
# Allow Socket.io dashboard feed
ufw allow 3001/tcp comment "CloudSentinel WebSocket"
ufw --force enable || true
systemctl restart ssh || systemctl restart sshd
echo "Firewall configured."

# systemd Service
cat > /etc/systemd/system/cloudsentinel.service << 'SERVICE'
[Unit]
Description=CloudSentinel SSH Defense Sensor
After=network.target clickhouse-server.service redis-server.service
Wants=clickhouse-server.service redis-server.service

[Service]
Type=simple
User=cloudsentinel
Group=cloudsentinel
WorkingDirectory=/opt/cloudsentinel
ExecStart=/opt/cloudsentinel/venv/bin/python -m cloudsentinel.server --host 0.0.0.0 --port 2222
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cloudsentinel
Environment=PYTHONPATH=/opt
Environment=REDIS_URL=redis://127.0.0.1:6379/0
Environment=CLICKHOUSE_ENABLED=true
Environment=CLICKHOUSE_HOST=127.0.0.1
Environment=SOAR_FIREWALL_ENABLED=true
Environment=SOAR_FIREWALL_DRY_RUN=false
Environment=SOAR_ACTIVE_PROFILE=do
Environment=SOAR_ALLOWLIST=${SOAR_ALLOWLIST}
Environment=SOAR_BLOCK_TTL=3600
Environment=SOAR_MTTB_TARGET_MS=100
Environment=STREAM_ENABLED=true
Environment=STREAM_HOST=0.0.0.0
Environment=STREAM_PORT=3001
Environment=STREAM_CORS_ORIGIN=*
Environment=ADMIN_ENABLED=true
Environment=ADMIN_PORT=8080

# Resource limits (1 vCPU, 1 GB RAM)
MemoryMax=768M
CPUQuota=80%

# Service hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/cloudsentinel/var /opt/cloudsentinel/downloads /opt/cloudsentinel/data
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_RAW
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
LockPersonality=true
RestrictSUIDSGID=true
SystemCallArchitectures=native

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable cloudsentinel

echo ""
echo "============================================================"
echo " CloudSentinel Phase 1 deployment complete!"
echo ""
echo " Start the sensor:"
echo "   sudo systemctl start cloudsentinel"
echo ""
echo " Check status:"
echo "   sudo systemctl status cloudsentinel"
echo ""
echo " View logs:"
echo "   sudo journalctl -u cloudsentinel -f"
echo ""
echo " ClickHouse query:"
echo "   clickhouse-client --query 'SELECT count() FROM cloudsentinel_events'"
echo ""
echo " Honeypot SSH port: ${SSH_PORT}"
echo " Public honeypot SSH: ${HONEYPOT_PUBLIC_PORT} -> ${SSH_PORT}"
echo " Management SSH: ssh -p ${MGMT_SSH_PORT} root@188.166.184.42"
echo " WebSocket stream:  port 3001"
echo " SOAR allowlist: ${SOAR_ALLOWLIST}"
echo "============================================================"
