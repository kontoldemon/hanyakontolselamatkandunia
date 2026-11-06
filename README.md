# CloudSentinel

CloudSentinel is an SSH honeypot and automated response platform. It records attacker sessions, fingerprints the SSH client with HASSH, maps commands to MITRE ATT&CK, scores the risk, and blocks high-risk sources through a firewall rule.

## Current status

- Phase 1 was deployed on a DigitalOcean droplet and validated on 2026-05-26. The droplet is now offline.
- The dashboard runs on Vercel.
- For a zero-cost demo, run the full stack locally with Docker. See [docs/LOCAL_DEMO.md](docs/LOCAL_DEMO.md).
- Phase 2 is the Azure target: Azure VM sensor, Event Grid, Azure Functions with NSG blocking, self-hosted ClickHouse, and the existing Vercel dashboard. It is not deployed yet.

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before changing code or writing the report.

## Tech stack

| Layer | Phase 1 (actual) | Phase 2 (Azure target, not deployed) |
|---|---|---|
| Sensor compute | DigitalOcean droplet, Ubuntu 24.04 | Azure VM `Standard_B2ats_v2`, Ubuntu 24.04 |
| SSH honeypot | AsyncSSH on port 2222 | Same, public port 22 redirected to 2222 |
| Fingerprinting | HASSH, JA4S-style profile, GeoIP | Same |
| Detection and scoring | MITRE ATT&CK mapping, anomaly and risk scoring | Same |
| SOAR | Local iptables/nftables block | Azure Event Grid custom topic -> Azure Function -> Azure NSG rule |
| Event buffer | Self-hosted Redis Streams | Self-hosted Redis on the sensor VM |
| Analytics database | Self-hosted ClickHouse | Self-hosted ClickHouse on a private Azure VM |
| Backups | Local daily backup script | Azure Blob Storage target |
| Live stream | Local Socket.io server | Same Socket.io server on the sensor VM |
| Admin API | FastAPI on the sensor | Same FastAPI service, token/JWT protected |
| Dashboard | Next.js 16 on Vercel | Existing Vercel deployment; Azure Static Web Apps is optional later |
| Secrets | `.env`, Vault, or Infisical | Azure Key Vault with managed identity |
| Infrastructure as code | Manual droplet setup | Bicep |
| Observability | Prometheus metrics, structured logs | Azure Monitor and Log Analytics (optional) |

The Azure plan deliberately avoids AKS, Azure Cache for Redis, Azure Data Explorer, managed Kafka, and managed ClickHouse. They add cost and are not needed for the FYP load.

## Quick start (local demo)

```powershell
.\scripts\run_local.ps1
```

This uses `src/cloudsentinel/.env.local`. It listens on `127.0.0.1` only and runs SOAR in dry-run mode.

The SSH honeypot port is `2222`.
Admin API: `http://127.0.0.1:8080/healthz`
Live stream: `http://127.0.0.1:3001`
Dashboard: see [docs/LOCAL_DEMO.md](docs/LOCAL_DEMO.md) and [dashboard/README.md](dashboard/README.md)

For a server deployment, see [docs/DEPLOY.md](docs/DEPLOY.md).

## Documentation map

| Need | Read |
|---|---|
| Architecture and trust boundaries | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Which document is current | [docs/INDEX.md](docs/INDEX.md) |
| Zero-cost local demo | [docs/LOCAL_DEMO.md](docs/LOCAL_DEMO.md) |
| Deployment steps | [docs/DEPLOY.md](docs/DEPLOY.md) |
| ClickHouse truth checks | [docs/CLICKHOUSE_TRUTH_QA.md](docs/CLICKHOUSE_TRUTH_QA.md) |
| Security policy and audit status | [SECURITY.md](SECURITY.md) |
| Measured evidence | [artifacts/](artifacts/) |
| FYP report source | [docs/working-paper/report/FYP Pitching Content.docx](docs/working-paper/report/FYP%20Pitching%20Content.docx) |
| Slide content | [docs/working-paper/slides/slidecontent.txt](docs/working-paper/slides/slidecontent.txt) |
| Code map | [src/cloudsentinel/PROJECT_STRUCTURE.md](src/cloudsentinel/PROJECT_STRUCTURE.md) |

## Evidence

- MTTB, local dry-run: median `0.962 ms`, p95 `1.5 ms` ([artifacts/mttb-benchmark.md](artifacts/mttb-benchmark.md)).
- Concurrency, local dry-run: p95 MTTB below `1000 ms` up to `600` events ([artifacts/mttb-concurrency-threshold.md](artifacts/mttb-concurrency-threshold.md)).
- MITRE coverage: `20` catalogued, `17` mapped from commands ([artifacts/ttp-coverage.md](artifacts/ttp-coverage.md)).
- Phase 1 validation: SSH, management SSH, stream, Redis PASS ([artifacts/phase1-validation.md](artifacts/phase1-validation.md)).

The `0.86 s` MTTB in the literature is from Chin et al. (2025). It is not a result of this project.

## Security

- Honeypot credentials are accepted on purpose. The sensor is not a production SSH server.
- Keep Redis, ClickHouse, NATS, and the admin API on a private network or behind a firewall.
- Do not commit `.env` files or `.vercel/` secrets. Rotate any key that was shared.
- The LLM response path is optional. Prompts are best-effort redacted and rate-limited. Set `LLM_PROVIDER=mock` if commands must not leave the host.
