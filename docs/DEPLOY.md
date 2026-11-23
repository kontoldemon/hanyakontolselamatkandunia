# CloudSentinel Deployment Guide

> Status: the droplet used for Phase 1 validation is now offline. This guide remains for redeployment. For a zero-cost local demo, see `docs/LOCAL_DEMO.md`.

## Phase 1: DigitalOcean Dev/MVP

Status snapshot from 2026-05-26:

- Dashboard production URL: `https://dashboard-l7529dwmb-zis3cs-projects.vercel.app`
- Vercel alias: `https://dashboard-six-mu-20.vercel.app`
- Validation target: `188.166.184.42`
- Current validation: see `artifacts/phase1-validation.md` for the recorded result. The snapshot in this guide may be stale.

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

## Phase 2: Azure Production Migration

> This is a planning section. Phase 2 is not deployed. Phase 1 deployment is historical and the droplet is offline.

### Architecture

```text
Internet
  -> Azure public IP + NSG
       :22 public, :22222 admin CIDR, :80/:443 dashboard
  -> Azure VM sensor (Standard_B2ats_v2)
       -> SSH honeypot :2222
       -> HASSH + GeoIP + MITRE + risk score
       -> SOAR decision
            -> Redis channel cloudsentinel:soar:blocks
                 -> host agent -> iptables block with TTL
            -> self-hosted Redis Stream
                 -> ClickHouse on the same VM
                 -> Socket.io stream :3001
                      -> Vercel dashboard
```

The minimal Azure path is one VM. A private ClickHouse VM and Event Grid/Function
are optional scale-up work, not required for the FYP demo.

### Azure service map

| Service | Phase 1 | Phase 2 Azure target |
|---|---|---|
| Sensor | DigitalOcean droplet | Azure VM `Standard_B2ats_v2`, Ubuntu 24.04 |
| Event bus | Local Python call | Local Redis channel `cloudsentinel:soar:blocks` |
| SOAR blocking | iptables subprocess | Host agent on the VM applies iptables with TTL |
| Intelligence | Python dict | Same core; optional Microsoft Defender for Cloud posture |
| Database | Self-hosted ClickHouse | Self-hosted ClickHouse on the same VM |
| Dashboard | Vercel | Vercel (existing) |
| WebSocket | Local Socket.io | Same Socket.io on sensor VM |
| Backups | Local files | Azure Blob Storage |
| Secrets | `.env` / Vault / Infisical | Azure Key Vault + managed identity |
| IaC | Manual | Bicep |

### Step 1: Azure infrastructure (Bicep)

The minimal Bicep is in `infra/main.bicep`. It creates:

- A VNet and an NSG. NSG allows public `22`, admin `22222` from `adminIpCidr`, and `80`/`443`, then denies the rest.
- A `Standard_B2ats_v2` Ubuntu 24.04 sensor VM with a public IP and a 64 GB data disk.
- A system-assigned managed identity on the VM.
- A Key Vault (RBAC) with `Key Vault Secrets User` for the VM.
- A Storage account with a private `backups` container and `Storage Blob Data Contributor` for the VM.

Deploy it:

```bash
az group create --name cloudsentinel-rg --location southeastasia
az deployment group create \
  --resource-group cloudsentinel-rg \
  --template-file infra/main.bicep \
  --parameters \
      adminIpCidr="<your-public-ip>/32" \
      adminSshPublicKey="$(cat ~/.ssh/id_ed25519.pub)"
```

Then mount the data disk and run the normal installer on the VM. The first SSH
login uses port `22`; after `deploy.sh`, management SSH moves to `22222`.

```bash
ssh azureuser@<public-ip>
sudo mkfs.ext4 /dev/disk/azure/scsi1/lun0
sudo mkdir -p /opt/cloudsentinel
sudo mount /dev/disk/azure/scsi1/lun0 /opt/cloudsentinel
sudo ADMIN_IP="<your-public-ip>" ./deploy.sh
```

Store the admin token and LLM key in Key Vault, then copy them into `.env`
through the VM identity. Install the Azure CLI first if it is missing:

```bash
az keyvault secret set --vault-name "<vault-name>" --name ADMIN_TOKEN --value "$(openssl rand -hex 32)"
az keyvault secret set --vault-name "<vault-name>" --name LLM_API_KEY --value "<provider-key>"
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
sudo KEY_VAULT_NAME="<vault-name>" /opt/cloudsentinel/load_secrets.sh
```

The Event Grid topic, Function, and separate ClickHouse VM from earlier drafts
are not part of this minimal path.

### Step 2: Service migration

| Service | Local/Phase 1 behavior | Azure target behavior |
|---|---|---|
| SOAR coordinate | `soar.py` publishes to Redis | Same; the channel is local to the VM |
| Firewall adapter | iptables subprocess | Host agent applies iptables with TTL |
| Redis | Docker Redis | Native Redis on the sensor VM |
| ClickHouse | Docker ClickHouse | Native ClickHouse on the sensor VM |
| Dashboard | Vercel | Same Vercel project |
| Secrets | `.env` | Key Vault through `load_secrets.sh` and the VM identity |

Keep `SOAR_FIREWALL_DRY_RUN=true` until the host agent is running and a test
block has been verified. The host agent only accepts public IPs that are not
allowlisted; the SOAR engine enforces the same rules before publishing.

### Step 3: Cutover checks

1. Verify the sensor VM has no unexpected inbound ports.
2. Verify SSH port 22 redirects to the honeypot on 2222, and management SSH is restricted to the operator IP.
3. Trigger a test block and confirm the host agent adds an iptables rule.
4. Confirm the rule is removed after the TTL.
5. Confirm Redis, ClickHouse, and the admin API are not publicly reachable.
6. Confirm `sudo systemctl status cloudsentinel-host-agent` is active.
7. Confirm ClickHouse rows and dashboard totals match the truth window.
8. Run the MTTB benchmark and record the result.

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
| Automatic blocks do nothing | `systemctl status cloudsentinel-host-agent`; check the Redis channel `cloudsentinel:soar:blocks` |
| MTTB > 100ms | Check the host agent and iptables latency with `iptables -L INPUT -v -n` |
| No attacks showing | Verify port 22 is exposed to internet: `curl ifconfig.me` |
| Dashboard totals look small | Check `CLOUDSENTINEL_TRUTH_WINDOW_HOURS` (0 means all time) and the `clickhouse_ok` field in `/readiness`. |
| Data missing after a ClickHouse outage | Check `var/lib/cloudsentinel/clickhouse_spill.jsonl`. The forwarder replays it when ClickHouse returns. |
