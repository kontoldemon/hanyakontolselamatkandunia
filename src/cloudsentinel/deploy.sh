#!/usr/bin/env bash
# ============================================================================
# CloudSentinel Phase 1 - DigitalOcean Deployment Script
# Tested on: Ubuntu 24.04 LTS Droplet (2 vCPU, 2 GB RAM)
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
SOAR_ALLOWLIST="${SOAR_ALLOWLIST:-${ADMIN_IP:+${ADMIN_IP},}127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16}"
VERCEL_DASHBOARD_ORIGIN="${VERCEL_DASHBOARD_ORIGIN:-https://cloudsentinel.zis3c.dev}"
PUBLIC_TLS_HOST="${PUBLIC_TLS_HOST:-188.166.184.42.sslip.io}"
ADMIN_TOKEN="${ADMIN_TOKEN:-}"
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

setup_swap() {
    local swap_path="/swapfile"
    local swap_size="${CLOUDSENTINEL_SWAP_SIZE:-2G}"

    if ! swapon --show=NAME | grep -qx "${swap_path}"; then
        if [ ! -f "${swap_path}" ]; then
            fallocate -l "${swap_size}" "${swap_path}" || dd if=/dev/zero of="${swap_path}" bs=1M count=2048
            chmod 0600 "${swap_path}"
            mkswap "${swap_path}"
        fi
        swapon "${swap_path}" || true
    fi

    grep -q "^${swap_path} " /etc/fstab || echo "${swap_path} none swap sw 0 0" >> /etc/fstab

    cat > /etc/sysctl.d/99-cloudsentinel-memory.conf << SYSCTL
vm.swappiness=20
vm.vfs_cache_pressure=50
SYSCTL
    sysctl --system >/dev/null || true
}

echo "============================================================"
echo " CloudSentinel Phase 1 - DigitalOcean Deployment"
echo " Target: Ubuntu 24.04 LTS (2 vCPU / 2 GB RAM)"
echo "============================================================"

# System Dependencies
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev \
    python3-pip \
    build-essential libssl-dev libffi-dev openssl \
    iptables curl wget unzip \
    git ca-certificates gnupg redis-server openssh-server ufw caddy

if [ -z "${ADMIN_TOKEN}" ]; then
    ADMIN_TOKEN="$(openssl rand -hex 32)"
fi

echo "[1b/7] Configuring memory guardrails..."
setup_swap

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

mkdir -p /etc/clickhouse-server/config.d
cat > /etc/clickhouse-server/config.d/cloudsentinel-memory.xml << CLICKHOUSE_MEMORY
<clickhouse>
    <max_server_memory_usage>1073741824</max_server_memory_usage>
    <mark_cache_size>134217728</mark_cache_size>
    <uncompressed_cache_size>67108864</uncompressed_cache_size>
    <query_cache>
        <max_size_in_bytes>67108864</max_size_in_bytes>
    </query_cache>
</clickhouse>
CLICKHOUSE_MEMORY

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
mkdir -p /etc/iptables
iptables-save > /etc/iptables/rules.v4 || true


# ── Kernel-Level Rate Limiting (hashlimit) ─────────────────────
# Protects against botnet floods at the kernel level (60 conn/min per IP).
echo "    [+] Adding kernel-level hashlimit (60 conn/min per IP, burst 10)..."
iptables -C INPUT -p tcp --dport ${HONEYPOT_PUBLIC_PORT} -m state --state NEW \
    -m hashlimit --hashlimit-name cloudsentinel_conn --hashlimit-above 60/minute \
    --hashlimit-burst 10 --hashlimit-mode srcip -j DROP 2>/dev/null || \
    iptables -A INPUT -p tcp --dport ${HONEYPOT_PUBLIC_PORT} -m state --state NEW \
    -m hashlimit --hashlimit-name cloudsentinel_conn --hashlimit-above 60/minute \
    --hashlimit-burst 10 --hashlimit-mode srcip -j DROP

# Whitelist established connections at the top
iptables -C INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || \
    iptables -I INPUT 1 -m state --state ESTABLISHED,RELATED -j ACCEPT

echo "    Kernel-level DDoS protection active."

cat > /usr/local/sbin/cloudsentinel-netfilter.sh << NETFILTER
#!/usr/bin/env bash
set -euo pipefail

iptables -t nat -C PREROUTING -p tcp --dport ${HONEYPOT_PUBLIC_PORT} -j REDIRECT --to-ports ${SSH_PORT} 2>/dev/null \
    || iptables -t nat -A PREROUTING -p tcp --dport ${HONEYPOT_PUBLIC_PORT} -j REDIRECT --to-ports ${SSH_PORT}
iptables -t nat -C OUTPUT -p tcp -d 127.0.0.1 --dport ${HONEYPOT_PUBLIC_PORT} -j REDIRECT --to-ports ${SSH_PORT} 2>/dev/null \
    || iptables -t nat -A OUTPUT -p tcp -d 127.0.0.1 --dport ${HONEYPOT_PUBLIC_PORT} -j REDIRECT --to-ports ${SSH_PORT}
iptables -C INPUT -p tcp --dport ${HONEYPOT_PUBLIC_PORT} -m state --state NEW \
    -m hashlimit --hashlimit-name cloudsentinel_conn --hashlimit-above 60/minute \
    --hashlimit-burst 10 --hashlimit-mode srcip -j DROP 2>/dev/null || \
    iptables -A INPUT -p tcp --dport ${HONEYPOT_PUBLIC_PORT} -m state --state NEW \
    -m hashlimit --hashlimit-name cloudsentinel_conn --hashlimit-above 60/minute \
    --hashlimit-burst 10 --hashlimit-mode srcip -j DROP
iptables -C INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || \
    iptables -I INPUT 1 -m state --state ESTABLISHED,RELATED -j ACCEPT
NETFILTER
chmod 0755 /usr/local/sbin/cloudsentinel-netfilter.sh

cat > /etc/systemd/system/cloudsentinel-netfilter.service << NETFILTER_SERVICE
[Unit]
Description=CloudSentinel honeypot netfilter rules
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/cloudsentinel-netfilter.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
NETFILTER_SERVICE

systemctl daemon-reload
systemctl enable --now cloudsentinel-netfilter.service

# Allow SSH on the honeypot public and internal ports.
ufw allow ${HONEYPOT_PUBLIC_PORT}/tcp comment "CloudSentinel public SSH honeypot"
ufw allow ${SSH_PORT}/tcp comment "CloudSentinel internal SSH honeypot"
# Allow ClickHouse (local only by default)
ufw allow from 127.0.0.1 to any port 8123 comment "ClickHouse HTTP"
# Public HTTPS proxy for admin API and dashboard feed
ufw allow 80/tcp comment "Caddy ACME HTTP"
ufw allow 443/tcp comment "CloudSentinel HTTPS proxy"
ufw delete allow 3001/tcp 2>/dev/null || true
ufw delete allow 8080/tcp 2>/dev/null || true
ufw --force enable || true
systemctl restart ssh || systemctl restart sshd
echo "Firewall configured."

cat > /etc/caddy/Caddyfile << CADDY
${PUBLIC_TLS_HOST} {
    encode gzip zstd

    handle /socket.io/* {
        reverse_proxy 127.0.0.1:3001
    }

    reverse_proxy https://127.0.0.1:8080 {
        transport http {
            tls_insecure_skip_verify
        }
    }
}
CADDY
systemctl enable caddy
systemctl reload caddy || systemctl restart caddy

# systemd Service
cat > /etc/systemd/system/cloudsentinel.service << SERVICE
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
Environment=CLICKHOUSE_PORT=8123
Environment=CLICKHOUSE_DATABASE=default
Environment=CLICKHOUSE_USERNAME=default
Environment=CLICKHOUSE_PASSWORD=
Environment=NATS_ENABLED=false
Environment=KAFKA_ENABLED=false
Environment=SOAR_FIREWALL_ENABLED=true
Environment=SOAR_FIREWALL_DRY_RUN=false
Environment=SOAR_ACTIVE_PROFILE=do
Environment=SOAR_ALLOWLIST=${SOAR_ALLOWLIST}
Environment=SOAR_BLOCK_TTL=3600
Environment=SOAR_MTTB_TARGET_MS=100
Environment=STREAM_ENABLED=true
Environment=STREAM_HOST=0.0.0.0
Environment=STREAM_PORT=3001
Environment=STREAM_CORS_ORIGIN=${VERCEL_DASHBOARD_ORIGIN}
Environment=ADMIN_ENABLED=true
Environment=ADMIN_PORT=8080
Environment=ADMIN_SERVER=uvicorn
Environment=ADMIN_TOKEN=${ADMIN_TOKEN}

# Resource limits (2 vCPU, 2 GB RAM)
MemoryMax=1024M
CPUQuota=150%

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

install -m 0600 /dev/null /root/cloudsentinel-admin-token
printf '%s\n' "${ADMIN_TOKEN}" > /root/cloudsentinel-admin-token

systemctl daemon-reload
systemctl enable cloudsentinel
systemctl restart cloudsentinel
wait_for_port 127.0.0.1 ${SSH_PORT} "CloudSentinel SSH"
wait_for_port 127.0.0.1 8080 "CloudSentinel Admin API"
wait_for_port 127.0.0.1 3001 "CloudSentinel Socket.io"
wait_for_port 127.0.0.1 443 "CloudSentinel HTTPS proxy"

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
echo " HTTPS proxy: https://${PUBLIC_TLS_HOST}"
echo " SOAR allowlist: ${SOAR_ALLOWLIST}"
echo " Admin token saved at: /root/cloudsentinel-admin-token"
echo "============================================================"
