# CloudSentinel Deployment Guide

## Phase 1: DigitalOcean Dev/MVP

Current status as of 2026-05-26:

- Dashboard production URL: `https://dashboard-l7529dwmb-zis3cs-projects.vercel.app`
- Vercel alias: `https://dashboard-six-mu-20.vercel.app`
- Validation target: `188.166.184.42`
- Current validation: SSH honeypot PASS, MITRE coverage PASS, management SSH FAIL, Socket.io FAIL, admin API FAIL
- Blocker: this workstation cannot reach `188.166.184.42:22222`, so backend deployment cannot be completed remotely until management SSH is open or valid access details are provided.

### Prerequisites

- DigitalOcean account (free $200 credits via GitHub Student Pack)
- Domain name (optional, for TLS)
- SSH key pair for server access

### Step 1: Provision Droplet

```bash
# Using doctl (DigitalOcean CLI)
doctl compute droplet create cloudsentinel-sensor \
  --image ubuntu-24-04-x64 \
  --size s-1vcpu-1gb \
  --region sgp1 \
  --ssh-keys <your-key-id> \
  --tag-name cloudsentinel

# Or via the DO web dashboard:
# Create > Droplets > Ubuntu 24.04 LTS > Basic > $4/mo (1 vCPU / 1 GB)
```

### Step 2: Initial Server Setup

```bash
ssh root@<droplet-ip>

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER

# Install Docker Compose
apt install -y docker-compose-plugin

# Create cloudsentinel user
useradd -r -s /bin/false -d /opt/cloudsentinel cloudsentinel
mkdir -p /opt/cloudsentinel
```

### Step 3: Deploy CloudSentinel

```bash
# Copy the local project or clone repository, then deploy sensor package
cd /opt/cloudsentinel/src/cloudsentinel

# Recommended Phase 1 installer
sudo ADMIN_IP=<your-public-admin-ip> ./deploy.sh

# Verify on droplet
sudo systemctl status cloudsentinel
sudo journalctl -u cloudsentinel -n 100 --no-pager
curl http://127.0.0.1:8080/healthz
```

### Step 4: Expose Port 22

```bash
# The honeypot runs on port 2222 inside Docker.
# Redirect port 22 to 2222 using iptables:
iptables -t nat -A PREROUTING -p tcp --dport 22 -j REDIRECT --to-port 2222
iptables-save > /etc/iptables/rules.v4

# Or change docker-compose.yml ports mapping:
#   ports:
#     - "22:2222"
```

### Step 5: Install Systemd Service (without Docker)

```bash
cp deploy/cloudsentinel.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable cloudsentinel
systemctl start cloudsentinel
systemctl status cloudsentinel
```

### Step 6: Deploy Dashboard to Vercel

```bash
cd dashboard

# Local verification
npm install
npm run lint
npm run build

# Production deploy
vercel deploy --prod --yes

# Set environment variables in Vercel dashboard:
# NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_URL=http://<droplet-ip>:3001
# CLOUDSENTINEL_ADMIN_API_URL=http://<droplet-ip>:8080
# CLOUDSENTINEL_ADMIN_TOKEN=<optional-admin-token>
# DASHBOARD_USERNAME=<dashboard-user>
# DASHBOARD_PASSWORD=<dashboard-password>
# DASHBOARD_AUTH_SECRET=<random-64-byte-secret>
```

## Phase 2: AWS Production Migration

### Architecture

```
Internet --> AWS WAF --> EC2 (Sensor) --> EventBridge --> Lambda (SOAR)
                                    |
                            ClickHouse Cloud
                                    |
                            Amplify (Dashboard)
```

### Step 1: AWS Infrastructure (Terraform)

```hcl
# Coming soon: terraform/ directory with full AWS infra
# - EC2 t3.micro for sensor
# - EventBridge event bus
# - Lambda function for SOAR
# - Security Hub for intelligence
# - Amplify for dashboard
# - App Runner for WebSocket
```

### Step 2: Migrate Services

| Service | Phase 1 | Phase 2 |
|---|---|---|
| Sensor | DO Droplet | EC2 t3.micro |
| Event Bus | Local Python call | EventBridge |
| SOAR | iptables subprocess | Lambda |
| Intelligence | Python dict | Security Hub |
| Database | Self-hosted ClickHouse | ClickHouse Cloud |
| Dashboard | Vercel | Amplify |
| WebSocket | Local Socket.io | App Runner |

### Monitoring & Alerts

```bash
# View logs
journalctl -u cloudsentinel -f

# Prometheus metrics
curl http://localhost:8080/metrics

# Health check
curl http://localhost:8080/healthz
```

### Troubleshooting

| Issue | Fix |
|---|---|
| Port 22 already in use | `lsof -i :22` to find process, stop SSH server |
| Redis connection refused | `docker compose restart redis-plain` |
| ClickHouse connection refused | Check `CLICKHOUSE_PASSWORD` in `.env` |
| MTTB > 100ms | Check firewall backend: `nftables` is faster than `iptables` |
| No attacks showing | Verify port 22 is exposed to internet: `curl ifconfig.me` |
