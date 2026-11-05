# CloudSentinel Code Map

Architecture and trust boundaries: `../../docs/ARCHITECTURE.md`.

## Entry point

| File | Job |
|---|---|
| `server.py` | Unified async entrypoint: SSH sensor, session handling, event pipeline, SOAR, admin API, stream, optional HTTP and DNS honeypots |

The Dockerfile, systemd unit, and `deploy.sh` all start `python -m cloudsentinel.server`.

## Core modules

| Area | Files |
|---|---|
| Config | `config.py`, `configs/usas-production.yaml` |
| SSH session | `server.py`, `shell.py`, `vfs.py`, `vfs_agent.py`, `commands/` |
| Fingerprinting | `hassh.py`, `geoip.py`, `tls.py` |
| Detection and scoring | `mitre.py`, `anomaly.py`, `attack_graph.py` |
| Response | `soar.py`, `firewall.py`, `webhook.py` |
| Data pipeline | `pipeline.py`, `event_codec.py` |
| Admin API | `admin_api.py`, `auth.py` |
| Live stream | `stream.py` |
| Other honeypot services | `http_server.py`, `dns_honeypot.py` |
| Threat feeds and reports | `misp_feed.py`, `abuseipdb.py`, `threat_reporter.py` |
| Metrics and logging | `metrics.py`, `observability.py`, `exceptions.py` |
| Secrets | `_secrets.py` |
| Schema | `schema.sql`, `migrations/` |

## Tools and evidence

| File | Job |
|---|---|
| `mttb_benchmark.py` | MTTB benchmark used by CI and the CLI |
| `validate_phase1.py` | Phase 1 deployment checks |
| `ttp_coverage_test.py` | MITRE coverage evidence |
| `stress_test.py` | Concurrency stress test |
| `honeyfs_seed.py` | Generate the seeded VFS files under `honeyfs/` |
| `cli.py` | `serve`, `benchmark`, `status`, `validate` commands |

## Tests

| File | Job |
|---|---|
| `tests/test_stage1.py` | Main integration tests |
| `tests/test_e2e.py` | End-to-end sensor test |
| `tests/test_properties.py` | Property-based tests |
| `tests/test_benchmarks.py` | Benchmark tests |
| `tests/conftest.py` | Shared fixtures |

## Dashboard

The Next.js dashboard is in `../../dashboard/`. Its API routes call the admin API, not the sensor directly.
