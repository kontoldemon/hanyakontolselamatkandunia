# CloudSentinel Skill File v3.0

> Project: CloudSentinel - Event-Driven SSH Deception and SOAR
> Author: Radzi bin Zamri (I24107504)
> Supervisor: Sir Helmy Hanyff Bin Hairudin Ruzaili
> Faculty: FPTM, Universiti Sultan Azlan Shah (USAS)
> Type: Final Year Project (FYP)
> Last Updated: 2026-06-01
> Current Delivery State: Phase 1 deployed and validated on 2026-05-26; droplet now offline. Phase 2 prepared for AWS migration.

---

## 1. Project Metadata

| Field | Value |
|---|---|
| System Name | CloudSentinel |
| Domain | Cybersecurity, Honeypot, Active Deception, SOAR |
| Primary Threat Focus | SSH botnet campaigns on port 22 |
| Deployment Strategy | Two-phase: DigitalOcean (Dev and MVP) then AWS (Production-ready) |
| Architecture | Event-driven, service-boundary, cloud-agnostic core logic |
| Frontend | Next.js 16, React 19, TypeScript, TailwindCSS 4 |
| Phase 1 Host | DigitalOcean Droplet (sensor + SOAR + stream + ClickHouse) |
| Phase 1 Dashboard | Vercel |
| Phase 2 Target Host | AWS EC2 + EventBridge + Lambda + Security Hub + Amplify + App Runner |
| Key Performance Metric | MTTB measured; local dry-run median 0.962 ms |
| Latest Evidence | Median MTTB 0.962 ms (micro benchmark) and p95 MTTB below 1000 ms up to 600 concurrent events (local dry-run SOAR probe) |

---

## 2. Problem and Direction

CloudSentinel is built to stop high-speed automated SSH attacks where manual blocking fails.  
The system captures attacker behavior, fingerprints client identity using HASSH, maps behavior to MITRE ATT&CK, and auto-contains attacker IP with SOAR.

Current direction:
- Keep the local demo pipeline stable; the Phase 1 droplet is offline.
- Ensure telemetry truth from ClickHouse to dashboard.
- Measure MTTB under realistic load and report the actual value.

Phase 2 direction:
- Keep detection and intelligence logic unchanged.
- Move orchestration and scaling primitives to AWS managed services.

---

## 3. Research Alignment

| ID | Research Question | Objective |
|---|---|---|
| RQ1 | How can SSH-focused honeypot systems detect modern botnets with high confidence? | Build identity-centric SSH telemetry using HASSH and behavior analytics |
| RQ2 | How can a cloud-hosted honeypot block SSH attacks automatically? | Deliver automated containment for high-risk SSH attackers |
| RQ3 | How can cloud migration preserve logic while improving scalability? | Use cloud-agnostic core and migrate infra from DO to AWS |

---

## 4. Current System Reality (2026-06-01)

### 4.1 Phase 1 Deployment (validated 2026-05-26, now offline)

The droplet is offline. These are historical facts from the project artifacts:
- Phase 1 validation overall: PASS
- SSH honeypot: PASS
- Management SSH: PASS
- Socket.io port: PASS
- MITRE techniques: 20 catalogued, 17 mapped from commands
- Redis connected: True
- Stream enabled: True
- MTTB benchmark: median 0.962 ms, p95 1.5 ms

### 4.2 Core Engine Capabilities (Implemented)

- Unified async sensor entrypoint for SSH plus service modules.
- HASSH fingerprinting with real MD5 fingerprint set.
- MITRE ATT&CK mapping with regex and behavioral signatures.
- SOAR engine with automatic IP blocking.
- Redis stream pipeline plus ClickHouse persistence.
- Live telemetry stream for war-room UI.
- Prometheus metrics and structured observability.
- Admin API and secured operations endpoint.

---

## 5. Updated Two-Phase Architecture

### Phase 1 (validated, now offline): DigitalOcean
- Internet -> SSH Sensor -> HASSH + MITRE + Risk -> Local SOAR block -> ClickHouse -> Socket.io -> Vercel dashboard

### Phase 2 (Target): AWS
- Internet -> EC2 Sensor -> EventBridge -> Security Hub + Lambda SOAR -> ClickHouse Cloud -> App Runner stream -> Amplify dashboard

### Migration rule
Only infrastructure adapters change. Core detection logic remains same.

---

## 6. Improved WBS (Percent + Current Status)

```text
PROJECT: CLOUDSENTINEL (100%)

1. PLANNING AND ANALYSIS (20%) [Mostly Done]
1.1 SSH RFC Requirements (8%) [Done]
1.2 2026 Botnet TTP Research (6%) [Done]
1.3 AWS Tool Validation (6%) [In Progress]

2. SYSTEM DESIGN (15%) [Done]
2.1 Microservices Architecture (7%) [Done]
2.2 ERD and Time-Series Schema Design (5%) [Done]
2.3 Dashboard Mockups and UX Direction (3%) [Done]

3. CORE DEVELOPMENT (30%) [In Progress]
3.1 STAGE 1 SENSOR LAYER (9%) [Done]
3.1.1 AsyncSSH Reactor Implementation (4%) [Done]
3.1.2 HASSH Extraction Engine (3%) [Done]
3.1.3 Stateful Deceptive VFS Logic (2%) [Done]

3.2 STAGE 2 SOAR PIPELINE (12%) [Done on DO, AWS Adapter Planned]
3.2.1 DigitalOcean Local SOAR Blocking (iptables) [Done]
3.2.2 EventBridge Orchestration Adapter (5%) [Planned]
3.2.3 MITRE ATT&CK Parser and Risk Scoring (4%) [Done]
3.2.4 Lambda Blocking API Adapter (3%) [Planned]

3.3 STAGE 3 COMMAND CENTER (9%) [In Progress]
3.3.1 Next.js Dashboard Build (4%) [Done]
3.3.2 WebSocket Live Replay Server (3%) [Done]
3.3.3 Global Hosting Migration to AWS Amplify (2%) [Planned]

4. TESTING AND VALIDATION (15%) [In Progress]
4.1 Brute-force Simulation (8%) [Done]
4.2 MTTB Benchmark Testing (4%) [Done, 600-concurrency local dry-run p95 under 1000 ms]
4.3 User Acceptance Testing UAT (3%) [In Progress]

5. DEPLOYMENT AND DOCUMENTATION (20%) [In Progress]
5.1 24/7 Production Setup (DO Live, AWS Next) (10%) [In Progress]
5.2 Final Report and Diagrams (6%) [In Progress]
5.3 Pitching Presentation (4%) [In Progress]
```

---

## 7. SSH Botnet Specialization Matrix

CloudSentinel specializes in SSH-centric adversaries.

### 7.1 General SSH Botnet Families
- Mirai variants
- Gafgyt (Bashlite) variants
- Mozi
- Hajime
- Tsunami
- Kaiten
- Mayday
- Linux.BackDoor.Fgt
- XOR.DDoS
- BillGates botnet

### 7.2 Scanner and Tooling Fingerprints
- Nmap
- Zgrab2
- Masscan
- SSH-audit

### 7.3 SSH Attack Behavior Categories
- Brute-force credential stuffing
- Default credential replay
- Recon command bursts (`uname`, `id`, `cat /proc/cpuinfo`)
- Downloader execution (`wget`, `curl`, payload fetch)
- Persistence attempts (`crontab`, startup script edits)
- Lateral movement prep over SSH trust paths

---

## 8. KPI and Performance Targets

| Metric | Target | Current Evidence |
|---|---|---|
| MTTB | measured; local dry-run median 0.962 ms | p95 1.5 ms; p95 stays under 1000 ms up to 600 concurrent events; 800 concurrent reaches 1009.892 ms |
| MITRE technique coverage | 15+ | 17 of 20 catalogued techniques mapped from commands |
| Pipeline availability | High uptime for live capture | Phase 1 validation PASS |
| Telemetry truth | Dashboard must reflect ClickHouse truth | Truth QA runbook available |

---

## 9. PlantUML Pack (Updated)

### 9.1 Use Case Diagram
```plantuml
@startuml
left to right direction
actor Analyst
actor Attacker
actor Admin
rectangle CloudSentinel {
  usecase "Capture SSH Session" as UC1
  usecase "Fingerprint HASSH" as UC2
  usecase "Map MITRE TTP" as UC3
  usecase "Auto Block IP" as UC4
  usecase "Stream Live Telemetry" as UC5
  usecase "Review War Room" as UC6
  usecase "Tune SOAR Rules" as UC7
}
Attacker --> UC1
UC1 --> UC2
UC2 --> UC3
UC3 --> UC4
UC3 --> UC5
Analyst --> UC6
Admin --> UC7
UC6 --> UC5
UC7 --> UC4
@enduml
```

### 9.2 Component Diagram
```plantuml
@startuml
package "AWS EC2 Sensor Node" {
  [SSH Listener]
  [HASSH Extractor]
  [MITRE Mapper]
  [Risk Scorer]
}
package "AWS Security and Event Plane" {
  [EventBridge]
  [Security Hub]
  [Lambda SOAR Blocker]
  [Security Group Updater]
}
package "Analytics and Stream Plane" {
  [ClickHouse Cloud]
  [App Runner Stream API]
}
package "Presentation Plane" {
  [Amplify War Room Dashboard]
}
[SSH Listener] --> [HASSH Extractor]
[HASSH Extractor] --> [MITRE Mapper]
[MITRE Mapper] --> [Risk Scorer]
[Risk Scorer] --> [EventBridge]
[EventBridge] --> [Security Hub]
[Security Hub] --> [Lambda SOAR Blocker]
[Lambda SOAR Blocker] --> [Security Group Updater]
[Risk Scorer] --> [ClickHouse Cloud]
[ClickHouse Cloud] --> [App Runner Stream API]
[App Runner Stream API] --> [Amplify War Room Dashboard]
@enduml
```

### 9.3 Sequence Diagram (Phase 2 AWS)
```plantuml
@startuml
actor Attacker
participant "EC2 SSH Sensor" as Sensor
participant "EventBridge" as EB
participant "Security Hub" as SH
participant "Lambda SOAR" as LSOAR
participant "Security Group API" as SG
participant "ClickHouse Cloud" as CH
participant "App Runner Stream API" as AR
participant "Amplify Dashboard" as UI

Attacker -> Sensor: SSH connect and auth attempts
Sensor -> Sensor: compute HASSH, map MITRE, score risk
Sensor -> EB: publish high-risk event
EB -> SH: route finding
SH -> LSOAR: trigger automated response
alt risk above threshold
  LSOAR -> SG: revoke attacker IP
end
Sensor -> CH: write enriched event
CH -> AR: push stream payload
AR -> UI: render live update
@enduml
```

### 9.4 Activity Diagram (Detection to Block)
```plantuml
@startuml
start
:Receive SSH event;
:Extract HASSH;
:Map MITRE techniques;
:Score risk;
if (risk >= threshold?) then (yes)
  :Execute SOAR block;
  :Record block latency;
else (no)
  :Continue monitor;
endif
:Persist to ClickHouse;
:Publish live telemetry;
stop
@enduml
```

### 9.5 Deployment Diagram (Phase 2 AWS Only)
```plantuml
@startuml
node "Internet" {
  component "SSH Attack Traffic"
}
node "AWS Cloud" {
  node "EC2 Sensor Host" {
    component "CloudSentinel Sensor"
  }
  component "EventBridge"
  component "Security Hub"
  component "Lambda SOAR Blocker"
  component "Security Group Rule API"
  database "ClickHouse Cloud"
  component "App Runner Stream API"
  component "Amplify Dashboard"
}
"SSH Attack Traffic" --> "CloudSentinel Sensor"
"CloudSentinel Sensor" --> "EventBridge"
"EventBridge" --> "Security Hub"
"Security Hub" --> "Lambda SOAR Blocker"
"Lambda SOAR Blocker" --> "Security Group Rule API"
"CloudSentinel Sensor" --> "ClickHouse Cloud"
"ClickHouse Cloud" --> "App Runner Stream API"
"App Runner Stream API" --> "Amplify Dashboard"
@enduml
```

### 9.6 ER Diagram
```plantuml
@startuml
entity SESSIONS {
  * id : uuid
  --
  ip_address : string
  hassh_md5 : string
  start_time : datetime
  block_status : string
  cloud_provider : string
}
entity COMMAND_LOGS {
  * id : uuid
  --
  session_id : uuid
  command_raw : string
  mitre_id : string
  risk_score : int
}
entity HASSH_DNA {
  * hassh_md5 : string
  --
  client_software : string
  botnet_family : string
  first_seen : datetime
  last_seen : datetime
}
entity SOAR_ACTIONS {
  * action_id : uuid
  --
  session_id : uuid
  action_type : string
  mttb_ms : float
  blocked_at : datetime
  target_control : string
}
SESSIONS ||--o{ COMMAND_LOGS : generates
HASSH_DNA ||--o{ SESSIONS : identifies
SESSIONS ||--o{ SOAR_ACTIONS : triggers
@enduml
```

### 9.7 WBS Diagram (PlantUML WBS)
```plantuml
@startwbs
* CloudSentinel
** Planning and Analysis (20%) [mostly done]
*** SSH RFC requirements (8%) [done]
*** 2026 botnet TTP research (6%) [done]
*** AWS tool validation (6%) [in progress]
** System Design (15%) [done]
*** Microservices architecture (7%) [done]
*** ERD and time-series schema (5%) [done]
*** Dashboard mockups (3%) [done]
** Core Development (30%) [in progress]
*** Stage 1 Sensor Layer (9%) [done]
**** AsyncSSH reactor (4%) [done]
**** HASSH extraction (3%) [done]
**** Stateful deceptive VFS (2%) [done]
*** Stage 2 Cloud SOAR Pipeline (12%) [in progress]
**** EventBridge orchestration (5%) [planned]
**** MITRE parser and scoring (4%) [done]
**** Lambda blocking API (3%) [planned]
*** Stage 3 Command Center (9%) [in progress]
**** Next.js dashboard (4%) [done]
**** WebSocket live replay server (3%) [done]
**** AWS Amplify global hosting (2%) [planned]
** Testing and Validation (15%) [in progress]
*** Brute-force simulation (8%) [done]
*** MTTB benchmark testing (4%) [done]
*** UAT (3%) [in progress]
** Deployment and Docs (20%) [in progress]
*** 24/7 AWS production setup (10%) [in progress]
*** Final report and diagrams (6%) [in progress]
*** Pitching presentation (4%) [in progress]
@endwbs
```

---

## 10. AI Working Directives

- Use this file as living reference for current architecture and delivery status.
- Do not describe Phase 1 as currently live. The droplet is offline; cite the validation artifact.
- Do not invent metrics not backed by artifacts.
- Never send raw secrets to an LLM. Use `redact_secrets` and the per-session and global call limits.
- Use artifact-backed metrics. Do not promise a fixed sub-second target.
- Preserve SSH botnet specialization in any feature extension.
- For migration tasks, separate "core logic" from "cloud adapter" changes.

---

## 11. Source Anchors for This Update

- `docs/ARCHITECTURE.md`
- `docs/INDEX.md`
- `artifacts/mttb-benchmark.md`
- `artifacts/phase1-validation.md`
- `docs/DEPLOY.md`
- `docs/CLICKHOUSE_TRUTH_QA.md`
- `src/cloudsentinel/PROJECT_STRUCTURE.md`
- `dashboard/src/components/AIChatAgent.tsx`
