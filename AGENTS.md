# CloudSentinel Agent Handoff

Last updated: 2026-11-23. Read this first in a new session.

## Repository

- Path: `C:\Users\RADZ\project io\FYP`
- Branch: `main`
- Push target: `kontoldemon/hanyakontolselamatkandunia` (personal repo). Use the `kontoldemon` remote / active GitHub account when needed.
- Latest pushed commit: `09e5960` (DigitalOcean exposure provider removed).

## Current status

- Azure is the supported deployment target. The legacy DigitalOcean Phase 1 is retired and must not be used for new deployments.
- Phase 2 Azure code is implemented but **not deployed or tested**:
  - Event Grid -> Azure Function -> NSG deny rule with TTL.
  - Private ClickHouse VM, Key Vault private endpoint, Bicep, custom least-privilege NSG role.
  - Host firewall agent remains as the local/non-Azure fallback.
- Python suite: **520 passed, 2 skipped, coverage 99.01%**. GitHub CI: 522 passed, 99.32%.
- Dashboard: `npm run build` passes. `npm run lint` is very slow (timed out at 5 minutes with no error output).
- This Windows machine has no `az`, `bicep`, `func`, `docker`, or `bash`; Bicep, Function, and shell scripts are untested here.

## Outstanding work

1. **Dependency security:** GitHub Dependabot reports **55 vulnerabilities** on the default branch after the push (5 critical, 29 high, 19 moderate, 2 low). Next loop should audit and upgrade dependencies and update `SECURITY.md`, which still says 0.
2. **Azure deployment:** run `az bicep build --file infra/main.bicep`, deploy, publish the Function, create the Event Grid subscription, and test a real NSG block.
3. **Evidence:** MTTB is sensor-side, not full NSG enforcement time.
4. **Next code audit:** `shell.py` pipe/redirect behavior and VFS command handling.
5. Keep the redesigned dashboard component folders; they are committed in `d662aa6`.

## Verification commands

```powershell
$env:PYTHONPATH="src"
python -m pytest src/cloudsentinel/tests -q -o addopts=""
cd dashboard
npm run build
```

Never commit `.env` or secrets. `.env` is ignored. Local demo credentials are local only.

## Recent work

The last sessions performed a series of audit/fix loops: admin auth fail-closed, host-agent blocking, stream password redaction, SSH/port exposure, TTL handling, OTP fail-closed, Vault path fix, backup auth/retention, NATS/Redis/ClickHouse auth, memory caps, ClickHouse dedup, and anomaly-model training. See `git log --oneline -25`.
