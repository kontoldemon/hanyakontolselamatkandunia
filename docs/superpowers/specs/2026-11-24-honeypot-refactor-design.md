# CloudSentinel Honeypot Refactor — Design and Staged Plan

Status: proposed. No production code has been changed by this document.
Date: 2026-11-24
Scope: the Python SSH honeypot, its command emulation, and the admin API in
`src/cloudsentinel/`.

## 1. Context

The current Python side works and is well tested, but it has become hard to
navigate and risky to change:

| File | Physical lines | Responsibility today |
|---|---:|---|
| `admin_api.py` | 2,321 | FastAPI app, 17 routes, auth, ClickHouse query helpers, firewall/exposure logic, LLM/AI routes |
| `server.py` | 1,358 | Connection limits, SSH fingerprinting, host-key loading, TTY logging, fuzz detection, AsyncSSH server/session, HTTP honeypot, admin bootstrap, CLI |
| `commands/base.py` | 983 | 60+ fake shell commands and the command implementations |
| `pipeline.py` | 691 | Event pipeline |
| `soar.py` | 600 | Response engine |

There is no single 3,000-line file in this repository. The concern is still
valid: `admin_api.py` plus `server.py` contain more than 3,600 lines and mix
several failure domains. The cost is not the line count itself; it is the
number of reasons a file changes, the closure coupling inside
`create_admin_app()`, and the difficulty of proving that attacker-facing code
cannot reach operator or host capabilities.

Baseline before the refactor:

- Python 3.12, AsyncSSH, FastAPI, Redis, ClickHouse, Docker.
- 512 tests pass, 2 skipped, coverage 99.14%; CI gate is 99%.
- Ruff critical lint, `compileall`, Docker build, and dashboard build are in CI.
- Azure phase 2 is in progress. The deployment is one sensor container plus
  managed Azure services; this refactor does not change that shape.

## 2. Problem statement

1. `server.py` is both a library and an entrypoint. Moving any part of it
   requires importing AsyncSSH/CLI concerns and makes the data plane hard to
   test in isolation.
2. `admin_api.create_admin_app()` defines 17 routes and 30+ helpers inside one
   function. Every route closes over `settings`, `pipeline`, `soar`, and
   `require_auth`. This is hard to read, hard to type, and easy to break.
3. The command emulator is one file. A change to a text filter and a change to
   SSH emulation land in the same review.
4. The trust boundary is implicit. `_run_command()` in the admin API executes a
   real subprocess; `commands/` must never do that for attacker input. This
   needs to be enforced by module direction, not by reviewer memory.
5. Test imports depend on the current file layout. A naive move breaks dozens
   of tests even when behaviour is unchanged.

## 3. Goals, non-goals, anti-goals

### Goals

- Make the attacker-facing data plane independent of the operator control plane.
- Give every module one reason to change.
- Keep the current public behaviour, endpoints, command output, config, and
  deployment shape.
- Make the security invariants enforceable with an import-boundary test.
- Preserve the existing test suite and 99% coverage gate after every slice.
- Reduce the largest production modules without a big-bang rewrite.

### Non-goals

- No new features, endpoints, commands, or Azure resources.
- No microservices, message-bus redesign, or database/schema changes.
- No async rewrite, framework replacement, or dependency injection framework.
- No cosmetic rename of every class.
- No split purely by line count.

### Anti-goals

- A refactor that changes a single byte of attacker-visible output.
- A refactor that lets `sensor/` import `admin_api`, `fastapi`, `subprocess`, or
  firewall code.
- Moving code without a matching test or without compatibility exports.
- One giant pull request that cannot be reviewed or reverted.
- Deleting the old module names before downstream imports are migrated.

## 4. Design principles

1. **Split by failure domain and trust boundary, not line count.** The data
   plane, control plane, and command emulation are different products that
   happen to ship together.
2. **One deployable.** Keep the current container and process model. Clear
   modules are enough; microservices are not.
3. **Dependency direction is the architecture.** `sensor` may import shared
   services and the command protocol. It may not import the admin API.
   `admin_api` may import shared services, but not the SSH session core.
   `server.py` is the composition root.
4. **Behaviour-preserving extraction.** Move code, add compatibility exports,
   run tests; do not redesign logic while moving it.
5. **Small, reversible slices.** One cohesive module per commit. Every slice
   must be independently revertable.
6. **The test suite is the specification.** Golden transcripts, endpoint auth
   tests, and architecture tests come before the dangerous moves.
7. **Honeypot safety before elegance.** The fake shell stays fake; real
   subprocess and firewall access remain operator-only.

## 5. Target architecture

```text
src/cloudsentinel/
  server.py                     # thin composition root + compatibility exports
  sensor/
    __init__.py
    limits.py                   # ConnectionLimiter
    fingerprint.py              # algo helpers, HASSH, JA4S, host-key loading
    tty.py                      # TTYLogger, detect_fuzz
    http.py                     # start_http_honeypot
    ssh.py                      # CloudSentinelSSHServer
    session.py                  # CloudSentinelSession
  api/
    __init__.py
    app.py                      # create_admin_app + middleware only
    context.py                  # ApiContext: settings, pipeline, soar, auth
    auth.py                     # require_auth factory
    queries.py                  # ClickHouse query helpers (current private helpers)
    firewall.py                 # admin-side real command/firewall helpers
    routers/
      __init__.py
      health.py                 # /healthz, /readiness, /metrics, /metrics/json
      sessions.py               # /sessions, /events, /truth-summary, /war-room-state
      analytics.py              # /stats, /attack-distribution, /attack-graph, /anomaly-stats
      blocks.py                 # /admin/block-ip
      exposure.py               # /admin/exposure
      llm.py                    # /llm/status, /llm/chat, /llm/config, /threat-summary
      auth_routes.py            # /auth/login
    bootstrap.py                # start_admin_api
  commands/
    __init__.py                 # Command, CommandAdapter, registry
    base.py                     # compatibility aggregator only
    identity.py                 # whoami, id, uname, ...
    files.py                    # cat, ls, find, stat, checksums, ...
    text.py                     # grep, cut, awk, sed, sort, uniq, wc, tr, head, tail
    shell.py                    # sh, bash, sudo, python, ...
    network.py                  # curl, wget, netstat, ...
    system.py                   # ps, top, crontab, ...
  pipeline.py, soar.py, vfs.py, vfs_agent.py, ...   # unchanged initially
```

Compatibility facades:

- `server.py` remains importable and re-exports `ConnectionLimiter`,
  `TTYLogger`, `CloudSentinelSSHServer`, `CloudSentinelSession`,
  `_split_algorithms`, `detect_fuzz`, `main`, and the other names currently
  imported by tests.
- `admin_api.py` remains importable and re-exports `create_admin_app` plus the
  private helpers tests use (`_as_int`, `_trim_replay_entries`,
  `_is_noise_event`, `_is_noise_text`, `_load_recent_events_from_clickhouse`,
  `_load_recent_sessions_from_clickhouse`). Those helpers move to
  `api/queries.py`; the facade is removed only after a deprecation release.
- `commands/base.py` remains the import site for command classes. Family
  modules are imported there; tests can migrate to `commands.text` etc. later.

Allowed dependencies:

| Layer | May import | Must not import directly |
|---|---|---|
| `sensor/` | config, commands, vfs, vfs_agent, pipeline, auth, metrics, hassh, geoip, mitre, anomaly, stream, and the approved shared services `sandbox`, `soar`, `http_server` | `api/`, `admin_api`, `fastapi`, `subprocess`, real command runners |
| `api/` | config, pipeline, soar, queries, shared response/firewall helpers | `sensor.ssh`, `sensor.session`, live connection objects |
| `commands/` | `commands` base types, text/path libraries | `sensor/`, `api/`, `subprocess`, network |
| `server.py` | `sensor/`, `api/`, config, CLI | business logic that belongs in either |

The rule is **direct imports**, not "zero transitive dependencies". A honeypot
session must be able to call the sandbox for payload detonation and the SOAR
engine for response; those are approved shared services. What must never happen
is the SSH transport or command emulator directly importing `subprocess`,
`os.system`, or `fastapi`.

Approved shared services and why they are exceptions:

- `sandbox.py`: gVisor/Docker detonation of untrusted payloads. It is isolated
  and resource-bounded; the session does not run payloads directly.
- `soar.py`: the response engine. Its local firewall fallback is an intentional
  honeypot response, not a shell for attacker input.
- `http_server.py`: the attacker-facing HTTP honeypot. `sensor/http.py` may
  import it; `sensor/http.py` must not import FastAPI directly for control
  routing.

The `sensor/` direct-import rule is the important one. It is the difference
between a honeypot and a remote shell.

## 6. Security invariants

These are non-negotiable and must be covered by tests:

1. No attacker input can execute an arbitrary host command. `sensor/` and
   `commands/` must not directly import `subprocess`, `os.system`, `pty`, or a
   real command runner. Approved exceptions are `sandbox.py` detonation and the
   `soar.py` response path, which are bounded shared services.
2. Real firewall execution is confined to response modules: `soar.py` and a
   single admin-side firewall helper behind `require_auth` plus the existing IP
   validation/allowlist. It is never reachable from command emulation or the
   SSH session parser.
3. The fake filesystem stays fake. No falling back to the real filesystem when
   a VFS path is missing.
4. Session state is per connection. No attacker-controlled state is shared
   across sessions except the bounded connection limiter and read-only command
   registry.
5. All attacker input is size-bounded: SSH line limit, TTY buffer, command
   output, replay entries.
6. Secrets never enter logs, replay data, LLM prompts, or dashboard responses.
   LLM API keys stay server-side and masked in the browser.
7. The admin API's real subprocess helper stays time-bounded and allowlisted.
8. The refactor does not weaken auth, rate limits, fuzz detection, or TLS.

## 7. Staged plan

Every slice ends with: focused tests, full `pytest` with the 99% gate,
`compileall`, ruff critical lint, dashboard build when dashboard files change,
and one commit. No slice changes endpoint paths, response shapes, command text,
or config keys.

### Slice 0 — Baseline and guardrails (no production moves)

- Add `tests/test_architecture.py` against the modules that exist at that
  point, then extend it as each new module lands:
  - import the relevant `cloudsentinel.sensor.*` modules;
  - assert `cloudsentinel.admin_api` and `fastapi` are not imported directly by
    those modules;
  - assert `subprocess`/`os.system` are not imported directly by
    `commands/*` or the SSH transport/session modules;
  - allowlist the approved shared services documented in §5.
- Add a golden transcript test: `whoami`, `id`, a pipe
  (`cat /etc/passwd | grep root | head -n 1`), an awk condition, and `exit`.
- Confirm baseline `512 passed, 2 skipped, 99.14%`.
- Acceptance: no production file changes; new tests pass; no coverage drop.

Test migration policy for the whole project:

- Import paths and monkeypatch targets may be mechanically repointed to the
  module that now owns the function.
- Assertions, test names, and behaviour must not change.
- Do not add call-time compatibility shims solely to preserve a string patch
  target. Re-exports exist for import compatibility, not to keep monkeypatching
  the old module alive.
- No test may be deleted to satisfy the coverage gate; add focused tests
  instead.

### Slice 1 — `sensor/limits.py`

Move `ConnectionLimiter` (currently `server.py`) unchanged.

- `server.py`: `from .sensor.limits import ConnectionLimiter` and re-export.
- Add `tests/test_limits.py` for per-IP/total/window/eviction behaviour.
- Acceptance: existing limiter tests unchanged; server line count drops; no
  behaviour change.

### Slice 2 — `sensor/fingerprint.py`

Move `_split_algorithms`, `_decode_alg_list`, `extract_hassh`, `extract_ja4s`,
and the host-key loaders unchanged. Re-export from `server.py` (including
`_split_algorithms`, which tests import).

- Add focused tests for algorithm parsing and HASSH/JA4S edge cases if the
  existing coverage is indirect.
- Acceptance: fingerprint tests pass; no AsyncSSH import at module import time
  if avoidable; no change to connection handling.

### Slice 3 — `sensor/tty.py`

Move `TTYLogger` and `detect_fuzz`. Re-export from `server.py`.

- Add tests for buffer caps, redaction, and fuzz thresholds.
- Acceptance: `TTYLogger` and `detect_fuzz` imports remain valid; replay output
  unchanged.

### Slice 4 — `sensor/http.py`, `api/bootstrap.py`

- Move `start_http_honeypot` to `sensor/http.py`.
- Move `start_admin_api` to `api/bootstrap.py`.
- `server.py` keeps thin wrappers/re-exports.
- Acceptance: HTTP honeypot tests pass; admin startup tests pass; no port or
  route changes.

### Slice 5 — SSH server/session split (highest-risk data-plane move)

- Move `CloudSentinelSSHServer` to `sensor/ssh.py`.
- Move `CloudSentinelSession` to `sensor/session.py`.
- Keep `server.py` as the composition root and compatibility export.
- Add a transcript test that runs the session through a fake protocol.
- Acceptance: all session/auth/fuzz/TTY tests pass; `server.py` is an entrypoint
  of roughly 150-250 lines; no **direct** real-command import appears in the
  sensor modules. `vfs_agent`, `sandbox`, `soar`, and `http_server` remain
  approved shared dependencies.
- Repoint monkeypatch targets such as `cloudsentinel.server.extract_hassh` and
  `cloudsentinel.server.geo_enrich` to the new owner modules; assertions stay
  the same.

### Slice 6 — Admin API decomposition

- 6a: move ClickHouse query helpers to `api/queries.py`; `admin_api.py`
  re-exports the six helpers imported by tests.
- 6b: build `ApiContext` and `make_auth_dependency()`; extract the LLM router
  and health/metrics router first (small, recent).
- 6c: extract sessions/events/truth/war-room, then analytics.
- 6d: extract blocks/exposure last; these touch real firewall behaviour and
  need the most endpoint tests. Move the admin-side real command runner and
  manual block helpers into `api/firewall.py` at the same time. Tests that
  patch `cloudsentinel.admin_api._run_command`, `_http_json`, `_now_ms`,
  `_enrichment_for_ip`, `_load_war_room_evidence_from_clickhouse`, or
  `_toggle_exposure_digitalocean` must be repointed to the owning module; the
  assertions do not change.
- 6e: `api/app.py` assembles routers; `admin_api.py` becomes a compatibility
  facade.
- Acceptance for every router: same path, same auth dependency, same response
  shape; unauthenticated requests still 401; endpoint assertions unchanged.
- Use router factories that receive `ApiContext`; avoid a DI container and
  avoid global mutable settings. This keeps the old closures explicit.
- Do not use a call-time proxy through `admin_api` to keep old monkeypatch
  targets alive. Repoint the tests instead.

### Slice 7 — Command modules

- Split `commands/base.py` by family; keep a small aggregator that imports the
  modules and preserves `commands` and the class names.
- Start with text filters (`text.py`) because they have the most tests, then
  files, identity, network, shell, system.
- Acceptance: every command test imports from the same place; the registry
  contains the same keys; shell transcripts are byte-identical.

### Slice 8 — Cleanup

- Remove compatibility facades only after a release and after grep confirms no
  in-repo imports remain.
- Update `docs/ARCHITECTURE.md` component map and the developer guide.
- Optional: add a `docs/MODULE_MAP.md` generated from the final tree.

## 8. Test strategy

- **Golden transcripts** are the primary regression test for the fake shell.
  They must run through the real session dispatch path, not by calling each
  command class directly.
- **Endpoint matrix**: for each extracted router, unauthenticated = 401 and
  authenticated = the existing response. The auth dependency must not be lost
  during extraction.
- **Architecture tests** enforce the dependency table. They are cheap and catch
  the exact mistake this refactor is meant to prevent.
- **Property/fuzz tests** for line length, escape handling, malformed pipes,
  huge fields, and malformed JSON. Hypothesis is already a dev dependency.
- **Limits and TTY tests** assert caps, eviction, and redaction.
- **No real I/O in sensor tests**: no outbound network, no real firewall, no
  host filesystem.
- Coverage remains at or above 99%; any new module has tests for its error and
  empty-input paths.

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Circular imports after moving classes | dependency table, `server.py` composition root, import smoke test |
| Tests break because they import from `server`/`admin_api` | compatibility re-exports; keep old names until cleanup |
| Tests patch old module paths (for example `admin_api._run_command`) | repoint patch targets to the owning module; keep assertions; do not add call-time shims |
| Behaviour drift in the fake shell | golden transcripts for every slice |
| Coverage drops below 99% | read `--cov-report=term-missing` after every slice; add focused tests before moving on |
| Admin auth accidentally dropped during router extraction | endpoint auth matrix; one router per commit |
| Sensor gains a direct real-command path | architecture test; code review checklist; direct `subprocess` forbidden in sensor/commands; sandbox/soar exceptions documented |
| Firewall execution leaks into the session layer | move admin execution to `api/firewall.py`; SOAR remains the only other response executor; architecture test |
| Refactor delays Azure work | slices 0-4 are safe to do before deploy; Slice 5+ is post-deploy or a branch with a rollback tag |
| Large review burden | one slice, one commit, no unrelated formatting |

## 10. Deployment sequencing

- Keep the current Docker image and entrypoint. `server.py` remains the
  composition root, so the Dockerfile does not change.
- The safe pure modules (Slices 0-4) can merge before the Azure smoke test.
- Do not move the SSH server/session or the block/exposure routes on the same
  day as the first Azure deployment. Deploy first, observe, then continue.
- No Bicep, Function, or dashboard API changes are required for this refactor.

## 11. Definition of done

- `server.py`: thin entrypoint, target under 250 lines.
- `admin_api.py`: compatibility facade, target under 250 lines.
- `commands/base.py`: aggregator, target under 200 lines.
- No production Python file over 800 lines except a future generated file.
- `sensor/` has no direct import of `admin_api`, `fastapi`, or `subprocess`;
  approved shared services are allowlisted.
- Existing import paths in tests still work; monkeypatch targets are repointed
  where ownership moved. No assertions were weakened.
- 99% coverage gate passes; 512+ tests pass.
- Ruff critical lint, compileall, Docker build, and dashboard build pass.
- `docs/ARCHITECTURE.md` reflects the new module map.

## 12. Decisions and assumptions

1. Router style: use router factories with an `ApiContext` dataclass. This is
   the lowest-risk way to preserve the current closures without a global
   dependency container.
2. Query helpers: move them to `api/queries.py` in one slice, with the
   `admin_api` facade, rather than mixing moves with route extraction.
3. Command split boundaries: use text/files/identity/network/shell/system.
   Do not split every command into its own file.
4. Test contract: test import paths and monkeypatch targets may be mechanically
   repointed; assertions and names stay. If preserving untouched test source is
   a hard requirement, stop and revise this plan before Slice 5; otherwise the
   call-time shim would invert the dependency direction this design is trying
   to establish.
5. Sensor boundary: the architecture test checks **direct imports**. Approved
   shared services (`sandbox`, `soar`, `http_server`) are not violations; the
   session may use them. The SSH transport and command emulator must not
   directly run host commands.
6. Firewall boundary: real firewall execution belongs to the response layer.
   `soar.py` remains the sensor-side response executor; the admin side gets a
   single `api/firewall.py` helper. Both are unreachable from command
   emulation. The old wording "only admin_api.py" is not accurate and is not a
   target.
7. Facades: keep `server.py`, `admin_api.py`, and `commands/base.py` import
   facades for one release; do not delete them in the move PR.
8. Test additions: no test may be deleted or weakened to hit coverage; add
   focused tests for new modules and error paths.

## 13. Builder-check resolutions

The initial design was reviewed by a fresh builder. Three questions mattered:

- **Monkeypatch-by-string tests**: resolved by Decision 4. Repoint the tests;
  no compatibility shim that keeps old call-time patches alive.
- **Transitive sensor imports (`sandbox`, `soar`)**: resolved by Decision 5.
  The boundary is direct imports, with explicit approved shared services.
- **"Only admin_api runs firewall commands" was already false**: resolved by
  Decision 6. Use a response-layer rule and an admin-side firewall helper, not
  a literal single-file rule.

No production code is written until this document is approved.
