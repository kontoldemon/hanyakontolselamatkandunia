# CloudSentinel Agent Handoff

Last updated: 2026-11-28. Read this first in a new session.

## Repository

- Path: `C:\Users\RADZ\project io\FYP`
- Branch: `main`
- Push target: `kontoldemon/hanyakontolselamatkandunia` (personal repo). Use the `kontoldemon` remote / active GitHub account when needed.
- Latest pushed commit: `aa43f71` (staging block truth + stream auth + UI; see `git log` for newer).
- Detailed docs: `docs/ARCHITECTURE.md` (system), `docs/MOBILE.md` (Android), `docs/DEPLOY.md` (Azure), `docs/INDEX.md` (map).

## FYP report

- Report writing guide: `docs/fyp-report-guide.md`.
- Project skill: `.opencode/skills/fyp-report/SKILL.md` (reads the guide).
- Follow the guide when drafting or checking the report. Do not invent citations, data, or results.

## Current status

- Azure is the supported deployment target. The legacy DigitalOcean Phase 1 is retired and must not be used for new deployments.
- Phase 2 Azure code is implemented but **not deployed or tested**:
  - Event Grid -> Azure Function -> NSG deny rule with TTL.
  - Private ClickHouse VM, Key Vault private endpoint, Bicep, custom least-privilege NSG role.
  - Host firewall agent remains as the local/non-Azure fallback.
- Python suite: **533 passed, 2 skipped, coverage 99.02%** (local WIP snapshot, 2026-11-26; the 99% gate passes). CI at `de3ddfb`: **531 passed, 99.32%**. Ruff critical, bandit high, `npm audit`, and `pip-audit` are clean; full `npm run lint` exits 0.
- Dead-code cleanup (2026-11-26): removed unused `SOARScheduler` (+ tests), unused CLI/sandbox imports, the dead `data_dir` parameter on `VirtualFileSystem.build_default`, `LiveStream.emit_coro`, and the test-only modules `attack_graph.py`, `_secrets.py`, `shell.py`, `exceptions.py` (+ their tests). Also removed legacy `EventPipeline.emit_login/emit_command/reconnect`, `EventEnvelope.to_clickhouse_row`, session-score annotation, `ConnectionLimiter.acquire/release`, legacy config getters, `geoip.enrich_async`, `HASSHDNA.add_intel`, `VFSAgent._parse_args`, and the `hvac`/`networkx` requirements. Docs updated (`PROJECT_STRUCTURE.md`, `ARCHITECTURE.md`). Dashboard dead exports de-exported and the unused direct `eslint-plugin-react-hooks` devDependency removed; knip reports only registered `public/sw.js`. Added `tests/test_command_coverage.py` to keep production command branches covered after removing shell tests.
- Dashboard: `npm run build` passes and full `npm run lint` now exits 0 (2026-11-26; earlier it timed out).
- Android: `mobile-android\gradlew.bat :app:assembleDebug` and `:app:assembleRelease` (unsigned) pass with local JDK 21 + SDK (2026-11-26); signing/device pass still unverified.
- Live admin API smoke (2026-11-26): uvicorn on `127.0.0.1:8099` returned `healthz=200`, unauth `401`, persisted runtime config (`full` -> `restricted`), `/decoys` reflected the change, `/llm/config` returned the live provider, and `/docs` + `/openapi.json` returned 404 with docs disabled.
- Live Socket.io smoke (2026-11-26): token-authenticated client received the event with `password` redacted; wrong token now raises `ConnectionRefusedError` so the client reports `connected=False` and receives nothing. The dashboard socket stops reconnecting on an "unauthorized" error and falls back to HTTP polling.
- Live deployment audit (2026-11-26): `https://dashboard-six-mu-20.vercel.app` still serves the **pre-`de3ddfb` CSP** and `Access-Control-Allow-Origin: *`; `https://cloudsentinel.zis3c.dev` returns **NXDOMAIN**. Dead-domain defaults were removed from `deploy.sh`, `vercel.json`, `stream.py`, and the QA runbook; redeploy Vercel after wiring it to the current repo.
- Dashboard post-login `next` redirect now validates the resolved origin, blocking backslash/absolute external redirects.
- Mobile exposure now uses the shared firewall toggle (`apply_exposure_toggle`), with iptables cooldown/rollback semantics; `/mobile/runtime-controls` and `/mobile/policy` are covered by tests. Mobile exposure still targets host iptables, not the Azure NSG.
- Dashboard wiring (2026-11-26): settings persist to the sensor via `GET/POST /runtime-config` + `GET /decoys`; LLM config is a real proxy (`GET/POST /llm/config`). VFS depth, canary keys, HASSH drop, SOAR trigger/runtime, and LLM provider/model/limits apply live. Fake MTTB/risk/port values, hardcoded decoy inventory, synthetic anomaly trend, Next.js mobile fallbacks, and dry-run counting as a real block were removed. `GET /anomaly-stats` reports real detector state; `/readiness` exposes real port/deception config. Events cap: `CLOUDSENTINEL_EVENTS_MAX_LIMIT` (default 20000, max 50000). Dashboard polls are deduplicated across hooks. DNS and HTTP honeypot events now reach the pipeline and live stream. The Socket.io stream supports `STREAM_AUTH_TOKEN` (sensor) matched by `NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_TOKEN` (dashboard); an empty token keeps the stream open. Mobile alert state now round-trips camelCase fields (riskScore/mitreId/timestampMs) instead of resetting them on reload. ClickHouse reads now run via `asyncio.to_thread` wrappers so admin handlers no longer block the sensor loop. VFS routes Groq/Anthropic through litellm and no longer reuses the primary key for fallback models. The AI chat approve action no longer depends on `setMessages` side effects. `/docs` + `/openapi.json` are opt-in via `CLOUDSENTINEL_ENABLE_DOCS=1`. HTTP/DNS events are geo-enriched and carry `input`/`reason`; DNS/HTTP now reach ClickHouse with meaningful rows. Prometheus `events_total` and uptime are wired (`EventPipeline.emit` + `_start_metrics`). The mobile pairing panel defaults to the configured sensor URL (`NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_URL` / `CLOUDSENTINEL_ADMIN_API_URL`) instead of the dashboard hostname. Persisted runtime config is re-validated on load; invalid sections fall back to defaults. Changed-file eslint is clean (0 errors/warnings). HASSH DNA had a malformed entry (missing brace after "Ansible SSH") that nested 17 botnet variants under one key, so most critical signatures were unreachable; fixed, `_KNOWN` now has 33 top-level signatures and `mypy hassh.py` is clean. HASSH now has no duplicate keys (guarded by an AST test) and all entries are flat top-level records. Mobile `/runtime-controls` deception level + HASSH action now persist through the runtime config store; `soar_dry_run` still applies in-memory only. Android API models were checked field-by-field against the mobile router responses and match. Deployment remains blocked locally: no Vercel credentials, `az`, `bicep`, or Docker.
- This Windows machine has no `az`, `bicep`, `func`, `docker`, or `bash`; Bicep, Function, and shell scripts are untested here.

## Staging deployment (2026-11-28)

- Azure: `cloudsentinel-rg` in **eastasia** (the student subscription policy only allows `malaysiawest`, `eastasia`, `indonesiacentral`, `japaneast`, `indiasouthcentral`; Malaysia West B-series are blocked for this subscription).
- Sensor: `cloudsentinel-4nxdgq72ncekc.eastasia.cloudapp.azure.com` / `20.205.118.45`; **`Standard_B2als_v2` (4 GB)** with `MemoryMax=3072M`. ClickHouse `10.20.2.4` on `B2als_v2`.
- Dashboard: `https://cloudsentinel.zis3c.dev` (Vercel project `dashboard`, Cloudflare CNAME `cname.vercel-dns.com`, cert valid). Deploy with `vercel --prod --yes --archive=tgz` from the repo root; `.vercelignore` limits the upload to the dashboard.
- Auth: admin token `/root/cloudsentinel-admin-token`; stream token `/root/cloudsentinel-stream-token`; `STREAM_AUTH_TOKEN` is required and must match Vercel `NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_TOKEN`. `deploy.sh` reuses the saved stream token and generates one only when absent.
- Azure path verified: Event Grid -> Function -> NSG deny rule (priority 100) + queue unblock; timer cleanup fallback. Manual dashboard/mobile blocks are persisted to ClickHouse (`cloudsentinel.block.manual`), so the truth summary/MTTB reflects them (117.35 ms). Active blocks read `soar:block:*` Redis TTL keys.
- UI fixes: latency thresholds (green <250 ms), light/dark stream console, block-rate one-decimal formatting, `Port 22/TCP -> 2222` label, modal/panel z-index above sidebar/AI, intelligence event fetch capped at 5,000. Settings dropdowns portal at z-500 so they render above cards; the API key input is prefilled from `/llm/config` with an eye toggle to reveal it (dashboard session required).
- Android: pairing default is the staging FQDN; debug APK and **signed** release APK build. Keystore `mobile-android/keystore/cloudsentinel-release.jks` and `keystore.properties` are gitignored; back them up. On-device install is still manual.
- HASSH: only clients that send an SSH version/KEX produce HASSH. TCP port scans show `TCP probe` and no HASSH by design. A controlled full SSH session captured `b6877c001729f21db804a5f505029b82`. HASSH is now also captured in `connection_lost` when the client completed KEX but never authenticated (for example `ssh-keyscan`/Nmap), and port 2222 is public so KEX-only scanners hit it directly; an external `SSH-2.0-Nmap-SSH2-Hostkey` scanner produced `84f27d3e3d5d2ca00d2994db56d96cdb` within minutes. The server banner no longer doubles the `SSH-2.0-` prefix.
- LLM: OpenCode Go service account `cloudsentinel-staging` (Models only) at `https://opencode.ai/inference/go/openai/v1`, model `openai/deepseek-v4.1-flash`. `threat_reporter` now passes `LLM_API_KEY`/`LLM_ENDPOINT` (plus `x-opencode-session`) to litellm; `/llm/chat` and the dashboard Copilot are verified. The key is persisted in `/opt/cloudsentinel/var/runtime_config.json` (0600) so it survives reboots, and `/llm/config` returns it to the authenticated settings page, which prefills the API key input; that endpoint is behind the dashboard session login. DeepSeek V4.1 Flash is a reasoning model, so VFS calls also send `extra_body.reasoning_effort=none` and `max_tokens=1600`; without that, dynamic terminal output came back empty. Free Go models (`beam-free`, `hy4-flash-free`, `hungerg-free`) return 403 outside OpenCode, so only the paid Go model works from the sensor. The direct DeepSeek key had no balance; the `botlab` key is not the Go key. Rotate the service account key if it was exposed in chat.
- Attack surface (2026-11-28): NSG rules 240 (UDP 53), 250 (TCP 8081) and 260 (TCP 2222) are applied via the Azure CLI (personal account, Azure for Students). Public now: 22→2222 SSH honeypot, 80/443 Caddy admin, UDP 53→5353 DNS honeypot, TCP 8081 HTTP honeypot, TCP 2222 SSH honeypot direct. Verified externally: DNS `example.com` returns `10.0.0.4`, HTTP `/wp-login.php` returns 200 and `/.env` returns fake creds, and an Nmap SSH scanner produced HASSH. The DNS honeypot listens on UDP 5353 because 53 conflicts with systemd-resolved; the HTTP honeypot uses uvicorn because the installed granian has no `serve`. UFW allows 5353/udp and 8081/tcp. Most external scanners only TCP-connect; HASSH needs a KEX. DigitalOcean felt louder because it exposed more ports on an older, heavily scanned IP.
- Exposure toggle now works: the sensor unit needs `/run` in `ReadWritePaths` plus an `ExecStartPre` that gives `cloudsentinel` ownership of `/run/xtables.lock`; resume also checks every iptables backend instead of treating the first "not found" as already open (the live host has both legacy and nft tables). Pause closes 22 and resume reopens it (verified).
- Settings live checks (2026-11-28): deception level/canary (full 8 decoys vs restricted 1, canary file disappears), HASSH action/threshold and SOAR trigger/execution round-trip and persist, decoys reflect the level, LLM chat/threat summary work, VFS budget stops after the configured hourly limit, exposure pause/resume works. HASSH live drop and SOAR host auto-block were not re-run (would need a known malicious fingerprint / risk locking out the admin IP); their unit tests and the earlier manual/Azure block path cover them. Mobile pairing works through the dashboard (`serverUrl` comes from `NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_URL`/`CLOUDSENTINEL_ADMIN_API_URL`); the paired device has no FCM token, so test alerts are `local_sync_only` until the app registers one.
- Telemetry audit (2026-11-28): every card maps to a live sensor endpoint — `/readiness` (engine/bus/store/stream), `/metrics/json` (MTTB, sessions, blocks, commands, auth counters), `/decoys` (8 real decoy files), measured `/operations` upstream latencies, and the Socket.IO telemetry stream. Verified counters increment (auth success 1→2, publickey failure 0→1, commands 14→15, connections 6→7). Fixed misleading labels: "Redis / NATS" → "Redis Streams" (NATS is disabled), "Active Hash" → "ClickHouse Token" (insert dedup token), "Ingress Port" → "Honeypot Port".
- Remaining: dynamic admin IP for 22222, on-device APK install, Vercel Git auto-deploy vs CLI drift.

## Outstanding work

1. **Dependency security:** Dependabot has **0 open alerts**; 55 historical alerts are fixed. `npm audit` and `pip-audit` are clean.
2. **Azure deployment:** run `az bicep build --file infra/main.bicep`, deploy, publish the Function, create the Event Grid subscription, and test a real NSG block. Block rules now use priority 100-199, before static allows at 200-230.
3. **Evidence:** MTTB is sensor-side, not full NSG enforcement time.
4. **Live stream auth:** code is wired (`STREAM_AUTH_TOKEN` -> `NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_TOKEN`), but deployment must set both or the stream stays open on port 3001. Events are redacted; treat the dashboard token as a read credential.
5. **Next code audit:** remaining `admin_api.py` helper extraction and unused test-only modules (`shell.py`, `_secrets.py`, `attack_graph.py`, benchmark scripts).
6. Dashboard WIP is uncommitted: settings/telemetry/wiring refactor. Build and run the Python suite before committing.
7. **Live deployment drift:** current Vercel deployment is stale; redeploy it from the current repo and decide whether to restore a custom domain. Live headers are not final until then.

## Verification commands

```powershell
$env:PYTHONPATH="src"
python -m pytest src/cloudsentinel/tests -q -o addopts="-n auto --cov=cloudsentinel --cov-report=term --cov-fail-under=99"
cd dashboard
npm run build
```

Never commit `.env` or secrets. `.env` is ignored. Local demo credentials are local only.

## Recent work

Recent loops extracted the sensor session/server, HTTP/admin bootstrap, TTY/fingerprint/limits, API routers (health, events, sessions, analytics, blocks, LLM, auth, exposure), read-model queries, firewall helpers, mobile companion security (token-gated pairing, rate limits, shared state, real sensor dispatch), and fixed Azure NSG priority ordering so blocks precede allows. The 2026-11-26 loop wired dashboard settings/decoys/LLM/anomaly to the sensor, made mobile endpoints fail honestly, stopped dry-run blocks from inflating truth metrics, added optional Socket.io stream auth, and fixed mobile alert state round-tripping. See `git log --oneline -25`.
