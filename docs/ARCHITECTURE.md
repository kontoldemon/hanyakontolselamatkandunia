# CloudSentinel Architecture

This file is the single source of truth for the system architecture. If a report, slide, or README disagrees with this file, this file wins.

Last reviewed: 2026-11-23.

## 1. Purpose

CloudSentinel is a cloud-hosted SSH honeypot with automated containment. It does four jobs:

1. Accept SSH sessions from attackers and record what they send.
2. Identify the client with HASSH and map commands to MITRE ATT&CK.
3. Score the risk and block high-risk source IPs with a firewall rule.
4. Store the events and show them on a dashboard.

## 2. Two phases

| Phase | Status | Host |
|---|---|---|
| Phase 1 | Deployed and validated 2026-05-26; currently offline | DigitalOcean droplet, Vercel dashboard |
| Phase 2 | Target, not deployed | Azure VM sensor, Event Grid, Azure Function + NSG rules, private ClickHouse VM, Vercel dashboard |

The detection logic is the same in both phases. Only the cloud adapters change.

## 3. Phase 1 (deployed, now offline)

The Phase 1 stack was validated on 2026-05-26. The droplet is now offline. The same stack can run locally with Docker; see `docs/LOCAL_DEMO.md`.

### Components

| Component | Runs on | Job |
|---|---|---|
| SSH sensor (`server.py`) | DigitalOcean droplet | AsyncSSH honeypot on port `2222`; public `22` is redirected to it |
| Session shell | Sensor process | Fake command registry plus VFS and optional LLM-backed output |
| Fingerprinting | Sensor process | HASSH, JA4S-style profile, client version, GeoIP |
| MITRE and risk | Sensor process | Command to technique mapping, session risk score |
| SOAR | Sensor process | Applies the firewall block when risk passes the threshold |
| Firewall | Droplet kernel | iptables or nftables dynamic block |
| Event pipeline | Droplet | Redis Streams, optional NATS, local WAL fallback |
| ClickHouse | Droplet | Event storage and dashboard queries |
| Stream server | Droplet, port `3001` | Socket.io live feed |
| Admin API | Droplet, port `8080` | Health, stats, sessions, events, block, exposure |
| Dashboard | Vercel | War room, threat map, session replay, AI panel |
| Management SSH | Droplet, separate port | Operator access, not the honeypot |

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
```

If Redis is down, events go to the local WAL and memory queue. The WAL is flushed when Redis returns.

### Default ports

| Port | Service | Exposure |
|---|---|---|
| 22 | SSH honeypot, redirected | Public |
| 2222 | AsyncSSH sensor | Internal |
| 8080 | Admin API | Private or token-protected |
| 3001 | Socket.io stream | Public read-only feed |
| 8443 | HTTP honeypot | Disabled by default |
| 53/udp | DNS honeypot | Disabled by default |

## 4. Phase 2 (Azure target)

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
| Monitoring | Azure Monitor + Log Analytics | Free-tier friendly; optional |
| Dashboard | Vercel | Existing Next.js deployment; Azure Static Web Apps is optional later |

Not in the Azure target: AKS, Azure Cache for Redis, Azure Data Explorer, managed Kafka/Event Hubs, managed ClickHouse, Azure SQL, and Azure Front Door. They add cost without being needed for this project.

## 5. Component map

| Area | Files |
|---|---|
| Entrypoint | `src/cloudsentinel/server.py` |
| Config | `src/cloudsentinel/config.py`, `configs/usas-production.yaml` |
| SSH session and VFS | `vfs.py`, `vfs_agent.py`, `commands/` |
| Fingerprinting | `hassh.py`, `geoip.py` |
| Detection and scoring | `mitre.py`, `anomaly.py`, `attack_graph.py` |
| Response | `soar.py`, `eventgrid.py`, `webhook.py`; host firewall agent in `../host_agent/iptables_worker.py` |
| Azure Function | `../../azure/function/function_app.py`, `block_logic.py` |
| Data pipeline | `pipeline.py`, `event_codec.py` |
| Admin API | `admin_api.py`, `auth.py` |
| Live stream | `stream.py` |
| Other honeypot services | `http_server.py`, `dns_honeypot.py` |
| Threat integrations | `misp_feed.py`, `abuseipdb.py`, `threat_reporter.py` |
| Metrics and logging | `metrics.py`, `observability.py` |
| Tools | `mttb_benchmark.py`, `validate_phase1.py`, `ttp_coverage_test.py`, `stress_test.py`, `honeyfs_seed.py` |

## 6. Trust boundaries

| Boundary | What crosses it | Control |
|---|---|---|
| Internet to honeypot | Untrusted SSH, HTTP, DNS input | Honeypot by design; connection limits; auth attempt cap; fuzz detection |
| Honeypot to internal services | Events and session data | Keep Redis, NATS, ClickHouse on a private network |
| Dashboard to admin API | Admin commands and queries | Bearer token or JWT; TLS when enabled |
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
- Admin API supports a static bearer token or JWT. It fails closed with `503` when neither is configured. The Prometheus text endpoint stays private.
- The dashboard uses an HMAC-signed session cookie, a password step, a six-digit OTP sent by email, and Cloudflare Turnstile. OTP verification is capped at five attempts.
- The public Socket.io stream removes captured passwords. Full event replay remains behind the dashboard session.
- The host agent applies SOAR blocks on the VM and auto-unblocks after the configured TTL. `deploy.sh` installs it as `cloudsentinel-host-agent.service` for non-Azure installs.
- On Azure, `eventgrid.py` publishes a CloudEvent to the block topic. The Function validates public/non-allowlisted IPs, creates an NSG deny rule, and queues its deletion after the TTL. A five-minute timer trigger deletes expired `cs-block-*` rules if a queue message is lost.
- The sensor also publishes the block to the local host-agent channel when Redis is available, so the sensor VM still blocks if Event Grid delivery or the Function fails.
- Manual dashboard blocks use the same Event Grid path when it is enabled, then notify the host agent. They do not bypass the Azure NSG.
- Secrets can come from environment variables, HashiCorp Vault, or Infisical. On Azure, Key Vault has public access disabled and a private endpoint in the VNet; `deploy/load_secrets.sh` copies secrets into the sensor `.env` through the VM managed identity and private DNS.
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
| Dashboard totals | `CLOUDSENTINEL_TRUTH_WINDOW_HOURS=0` | All-time by default. Set `24` for a rolling 24-hour view. |
| Backup | `deploy/backup.sh` | Daily cron backs up Redis, ClickHouse, TTY logs, and buffer files; uploads to Azure Blob when configured. |

The spill file protects against ClickHouse outages, but it uses disk. If the disk fills, events can still be lost. Monitor disk space.

## 9. Known gaps

These are real gaps, not completed features.

1. MTTB is measured in dry-run mode. A live end-to-end run with real firewall changes is still needed.
2. Redis and ClickHouse use generated passwords on the deployment paths. NATS remains without authentication; keep all three on a private network.
3. The public live stream is read-only but unauthenticated. Passwords are removed, but other attacker commands are visible.
4. Session score maps grow for the life of the process. A long-running sensor needs a cleanup job.
5. Phase 2 Azure is not deployed.
6. No uptime percentage has been measured. Do not claim 99.9% or 99.5%.
7. The Phase 1 droplet is offline. No public sensor is live at the moment. Use the local demo for a working system.
8. LLM redaction is pattern-based and best-effort. Use `LLM_PROVIDER=mock` or a local model if commands may contain sensitive data.
9. The Event Grid/Function path adds delivery and NSG-write latency. The recorded MTTB is the sensor-side publish time, not the full NSG enforcement time.
10. Local auto-blocks need the host agent; Azure auto-blocks need the Event Grid subscription, the Function, and the NSG role assignment to be healthy.
11. A manual block with a TTL is enforced by a background task in the API process. A restart before the TTL expires leaves the rule in place.
12. The Function picks a free NSG priority in the 200-3999 range. A full NSG rejects new blocks until rules are cleaned up.

## 10. Configuration rule

Environment variables override the YAML profile. Secrets stay in `.env`, Vault, Infisical, Azure Key Vault, or the Vercel environment. Never commit `.env`, `.vercel/`, tokens, or private keys.

## 11. Documentation rule

1. Change this file first when the architecture changes.
2. Then update `README.md`, `docs/DEPLOY.md`, the FYP report, and the slides.
3. Remove or overwrite old versions. Do not leave two current documents that disagree.

