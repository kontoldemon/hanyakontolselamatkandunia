# Security Policy

CloudSentinel is a defensive honeypot. Treat all captured attacker input as untrusted.

## Reporting a vulnerability

Do not open a public issue for a security problem. Contact the repository owner privately with:

- the affected file or component
- steps to reproduce
- impact
- a suggested fix, if known

Do not test against systems you do not own. The local demo and CI are the supported test targets.

## Automated quality gates

| Check | Workflow | Scope | Current result |
|---|---|---|---|
| Unit tests + coverage | `.github/workflows/ci.yml` | Python 3.12, Redis service | 487 passed, 99.27% (gate 99%) |
| SQL/static lint | `.github/workflows/ci.yml` | Ruff critical rules | passing |
| CodeQL | `.github/workflows/codeql.yml` | Python + JavaScript/TypeScript, `security-extended` | 0 open alerts (2026-11-06) |
| Python dependency audit | `.github/workflows/security.yml` | `pip-audit -r src/cloudsentinel/requirements.txt` | 0 known vulnerabilities |
| Node production audit | `.github/workflows/security.yml` | `npm audit --omit=dev --audit-level=high` | 0 vulnerabilities |
| Node full audit | `.github/workflows/security.yml` | `npm audit --audit-level=moderate` | 0 vulnerabilities |
| Bandit | `.github/workflows/security.yml` | Python source, high severity | 0 high-severity findings |
| Secret scan | manual / GitHub | tracked files only | no tracked `.env`, key, or PEM files |

CodeQL results are published under **Security > Code scanning**. Dependency and Bandit reports are uploaded as workflow artifacts.

## Local audit commands

```powershell
# Python dependencies
python -m pip install pip-audit
python -m pip_audit -r src/cloudsentinel/requirements.txt

# Python static analysis
python -m pip install bandit
python -m bandit -r src/cloudsentinel -x src/cloudsentinel/tests -lll

# Dashboard production dependencies
cd dashboard
npm audit --omit=dev --audit-level=high
```

## Accepted risks and triage

- **Honeypot listeners bind to all interfaces by default.** This is intentional for the sensor profile. The local demo overrides it to `127.0.0.1`.
- **Bandit medium findings** cover deliberate honeypot behavior: fake `/tmp` paths, permissive listener defaults, local trusted VFS pickle loading, and parameterized ClickHouse query fragments built from constants. They are reported but do not fail CI. High-severity findings do fail CI.
- **The nested `minimatch` used by `@typescript-eslint/typescript-estree` is pinned to `11.0.5`.** This clears the last dev-only advisory while keeping lint and build passing.
- **`CLOUDSENTINEL_AUTH_SECRET` is required when auth is enabled.** `load_settings` validates this and refuses to start in production without it.
- **The admin API fails closed.** With no `ADMIN_TOKEN` and no JWT auth, protected endpoints return `503`. Compose also refuses to start without `ADMIN_TOKEN`. The Prometheus `/metrics` endpoint stays unauthenticated and must remain private; nginx restricts it and Compose binds the API to localhost.
- **The public stream is read-only and unauthenticated.** Captured passwords are removed before emit; other attacker commands remain visible.
- **Dashboard OTP delivery fails closed in production.** A missing `RESEND_API_KEY`/`ADMIN_EMAIL` or a failed email send returns `503`. The OTP is logged only in development.
- **Firewall actions must remain dry-run until the deployment host is verified.** Production mode requires `SOAR_FIREWALL_DRY_RUN=false` and a working Event Grid/Function path or host agent.
- **The Azure Function has a custom NSG rule operator role scoped to one NSG.** It validates public, non-allowlisted IPs and creates rules with a TTL; the storage queue deletes the rule, and a five-minute timer cleanup handles lost queue messages. The Event Grid topic key is stored in Key Vault and copied to the sensor through `load_secrets.sh`.
- **Key Vault public access is disabled.** The sensor reads secrets through a private endpoint and the `privatelink.vaultcore.azure.net` DNS zone linked to the VNet.
- **Redis and ClickHouse use generated passwords on the deployment paths.** NATS uses a compose default password; override `NATS_PASSWORD` for shared environments. All services stay on a private network.

## Dependency policy

- Python and Node dependencies are pinned by lock/constraint files where possible.
- CI installs from `src/cloudsentinel/requirements.txt` and `dashboard/package-lock.json`.
- A new high/critical production vulnerability blocks the security workflow.
- Dependencies with no upstream fix are documented here with the affected scope and a migration plan.
