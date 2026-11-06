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
| Unit tests + coverage | `.github/workflows/ci.yml` | Python 3.12, Redis service | 362 passed, 96.07% (gate 96%) |
| SQL/static lint | `.github/workflows/ci.yml` | Ruff critical rules | passing |
| CodeQL | `.github/workflows/codeql.yml` | Python + JavaScript/TypeScript, `security-extended` | 0 open alerts (2026-11-06) |
| Python dependency audit | `.github/workflows/security.yml` | `pip-audit -r src/cloudsentinel/requirements.txt` | 0 known vulnerabilities |
| Node production audit | `.github/workflows/security.yml` | `npm audit --omit=dev --audit-level=high` | 0 vulnerabilities |
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
- **Eight moderate npm findings remain in development-only ESLint/TypeScript tooling.** They are not in the production dependency tree. The production audit is clean. The tooling is pinned to keep the existing lint rules and build stable.
- **`CLOUDSENTINEL_AUTH_SECRET` is required when auth is enabled.** If it is missing, the manual JWT backend generates a random per-process secret; tokens do not survive a restart. Set the secret in production.
- **Firewall actions must remain dry-run until the deployment host is verified.** Production mode requires `SOAR_FIREWALL_DRY_RUN=false` and a working firewall backend.

## Dependency policy

- Python and Node dependencies are pinned by lock/constraint files where possible.
- CI installs from `src/cloudsentinel/requirements.txt` and `dashboard/package-lock.json`.
- A new high/critical production vulnerability blocks the security workflow.
- Dependencies with no upstream fix are documented here with the affected scope and a migration plan.
