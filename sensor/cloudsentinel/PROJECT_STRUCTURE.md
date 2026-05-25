# CloudSentinel v2.0 — Production-Grade Honeypot

## Architecture
```
sensor/cloudsentinel/
  server.py              # Unified async SSH + HTTP + DNS honeypot entrypoint
  auth.py                # HS256 JWT auth (zero-dependency)
  tls.py                 # Self-signed TLS cert auto-generation
  anomaly.py             # ML anomaly detection (IsolationForest + heuristics)
  dns_honeypot.py        # UDP DNS honeypot (T1590 trap)
  webhook.py             # Slack/Discord/Telegram alerting
  soar.py                # SOAR engine (attack chains, IP profiling, iptables)
  pipeline.py            # Redis Streams + ClickHouse + WAL
  config.py              # Pydantic Settings (YAML + .env + env vars)
  admin_api.py           # JWT-protected REST API (health, stats, attack-graph)
  vfs.py                 # Virtual filesystem (61 entries, 18 honeytokens)
  vfs_agent.py           # LLM-backed command output generator
  commands/              # 163 fake Linux commands
    __init__.py           #   Command base class + CommandAdapter
    base.py               #   55+ registered command implementations
  hassh.py               # HASSH fingerprinting (18 real-MD5 fingerprints)
  mitre.py               # MITRE ATT&CK mapping (20 techniques, 21 regex)
  geoip.py               # MaxMind GeoIP2 enrichment
  metrics.py             # Prometheus metrics (12 gauge/counter)
  observability.py       # loguru + structlog + sentry + OpenTelemetry
  http_server.py         # HTTP honeypot (WordPress, Tomcat, phpMyAdmin, .env trap)
  stream.py              # Socket.io live event streaming
  sandbox.py             # Docker sandbox for payload execution
  threat_reporter.py     # AI threat report generation (Gemini/OpenAI)
  shell.py               # Interactive shell protocol (pipe, redirect, TAB)
  event_codec.py         # msgspec fast serialization
  output.py              # ClickHouse batch output writer
  stress_test.py         # 500-connection concurrent stress test
  validate_phase1.py     # Live deployment validation
  ttp_coverage_test.py   # MITRE TTP coverage evidence generator
  mttb_benchmark.py      # SOAR mean-time-to-block benchmark
  configs/
    usas-production.yaml  # Production profile
  tests/
    test_stage1.py        # 45 integration/unit tests (11 categories)
  .pre-commit-config.yaml # ruff + bandit + general hooks
  pyproject.toml          # ruff, mypy, bandit, pytest-cov config
  Dockerfile              # Python 3.12 + healthcheck
  docker-compose.yml      # Redis + NATS + Redpanda + CloudSentinel
  deploy.sh               # DigitalOcean deployment script
  requirements.txt        # 30+ production dependencies
  log_config.json         # Structured JSON logging configuration
  schema.sql              # ClickHouse schema (MergeTree + materialized views)
```

## Key Metrics
- **HASSH fingerprints**: 18 real cryptographically-computed MD5 hashes
- **Botnets detected**: Mirai (4 variants), Gafgyt (2), Mozi, Hajime, Tsunami, Dark.IoT, Qbot, RIoT, Meris, 3ve
- **Scanners detected**: Nmap, Zgrab2 (2), Masscan (2), SSH-audit
- **Commands**: 163 registered Linux utilities
- **VFS entries**: 61 files, 18 honeytoken traps
- **MITRE techniques**: 20 mapped, 21 regex patterns
- **Tests**: 45 cases across 11 categories
- **MTTB**: 0.96ms median (target: 100ms)
- **API endpoints**: /healthz, /readiness, /stats, /attack-graph, /auth/login
- **Alert platforms**: Slack, Discord, Telegram
- **Logging**: loguru (rotation) + structlog (JSON) + sentry (error tracking)
