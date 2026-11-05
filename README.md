# CloudSentinel

CloudSentinel is an SSH honeypot and automated response platform. It records attacker sessions, fingerprints the SSH client with HASSH, maps commands to MITRE ATT&CK, scores the risk, and blocks high-risk sources through a firewall rule.

## Current status

- Phase 1 was deployed on a DigitalOcean droplet and validated on 2026-05-26. The droplet is now offline.
- The dashboard runs on Vercel.
- For a zero-cost demo, run the full stack locally with Docker. See [docs/LOCAL_DEMO.md](docs/LOCAL_DEMO.md).
- Phase 2 is the AWS target: EC2, EventBridge, Security Hub, Lambda, ClickHouse Cloud, App Runner, and Amplify. It is not deployed yet.

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before changing code or writing the report.

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
| Measured evidence | [artifacts/](artifacts/) |
| FYP report source | [docs/working-paper/Pitching/core content/FYP Pitching Content.docx](docs/working-paper/Pitching/core%20content/FYP%20Pitching%20Content.docx) |
| Slide content | [docs/working-paper/Pitching2/slidecontent.txt](docs/working-paper/Pitching2/slidecontent.txt) |
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
