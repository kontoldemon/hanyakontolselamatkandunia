# CloudSentinel Architecture

This file is the single source of truth for the system architecture. If a report, slide, or README disagrees with this file, this file wins.

Last reviewed: 2026-11-26.

## 1. Purpose

CloudSentinel is a cloud-hosted SSH honeypot with automated containment. It does five jobs:

1. Accept SSH sessions from attackers and record what they send.
2. Identify the client with HASSH and map commands to MITRE ATT&CK.
3. Score the risk and block high-risk source IPs with a firewall rule.
4. Store the events and show them on a dashboard.
5. Give the operator a scoped Android companion for alerts and triage.

The Android companion does not replace the web dashboard or open a second data plane; it calls the sensor admin API with a paired device token. Its full contract is in `docs/MOBILE.md`.

## 2. Deployment status

| Target | Status |
|---|---|
| Azure | Supported deployment target: sensor VM, Event Grid, Azure Function + NSG rules, private ClickHouse VM, Vercel dashboard |
| Legacy DigitalOcean Phase 1 | Retired and no longer supported; do not deploy new instances |

## 3. Runtime flow

The runtime can also run locally with Docker; see `docs/LOCAL_DEMO.md`.

### Data flow

```text
Attacker
  -> public port 22 (redirect)
  -> sensor port 2222
  -> HASSH + GeoIP + MITRE + risk score
  -> SOAR decision
       -> firewall block (high risk)
       -> Redis Stream (all events)
            -> ClickHouse (batch forwarder)
            -> Socket.io (live feed)
                 -> Vercel dashboard
            -> mobile alert policy
                 -> paired Android device (FCM HTTP v1)
```

If Redis is down, events go to the local WAL and memory queue. The WAL is flushed when Redis returns.

The mobile control plane is separate from the live event stream:

```text
Android app
  -> sensor admin API /mobile/* with a device bearer token
       -> block handler, queries, exposure state, AI copilot
```

Pairing is bootstrapped from the web dashboard: the dashboard asks the sensor for a 5-minute challenge, then the phone scans the QR or uses the deep link. The device receives a scoped `cs_mob_*` token; only its hash is stored on the sensor.

### Default ports

| Port | Service | Exposure |
|---|---|---|
| 22 | SSH honeypot, redirected | Public |
| 2222 | AsyncSSH sensor | Internal |
| 443 | Caddy TLS for admin API and Socket.io | Public |
| 8080 | Admin API (including `/mobile/*`) | Private or token-protected |
| 3001 | Socket.io stream | Should be private or token-protected |
| 8443 | HTTP honeypot | Disabled by default |
| 53/udp | DNS honeypot | Disabled by default |

## 4. Azure target

Azure NSG block rules use priority 100-199 so they are evaluated before the static allow rules at 200-230. Lower priority numbers are evaluated first; a block rule above an allow rule would never match the attacker traffic.

```text
Internet
  -> Azure sensor VM (Standard_B2ats_v2, public IP + NSG)
       NSG: 22 public, 22222 admin CIDR, 80/443 for the dashboard
  -> HASSH + GeoIP + MITRE + risk score
  -> SOAR decision
       -> Azure Event Grid custom topic (CloudEventSchemaV1_0)
            -> Azure Function (system-assigned managed identity)
                 -> NSG deny rule with TTL
                 -> storage queue -> delete rule after TTL
       -> self-hosted Redis Stream
            -> private ClickHouse VM (Standard_B2s, data subnet)
            -> Socket.io stream on the sensor VM
                 -> Vercel dashboard
```

Phase 2 is a migration plan. Do not describe it as deployed. The local host
agent remains as a fallback for non-Azure installs; Azure uses Event Grid and
the Function.

### Azure service choices

| Job | Azure choice | Reason |
|---|---|---|
| Sensor host | `Standard_B2ats_v2` VM, Ubuntu 24.04 | Low-cost, enough for AsyncSSH and the local pipeline |
| ClickHouse | `Standard_B2s` VM, private data subnet | Self-hosted keeps cost predictable; no Azure Data Explorer |
| Event routing | Event Grid custom topic | Native event delivery to the Function without a broker cluster |
| Automated block | Azure Function (Consumption) with system-assigned managed identity | Creates and deletes NSG rules through Azure Resource Manager |
| Firewall | Azure NSG | Native, auditable, removable with a TTL |
| Backups | Azure Blob Storage | Off-VM copy of ClickHouse and Redis backups |
| Secrets | Azure Key Vault + private endpoint + managed identity | `deploy/load_secrets.sh` copies secrets into `.env` over the private endpoint |
| Monitoring | Application Insights + Log Analytics for the Function; Prometheus on the VM | Function traces and logs without extra infrastructure |
| Dashboard | Vercel | Existing Next.js deployment; Azure Static Web Apps is optional later |

Not in the Azure target: AKS, Azure Cache for Redis, Azure Data Explorer, managed Kafka/Event Hubs, managed ClickHouse, Azure SQL, and Azure Front Door. They add cost without being needed for this project.

### 4.1 Control planes

| Plane | Client | Auth | Main paths |
|---|---|---|---|
| Web dashboard | Browser on Vercel | HMAC session cookie after password + OTP + Turnstile | Next.js pages and `/api/cloudsentinel/*` proxies |
| Sensor admin API | Dashboard server, CLI, mobile admin actions | `ADMIN_TOKEN` or JWT | `/stats`, `/events`, `/sessions`, `/admin/*`, `/runtime-config`, `/llm/*`, `/mobile/config` |
| Mobile device API | Android companion | Scoped `cs_mob_*` device token | `/mobile/alerts`, `/mobile/dashboard`, `/mobile/sessions`, `/mobile/block-ip`, `/mobile/exposure`, `/mobile/policy`, `/mobile/runtime-controls`, `/mobile/ai-copilot` |
| Live stream | Dashboard browser | Optional `STREAM_AUTH_TOKEN` | Socket.io on 3001 / Caddy 443 |

The dashboard never exposes the sensor admin token to the browser. Next.js route handlers proxy admin calls server-side using `CLOUDSENTINEL_ADMIN_TOKEN`.

## 5. Component map

| Area | Files |
|---|---|
| Entrypoint | `src/cloudsentinel/server.py` |
| Config and runtime settings | `config.py`, `configs/usas-production.yaml`, `runtime_config.py` |
| SSH session and VFS | `sensor/session.py`, `sensor/ssh.py`, `sensor/tty.py`, `vfs.py`, `vfs_agent.py`, `commands/` |
| Fingerprinting and limits | `sensor/fingerprint.py`, `sensor/limits.py`, `hassh.py`, `geoip.py` |
| Detection and scoring | `mitre.py`, `anomaly.py`, `attack_graph.py` |
| Response | `soar.py`, `eventgrid.py`, `webhook.py`; host firewall agent in `../host_agent/iptables_worker.py` |
| Azure Function | `../../azure/function/function_app.py`, `block_logic.py` |
| Data pipeline | `pipeline.py`, `event_codec.py` |
| Admin API | `admin_api.py`, `api/routers/`, `api/queries.py`, `api/firewall.py`, `auth.py` |
| Live stream | `stream.py` |
| Mobile backend | `mobile_push.py`, `api/routers/mobile.py` |
| Mobile Android | `../../mobile-android/` |
| Dashboard | `../../dashboard/` (Next.js 16, Vercel) |
| Other honeypot services | `http_server.py`, `dns_honeypot.py` |
| Threat integrations | `misp_feed.py`, `abuseipdb.py`, `threat_reporter.py` |
| Metrics and logging | `metrics.py`, `observability.py` |
| Tools | `mttb_benchmark.py`, `validate_phase1.py`, `ttp_coverage_test.py`, `stress_test.py`, `honeyfs_seed.py` |

## 6. Trust boundaries

| Boundary | What crosses it | Control |
|---|---|---|
| Internet to honeypot | Untrusted SSH, HTTP, DNS input | Honeypot by design; connection limits; auth attempt cap; fuzz detection |
| Honeypot to internal services | Events and session data | Keep Redis, NATS, ClickHouse on a private network |
| Browser to Vercel dashboard | Login credentials, OTP, session cookie | Turnstile, password step, email OTP, HMAC session cookie, CSP and COOP/CORP headers |
| Dashboard to admin API | Admin commands and queries | Server-side proxy; bearer token or JWT; TLS; admin token never sent to the browser |
| Mobile app to admin API | Pairing challenge, device token, commands | 5-minute pairing challenge, 10 attempts/min/IP, hashed device tokens, HTTPS in release |
| Sensor to FCM | Alert metadata | Optional outbound push; notification content is visible on the lock screen |
| Admin API to firewall | Block and unblock commands | IP validation, allowlist, public-IP check |
| Sensor to LLM provider | Attacker commands and session context | Optional feature; disable if data cannot leave the host |
| Sensor to Azure control plane | Block request (IP, TTL, reason) | Event Grid key from Key Vault; Function managed identity with a custom NSG rule operator role on the sensor NSG; allowlist and public-IP validation |
| Sensor to sandbox | Untrusted payload execution | gVisor or Docker isolation, no network, memory and CPU limits |
| Operator to server | Management SSH | Separate port, key-based access |

## 7. Security controls in the running system

- The SSH sensor accepts any credential on purpose. It is a honeypot, not a production server.
- `ConnectionLimiter` caps per-IP and total connections in a 60 second window.
- Password attempts are capped at 20 per session.
- Fuzz detection rejects oversized packets and null floods.
- SOAR blocks only public IPs and skips the configured allowlist.
- Admin API supports a static bearer token or JWT. It fails closed with `503` when neither is configured, including the login endpoint. The Prometheus text endpoint stays private.
- The dashboard uses an HMAC-signed session cookie, a password step, a six-digit OTP sent by email, and Cloudflare Turnstile. OTP verification is capped at five attempts, and OTP delivery fails closed in production. The post-login `next` target is origin-validated to block external and backslash redirects.
- Dashboard responses set CSP, COOP, CORP, HSTS, frame denial, MIME sniffing protection, and a restrictive permissions policy. `X-Powered-By` is disabled.
- The live stream removes captured passwords. `STREAM_AUTH_TOKEN` can require a token; when it is empty the stream must stay on a private network or behind TLS. Full event replay remains behind the dashboard session.
- Mobile devices pair with a 6-digit code plus a short-lived pairing token. Device tokens are scoped to `/mobile/*`, stored as hashes on the sensor, kept in Android `EncryptedSharedPreferences`, and revocable. Release Android builds disable cleartext traffic.
- Mobile device tokens are high privilege: block, exposure, and runtime-control actions are available without the admin token. Runtime-control changes are in-memory only and are lost on restart.
- Mobile blocks reuse the normal block handler; they do not write NSG rules directly. Mobile exposure reuses the host iptables toggle; it is not an Azure NSG control.
- The host agent applies SOAR blocks on the VM and auto-unblocks after the configured TTL. `deploy.sh` installs it as `cloudsentinel-host-agent.service` for non-Azure installs.
- On Azure, `eventgrid.py` publishes a CloudEvent to the block topic. The Function validates public/non-allowlisted IPs, rejects malformed events, creates an NSG deny rule, and queues its deletion after the TTL. Malformed unblock messages are ignored, and a five-minute timer trigger deletes expired `cs-block-*` rules if a queue message is lost.
- The sensor also publishes the block to the local host-agent channel when Redis is available, so the sensor VM still blocks if Event Grid delivery or the Function fails.
- Manual dashboard blocks use the same Event Grid path when it is enabled, then notify the host agent. They do not bypass the Azure NSG.
- Secrets come from environment variables. On Azure, Key Vault has public access disabled and a private endpoint in the VNet; `deploy/load_secrets.sh` copies secrets into the sensor `.env` through the VM managed identity and private DNS.
- The AI response path is optional. Secrets are redacted before the prompt, and calls are limited per session (20) and globally (200 per hour). If the budget is exhausted or no API key is set, the agent falls back to deterministic output.
- Optional integrations: Webhook alerts, AbuseIPDB, MISP, AI threat summaries.

## 8. Measured evidence

All numbers below are from the project artifacts, not from live production traffic.

| Metric | Result | Source |
|---|---|---|
| MTTB, local dry-run, 3 iterations | Median `0.962 ms`, p95 `1.5 ms`, target `100 ms`, PASS | `artifacts/mttb-benchmark.md` |
| Concurrency, local dry-run SOAR | p95 MTTB below `1000 ms` up to `600` events; at `800` events p95 is `1009.892 ms` | `artifacts/mttb-concurrency-threshold.md` |
| MITRE coverage | `20` catalogued, `17` mapped from commands | `artifacts/ttp-coverage.md` |
| Phase 1 validation | SSH PASS, management SSH PASS, stream PASS, Redis connected; ClickHouse result not recorded | `artifacts/phase1-validation.md` |

The phase 1 validation artifact reports `21` MITRE techniques mapped. The coverage artifact breaks the same catalog down as `20` techniques with `17` mapped from commands. The report uses the coverage artifact. The `0.86 s` MTTB reported by Chin et al. (2025) is prior work. It is not a result of this project.

## 8.1 Data retention and recovery

| Layer | Setting | Behavior |
|---|---|---|
| ClickHouse | `TTL timestamp + INTERVAL 3650 DAY` | Keeps ten years. No 90-day deletion. |
| Redis Stream | `maxlen: 200000` | Buffer for the forwarder. Oldest entries trim only after 200k events. |
| ClickHouse forwarder | Spill file | If ClickHouse is down, raw events go to `var/lib/cloudsentinel/clickhouse_spill.jsonl` and replay when it returns. |
| ClickHouse dedup | `insert_deduplication_token` + 1,000-block window | A retried spill batch after a crash is deduplicated. |
| Dashboard totals | `CLOUDSENTINEL_TRUTH_WINDOW_HOURS=0` | All-time by default. Set `24` for a rolling 24-hour view. |
| Backup | `deploy/backup.sh` | Daily cron backs up Redis, ClickHouse, TTY logs, and buffer files; refreshes the VM managed identity, uploads to Azure Blob, and prunes old Blob copies using `AZURE_RETENTION_DAYS`. |

The spill file protects against ClickHouse outages, but it uses disk. If the disk fills, events can still be lost. Monitor disk space.

## 9. Known gaps

These are real gaps, not completed features.

1. MTTB is measured in dry-run mode. A live end-to-end run with real firewall changes is still needed.
2. Redis and ClickHouse use generated passwords on the deployment paths. NATS uses a compose default password; override `NATS_PASSWORD` for shared environments. Keep all three on a private network.
3. The live stream is read-only and supports `STREAM_AUTH_TOKEN`, but the stream stays open when the token is empty on either side. Events are redacted of passwords, not of other attacker commands. Set the token and keep 3001 off the public internet.
4. In-memory SOAR IP/session maps, HASSH sightings, and the connection limiter are capped at 10,000 entries; the oldest entries are pruned, per-IP session sets are capped, and closed sessions are removed. SSH command lines are capped at 8 KiB and per-session TTY logs at 1 MB. Active entries beyond the caps can be evicted under extreme load.
5. Phase 2 Azure is not deployed.
6. No uptime percentage has been measured. Do not claim 99.9% or 99.5%.
7. No public sensor is live at the moment. The old Phase 1 droplet is offline; the Vercel dashboard is still up but points at stale settings. Use the local demo or a fresh Azure deployment for a working system.
8. LLM redaction is pattern-based and best-effort. Use `LLM_PROVIDER=mock` or a local model if commands may contain sensitive data.
9. The Event Grid/Function path adds delivery and NSG-write latency. The recorded MTTB is the sensor-side publish time, not the full NSG enforcement time.
10. Local auto-blocks need the host agent; Azure auto-blocks need the Event Grid subscription, the Function, and the NSG role assignment to be healthy.
11. A manual block with a TTL is enforced by a background task in the API process. A restart before the TTL expires leaves the rule in place.
12. The Function picks a free NSG priority in the 200-3999 range. A full NSG rejects new blocks until rules are cleaned up.
13. The interactive shell passes piped output to `grep`, `cut`, and basic `awk` forms (`{print $N}`, `/regex/`, `$N` comparisons, and `&&`/`||`/`!` conditions); `awk` `BEGIN`/`END`, parentheses grouping, and file arguments are not supported. `;`/`&&`/`||` execute each segment independently.
14. Mobile exposure executes the sensor host iptables path, not the Azure NSG. It returns an error if iptables is unavailable or the API process lacks permission.
15. FCM uses a manually supplied `CLOUDSENTINEL_FCM_ACCESS_TOKEN`; it is not refreshed automatically, so push delivery stops when the token expires.
16. The live Vercel deployment does not serve the latest security headers, and the old custom domain is dead. Redeploy from the current repository before treating live headers as final.
17. Android debug and unsigned release builds are verified (`assembleDebug`, `assembleRelease`, 2026-11-26); release signing, device instrumentation tests, and a physical-device pass are still untested.
18. Mobile runtime-control changes (`deception`, SOAR dry-run, HASSH action) mutate the live process only and are not persisted to runtime config; they revert on restart.

## 10. Testing and debugging

### 10.1 Python

```powershell
$env:PYTHONPATH="src"
python -m pytest src/cloudsentinel/tests -q -o addopts="-n auto --cov=cloudsentinel --cov-report=term --cov-fail-under=99"
```

The suite covers the sensor, API routers, auth matrix, Azure guards, mobile API state, runtime config, and golden shell transcripts. CI runs the same gate on Python 3.12. Do not add tests that depend on the developer's `.env` or a stale `var/runtime_config.json`; use `tmp_path` and `monkeypatch`.

### 10.2 Dashboard

```powershell
cd dashboard
npm run build
npx eslint src
```

The build is the type/runtime gate. Browser checks to run manually after deploy:

1. Sign in through password, Turnstile, and OTP.
2. Confirm the post-login redirect only goes to an internal path.
3. Confirm the latest CSP, COOP, CORP, HSTS, and `X-Powered-By` removal in response headers.
4. Open Settings and verify runtime config, LLM config, decoys, mobile pairing, and exposure controls reach the sensor.
5. Confirm the phone pairing QR expires and that a revoked device gets `401`.

### 10.3 Mobile

```powershell
cd mobile-android
.\gradlew.bat assembleDebug
```

Manual checks: QR pairing, manual pairing, dashboard KPIs, alert list, block action, session inspector, copilot failure message, FCM test alert, unpair, and revocation. The release build must use HTTPS; the debug build is the only build that permits cleartext.

### 10.4 Live checks

```powershell
curl.exe -sSI https://<dashboard-domain>/
curl.exe -sS https://<sensor-fqdn>/healthz
```

Expected: HSTS, CSP, COOP/CORP, no `X-Powered-By`, admin health reachable only through the intended TLS endpoint. The current Vercel deployment is stale; verify after redeploy, not before.

### 10.5 Common debug paths

| Symptom | First checks |
|---|---|
| Dashboard loads but API returns 401 | Session cookie, `DASHBOARD_AUTH_SECRET`, `CLOUDSENTINEL_ADMIN_TOKEN`, Vercel env |
| Admin API returns 503 | No `ADMIN_TOKEN`, JWT disabled, or auth config unavailable; check `/readiness` |
| Events missing | Redis connection, ClickHouse forwarder, `CLOUDSENTINEL_TRUTH_WINDOW_HOURS`, `/readiness` |
| Live stream silent | `NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_URL`, `STREAM_AUTH_TOKEN` match, Caddy WebSocket proxy, token expiry |
| Mobile pairing 401/429 | Pairing token/code mismatch, challenge older than 5 minutes, >10 attempts/min/IP |
| Mobile API 401 | Device revoked, token not stored, or wrong sensor URL |
| FCM missing | `google-services.json`, FCM project/access token, notification permission |
| Auto-block only dry-run | `SOAR_FIREWALL_DRY_RUN`, Event Grid env, Function role, host agent |
| NSG block not created | Event Grid subscription, Function logs, `NSG_NAME`, `NSG_RESOURCE_GROUP`, role assignment |

## 11. Configuration rule

Environment variables override the YAML profile. Secrets stay in `.env`, Vault, Infisical, Azure Key Vault, or the Vercel environment. Never commit `.env`, `.vercel/`, tokens, or private keys.

## 12. Documentation rule

1. Change this file first when the architecture changes.
2. Keep `docs/MOBILE.md` in sync for mobile behavior and limits.
3. Then update `README.md`, `docs/DEPLOY.md`, the FYP report, and the slides.
4. Remove or overwrite old versions. Do not leave two current documents that disagree.

