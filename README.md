# CloudSentinel

**SSH honeypot with automated containment for Azure.** CloudSentinel records attacker sessions, fingerprints SSH clients with HASSH, maps commands to MITRE ATT&CK, scores risk, and blocks high-risk sources through Azure NSG rules or a local host firewall.

![CloudSentinel CI](https://github.com/kontoldemon/hanyakontolselamatkandunia/actions/workflows/ci.yml/badge.svg?branch=main)
![Security Audit](https://github.com/kontoldemon/hanyakontolselamatkandunia/actions/workflows/security.yml/badge.svg?branch=main)
![CodeQL](https://github.com/kontoldemon/hanyakontolselamatkandunia/actions/workflows/codeql.yml/badge.svg?branch=main)
![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB)
![Next.js 16](https://img.shields.io/badge/Next.js-16-black)

Last updated: 2026-11-26.

## Status

| Area | State |
|---|---|
| Azure target | Implemented: sensor VM, private ClickHouse, Event Grid, Function + NSG, Key Vault, Blob backups |
| Azure deployment | **Not yet deployed end-to-end**; Bicep/Function/NSG path is still unverified on a live subscription |
| Dashboard | Next.js 16 on Vercel; live deployment needs a refresh from the current repo |
| Android companion | Implemented; debug and unsigned release builds pass |
| Legacy DigitalOcean | Retired; do not deploy new instances |
| Live public sensor | None at the moment; use the local demo or a fresh Azure deployment |

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before changing code or writing the report. Azure is the only supported deployment target.

## Architecture at a glance

```text
Internet
  -> Azure public IP + NSG
       :22 public, :22222 admin CIDR, :80/:443 dashboard
  -> sensor VM
       -> SSH honeypot :2222
       -> HASSH + GeoIP + MITRE + risk score
       -> SOAR decision
            -> Event Grid -> Azure Function -> NSG deny rule with TTL
            -> Redis Stream -> private ClickHouse VM
            -> Socket.io -> Vercel dashboard
            -> FCM -> Android companion

Dashboard / Android
  -> sensor admin API (token/JWT; scoped mobile device token)
```

Detailed trust boundaries, control planes, and known gaps: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## What it does

- Captures SSH attacker sessions and command history in a deceptive VFS.
- Fingerprints clients with HASSH/JA4S-style signals and enriches public IPs.
- Scores events, maps commands to MITRE ATT&CK, and applies SOAR policy.
- Blocks risky IPs through Azure Event Grid/Function/NSG or the local host agent.
- Streams telemetry to a Next.js war room and a Kotlin/Compose Android companion.
- Keeps ClickHouse analytics, Redis buffering, Blob backups, and Key Vault secrets in one Azure design.

## Quick start

### Local demo

```powershell
.\scripts\run_local.ps1
```

The local demo binds to `127.0.0.1` and runs SOAR in dry-run mode.

| Service | URL |
|---|---|
| SSH honeypot | `localhost:2222` |
| Admin API | `http://127.0.0.1:8080/healthz` |
| Live stream | `http://127.0.0.1:3001` |
| Dashboard | see [docs/LOCAL_DEMO.md](docs/LOCAL_DEMO.md) |

For the Docker demo, set `ADMIN_TOKEN` in `src/cloudsentinel/.env` and use the same value in `dashboard/.env.local`. The admin API refuses requests when no token is configured.

### Tests

```powershell
$env:PYTHONPATH="src"
python -m pytest src/cloudsentinel/tests -q -o addopts="-n auto --cov=cloudsentinel --cov-report=term --cov-fail-under=99"

cd dashboard
npm run build

cd ..\mobile-android
.\gradlew.bat assembleDebug
```

The Python gate enforces 99% coverage. The Android release build is unsigned by default.

## Repository layout

```text
src/cloudsentinel/     Sensor, SSH/VFS, detection, SOAR, pipeline, admin API, mobile backend
dashboard/             Next.js war room, settings, telemetry, auth, API proxies
mobile-android/        Kotlin/Compose SOC companion, pairing, FCM, forensics
azure/function/        NSG block/unblock Function
infra/                 Azure Bicep and cloud-init
deploy/                Installer, service unit, backups, monitoring, nginx/Helm
docs/                  Architecture, mobile, deployment, local demo, QA runbooks
artifacts/             MTTB, concurrency, MITRE coverage, phase validation evidence
```

## Documentation

| Need | Read |
|---|---|
| Architecture and trust boundaries | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Android companion, pairing, FCM, debugging | [docs/MOBILE.md](docs/MOBILE.md) |
| Azure deployment | [docs/DEPLOY.md](docs/DEPLOY.md) |
| Zero-cost local demo | [docs/LOCAL_DEMO.md](docs/LOCAL_DEMO.md) |
| ClickHouse truth checks | [docs/CLICKHOUSE_TRUTH_QA.md](docs/CLICKHOUSE_TRUTH_QA.md) |
| Security policy and audit status | [SECURITY.md](SECURITY.md) |
| Current document index | [docs/INDEX.md](docs/INDEX.md) |
| Sensor code map | [src/cloudsentinel/PROJECT_STRUCTURE.md](src/cloudsentinel/PROJECT_STRUCTURE.md) |
| Dashboard setup | [dashboard/README.md](dashboard/README.md) |
| Android quick start | [mobile-android/README.md](mobile-android/README.md) |
| Azure infrastructure | [infra/main.bicep](infra/main.bicep) |
| Azure Function | [azure/function/](azure/function/) |
| Measured evidence | [artifacts/](artifacts/) |

## Security

- Honeypot credentials are accepted on purpose; the sensor is not a production SSH server.
- The admin API fails closed with `503` when neither `ADMIN_TOKEN` nor JWT auth is configured. Keep `/metrics` private.
- The live stream removes captured passwords. Set `STREAM_AUTH_TOKEN` on the sensor and `NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_TOKEN` on the dashboard; an empty token leaves the stream open.
- Mobile device tokens are scoped to `/mobile/*`, hashed at rest, revocable, and treated as high-privilege credentials. Mobile exposure uses host iptables, not the Azure NSG.
- The Event Grid Function only handles public, non-allowlisted IPs, creates NSG deny rules with a TTL, and cleans up expired rules.
- Secrets stay in Azure Key Vault, Vault/Infisical, or the environment. Never commit `.env`, `.vercel/`, tokens, or private keys.
- The LLM path is optional; prompts are best-effort redacted and rate-limited. Use `LLM_PROVIDER=mock` when commands must not leave the host.

## Evidence

| Metric | Result |
|---|---|
| MTTB, local dry-run | Median `0.962 ms`, p95 `1.5 ms` |
| Concurrency, local dry-run | p95 below `1000 ms` up to `600` events |
| MITRE coverage | `20` catalogued, `17` mapped from commands |
| Phase 1 validation | SSH, management SSH, stream, Redis PASS |

Sources: [artifacts/mttb-benchmark.md](artifacts/mttb-benchmark.md), [artifacts/mttb-concurrency-threshold.md](artifacts/mttb-concurrency-threshold.md), [artifacts/ttp-coverage.md](artifacts/ttp-coverage.md), [artifacts/phase1-validation.md](artifacts/phase1-validation.md).

The `0.86 s` MTTB in the literature is from Chin et al. (2025), not a result of this project.

## Deploy

```bash
az group create --name cloudsentinel-rg --location southeastasia
az deployment group create \
  --resource-group cloudsentinel-rg \
  --template-file infra/main.bicep \
  --parameters adminIpCidr="<your-ip>/32" adminSshPublicKey="<public-key>"
```

Full steps, Key Vault/Event Grid wiring, and verification: [docs/DEPLOY.md](docs/DEPLOY.md).

## FYP material

- Report: [FYP Pitching Content.docx](docs/working-paper/report/FYP%20Pitching%20Content.docx)
- Slides: [CloudSentinel-slides.pptx](docs/working-paper/slides/CloudSentinel-slides.pptx)
- Slide text: [slidecontent.txt](docs/working-paper/slides/slidecontent.txt)
