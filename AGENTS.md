# CloudSentinel Agent Handoff

Last updated: 2026-11-25. Read this first in a new session.

## Repository

- Path: `C:\Users\RADZ\project io\FYP`
- Branch: `main`
- Push target: `kontoldemon/hanyakontolselamatkandunia` (personal repo). Use the `kontoldemon` remote / active GitHub account when needed.
- Latest pushed commit: `37d98d4` (Azure readiness guard tests).

## Current status

- Azure is the supported deployment target. The legacy DigitalOcean Phase 1 is retired and must not be used for new deployments.
- Phase 2 Azure code is implemented but **not deployed or tested**:
  - Event Grid -> Azure Function -> NSG deny rule with TTL.
  - Private ClickHouse VM, Key Vault private endpoint, Bicep, custom least-privilege NSG role.
  - Host firewall agent remains as the local/non-Azure fallback.
- Python suite: **522 passed, 2 skipped, coverage 99.02%**. GitHub CI is green; Azure readiness tests enforce NSG priority and private Key Vault/Blob settings.
- Dashboard: `npm run build` passes. `npm run lint` is very slow (timed out at 5 minutes with no error output).
- This Windows machine has no `az`, `bicep`, `func`, `docker`, or `bash`; Bicep, Function, and shell scripts are untested here.

## Outstanding work

1. **Dependency security:** Dependabot has **0 open alerts**; 55 historical alerts are fixed. `npm audit` and `pip-audit` are clean.
2. **Azure deployment:** run `az bicep build --file infra/main.bicep`, deploy, publish the Function, create the Event Grid subscription, and test a real NSG block. Block rules now use priority 100-199, before static allows at 200-230.
3. **Evidence:** MTTB is sensor-side, not full NSG enforcement time.
4. **Next code audit:** mobile pairing state/rate limits, remaining `admin_api.py` helper extraction, or the uncommitted dashboard settings refactor.
5. Dashboard WIP is uncommitted: settings/telemetry refactor. Build it before committing.

## Verification commands

```powershell
$env:PYTHONPATH="src"
python -m pytest src/cloudsentinel/tests -q -o addopts=""
cd dashboard
npm run build
```

Never commit `.env` or secrets. `.env` is ignored. Local demo credentials are local only.

## Recent work

Recent loops extracted the sensor session/server, HTTP/admin bootstrap, TTY/fingerprint/limits, API routers (health, events, sessions, analytics, blocks, LLM, auth, exposure), read-model queries, firewall helpers, mobile companion security (token-gated pairing, rate limits, shared state, real sensor dispatch), and fixed Azure NSG priority ordering so blocks precede allows. See `git log --oneline -25`.
