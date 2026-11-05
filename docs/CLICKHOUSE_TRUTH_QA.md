# ClickHouse Truth QA Runbook

This runbook verifies dashboard telemetry truth after deploy.

## Preconditions
- Target URL reachable (default: `https://cloudsentinel.zis3c.dev`).
- Admin API token configured in deployment.
- Optional direct ClickHouse SSH access for numeric compare.
- Active freshness window is `90 seconds` for war-room/session live state.

## Automated Audit
Run from repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\dashboard\qa\truth_audit.ps1
```

No-blocker full run (tries dashboard if auth provided, always tries sensor via SSH token fetch):

```powershell
powershell -ExecutionPolicy Bypass -File .\dashboard\qa\truth_audit_full.ps1
```

NPM equivalent:

```powershell
npm -C .\dashboard run qa:truth:full
```

If dashboard is auth-gated, pass active session cookie:

```powershell
powershell -ExecutionPolicy Bypass -File .\dashboard\qa\truth_audit.ps1 `
  -AuthCookie "cloudsentinel_session=YOUR_SESSION_TOKEN"
```

If you use bearer auth in front proxy:

```powershell
powershell -ExecutionPolicy Bypass -File .\dashboard\qa\truth_audit.ps1 `
  -AuthBearer "YOUR_BEARER_TOKEN"
```

Optional with direct ClickHouse compare:

```powershell
powershell -ExecutionPolicy Bypass -File .\dashboard\qa\truth_audit.ps1 `
  -SshHost "YOUR_HOST" `
  -SshPort 22222 `
  -SshUser "root" `
  -SshKey "C:\path\key" `
  -ClickHouseDb "default" `
  -ClickHouseTable "cloudsentinel_events"
```

Output JSON artifact is written into `artifacts/`.

Direct sensor audit (when dashboard cookie auth blocks terminal checks):

```powershell
$token = ssh -p 22222 root@188.166.184.42 "cat /root/cloudsentinel-admin-token"
powershell -ExecutionPolicy Bypass -File .\dashboard\qa\truth_audit_sensor.ps1 `
  -BaseUrl "https://188.166.184.42.sslip.io" `
  -BearerToken $token
```

## Manual Smoke (Phase-by-Phase)
1. Phase 1 API
- Check `/api/cloudsentinel/events`, `/summary`, `/operations`, `/analytics` all return:
  - `source`
  - `authoritative`
  - `sourceBreakdown`
- Confirm `summary.source` is `clickhouse` in strict mode.

2. Phase 2 War Room
- Open War Room page.
- Confirm telemetry badge shows `Authoritative` and source `clickhouse`.
- Confirm live feed and map update without stale phantom rows.

3. Phase 3 Sessions and Replay
- Open Sessions page.
- Confirm each session shows source badge.
- Confirm no `memory` source rows in strict mode.
- Confirm replay lines have no `cloudsentinel.*` noise entries.

4. Phase 4 Intelligence
- Open Intelligence page.
- Confirm source badge shows telemetry truth state.
- Validate KPI bounds:
  - `Avg Risk` in `[0,100]`
  - `Block Rate` in `[0,100]`
- Confirm timeline uses analytics endpoint and remains consistent with selected window.

5. Phase 5 Settings and AI
- Open Settings page.
- Confirm Telemetry Truth card separated from Ops Health.
- Open AI panel and confirm label states LLM output is analysis only (not telemetry source).

## Regression Focus
- Stale active IP rows.
- Session replay missing while session appears active.
- Inflated all-time KPI.
- Impossible block rate (>100).
- Auth-expiry UI state inconsistency.
