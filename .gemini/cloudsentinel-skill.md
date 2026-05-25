# CloudSentinel — AI Skill File

> **Project:** CloudSentinel: Event-Driven Automation and Identity-Centric Deception  
> **Author:** Radzi bin Zamri (I24107504)  
> **Supervisor:** Sir Helmy Hanyff  
> **Faculty:** FPTM — Universiti Sultan Azlan Shah (USAS)  
> **Type:** Final Year Project (FYP)  
> **Target Grade:** A+  
> **Last Updated:** 2026-05-25

---

## 1. Project Metadata

| Field                  | Value                                                                 |
|------------------------|-----------------------------------------------------------------------|
| **System Name**        | CloudSentinel                                                         |
| **Domain**             | Cybersecurity — Honeypot / Active Deception / SOAR                    |
| **Target Protocol**    | SSH (Port 22)                                                         |
| **Deployment Strategy**| **Two-Phase:** DigitalOcean (Dev/MVP) → AWS (Production-Ready)        |
| **Architecture Style** | Event-Driven, Cloud-Agnostic Service Boundaries                      |
| **Frontend Framework** | Next.js 16 + React 19 + TypeScript + TailwindCSS 4                    |
| **Dev Hosting**        | DigitalOcean Droplet (Sensor+SOAR), Vercel (Dashboard)                |
| **Prod Hosting**       | AWS EC2 + EventBridge + Lambda + Amplify (Migration Target)           |
| **Key Metric**         | MTTB (Mean Time to Block) target < 0.86 seconds                      |
| **Budget**             | RM 0 (GitHub Student Pack $200 DO credits + Vercel free tier)         |

---

## 2. Purpose & Problem Statement

CloudSentinel is a **cloud-native, event-driven SSH defense system** that detects, analyzes, and blocks cyberattacks automatically in near real-time. It was designed to address three cascading problems:

1. **Industrialization of Cybercrime** — Automated botnets (Mirai, Gafgyt) overwhelm static defenses through high-speed, adaptive reconnaissance.
2. **Operational Gaps** — Traditional student projects lack 24/7 coverage, leaving critical gaps in long-term threat data collection.
3. **Latency in Response** — Manual blocking cannot stop automated attacks that move laterally within seconds.

**Key Innovation:** Unlike traditional honeypots that passively log attacks, CloudSentinel actively responds by automatically blocking attackers in under 1 second using a SOAR pipeline, while using HASSH cryptographic fingerprinting to track botnets by identity rather than just IP.

**Implementation Strategy (Cowrie-Based Custom Rewrite):** To ensure a robust, well-structured, and highly reliable medium-interaction SSH/Telnet base, we utilize the open-source **Cowrie Honeypot** architecture. Instead of deploying it out of the box, we are rewriting/refactoring its core codebase 100% to implement all custom CloudSentinel requirements (event-driven SOAR blocking, ClickHouse logging, and identity-centric forensics), converting it entirely to our project objectives.

**Deployment Philosophy:** The system is built with **cloud-provider-agnostic service boundaries**. Phase 1 (Dev/MVP) deploys on DigitalOcean for rapid iteration and proven metrics. Phase 2 (Production-Ready) migrates to AWS managed services (EventBridge, Lambda, Security Hub) for enterprise-grade scalability. The core cybersecurity logic — HASSH extraction, MITRE mapping, and SOAR blocking — remains identical across both phases.

---

## 3. Research Questions & Objectives

| ID    | Research Question                                                                                          | Aligned Objective                                                                        |
|-------|------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| RQ1   | How do static, monolithic honeypots fail against automated SSH botnets in 2026?                            | Develop a Cloud-Native Intelligence Pipeline with MITRE ATT&CK v18 mapping.              |
| RQ2a  | How can a cloud-hosted, event-driven architecture achieve 24/7 operational uptime?                         | Design a resource-efficient SSH sensor using Asynchronous I/O on cloud VPS.               |
| RQ2b  | What architectural patterns enable sub-second automated response to SSH-based attacks?                     | Build an automated response mechanism with MTTB < 1s using event-driven SOAR.            |
| RQ3   | How do identity-centric deception techniques (Honey-tokens, HASSH) improve forensic depth for SOC teams?   | Deploy identity-centric deception (HASSH, Honey-tokens) for enhanced forensic depth.      |

---

## 4. System Architecture (Two-Phase Deployment)

### Phase 1 — Dev/MVP (DigitalOcean)

All services run on a **single DigitalOcean Droplet** ($4/mo, free via GitHub Student Pack). SOAR blocking is a local `iptables` call, eliminating IAM complexity and achieving faster MTTB.

**Data Flow (Phase 1):**
1. Attacker connects to the SSH sensor on Port 22.
2. HASSH fingerprint is extracted during the SSH handshake (pre-authentication).
3. `analyze(session)` is called locally — maps commands to MITRE ATT&CK v18, enriches with GeoIP.
4. If risk exceeds threshold → `iptables -A INPUT -s {ip} -j DROP` executes locally (MTTB ~0.05-0.1s).
5. Logs are persisted in **ClickHouse** (columnar OLAP database) on the same server.
6. Socket.io streams events to War Room Dashboard hosted on Vercel.

```
        Attacker (Botnet)
              │
              ▼
     Cowrie-Based Sensor (Port 22)     ─── DigitalOcean Droplet ───
              │
              ├──► HASSH Extract
              │
              ▼
     analyze(session)  ← Python
     ├── GeoIP Enrich (MaxMind)
     ├── MITRE ATT&CK Mapping
     │
     ▼
   Risk > Threshold?
     │ YES              │ NO
     ▼                  ▼
   iptables DROP     Continue
   (MTTB ~0.05s)     Monitoring
     │
     ▼
   ClickHouse  ← Session Logs
     │
     ▼
   Socket.io  ← Live Stream
     │
     ▼
   War Room Dashboard (Vercel)
```

### Phase 2 — Production-Ready (AWS Migration)

The same core logic migrates to AWS managed services for enterprise-grade scalability.

**Data Flow (Phase 2):**
1. Attacker connects to the SSH sensor on EC2 (Port 22).
2. HASSH fingerprint extracted, event pushed to **EventBridge** (~10ms latency).
3. **Security Hub** ingests the finding, maps to MITRE ATT&CK v18, scores risk.
4. High-risk → **Lambda SOAR** revokes IP via Security Group rule (MTTB < 0.86s).
5. Enriched logs persisted in **ClickHouse Cloud**, streamed to **Amplify**-hosted Dashboard.

```
        Attacker (Botnet)
              │
              ▼
     Cowrie-Based Sensor (Port 22)        ─── AWS EC2 t3.micro ───
              │
              ├──► HASSH Extract
              │
              ▼
     AWS EventBridge  ← Event Bus (~10ms)
              │
              ▼
     AWS Security Hub
     ├── MITRE ATT&CK v18 Mapping
     ├── Risk Scoring
     │
     ▼
   Risk > Threshold?
     │ YES              │ NO
     ▼                  ▼
   AWS Lambda SOAR   Continue
     │                Monitoring
     ▼
   Security Group
   Revoke IP
   (MTTB <0.86s)
     │
     ▼
   ClickHouse Cloud  ← Enriched Logs
     │
     ▼
   App Runner  ← Socket.io Stream
     │
     ▼
   War Room Dashboard (AWS Amplify)
```

### Migration Path (Phase 1 → Phase 2)

| Component        | Phase 1 (DO)                        | Phase 2 (AWS)                    | Code Change Required |
|------------------|-------------------------------------|----------------------------------|----------------------|
| Sensor Host      | DigitalOcean Droplet                | AWS EC2 t3.micro                 | None (same Python)   |
| Event Routing    | Local Python function call          | AWS EventBridge                  | Swap to boto3 call   |
| Intelligence     | Python dict (MITRE lookup)          | AWS Security Hub                 | Swap to SDK call     |
| SOAR Blocking    | `iptables` subprocess               | AWS Lambda → Security Group      | Swap to Lambda handler|
| Database         | ClickHouse (local/cloud free tier)  | ClickHouse Cloud (managed)       | Change connection URI |
| Dashboard Host   | Vercel (free)                       | AWS Amplify                      | Change deploy target |
| WebSocket        | Socket.io on same Droplet           | AWS App Runner                   | Change deploy target |

---

## 5. Technology Stack (Dual-Phase)

### Phase 1 — Dev/MVP Stack

| Cowrie (Custom Rewrite)   | Foundational Framework | Medium-interaction SSH/Telnet base, rewritten 100% for active defense.     |
| AsyncSSH (Python)         | Core Sensor Engine     | Non-blocking I/O handles 500+ concurrent SSH connections (underlies Cowrie). |
| DigitalOcean Droplet      | All-in-One Hosting     | $4/mo (free via GitHub Student Pack). 1 vCPU, 1GB RAM, Ubuntu 24.04.     |
| Python `iptables` wrapper | SOAR Blocking          | Local subprocess call = ~0.05s MTTB. No IAM, no cold starts.             |
| ClickHouse                | Threat Analytics DB    | Columnar OLAP engine — sub-ms aggregations on log data. Used by Cloudflare for security analytics. Free tier: 25GB. |
| MaxMind GeoIP2            | IP Enrichment          | Local file-based lookup. No API rate limits.                              |
| Socket.io (Node.js)       | Live Replay Stream     | Runs on same Droplet. Direct DB access.                                   |
| Vercel                    | Dashboard Hosting      | Free tier, built for Next.js, automatic CI/CD from GitHub.                |
| Next.js 16 / React 19    | Dashboard UI           | Server-side rendering, App Router, TypeScript, TailwindCSS.               |
| Recharts                  | Data Visualization     | Charts for attack type distribution and MITRE ATT&CK mapping.            |
| react-simple-maps         | Threat Map             | Interactive geospatial visualization with custom attack lines.            |

### Phase 2 — Production-Ready Stack (AWS Migration)

| Tool/Service         | Purpose                | Replaces (Phase 1)           |
|----------------------|------------------------|------------------------------|
| AWS EC2 (t3.micro)   | Sensor Hosting         | DigitalOcean Droplet         |
| AWS EventBridge      | Event Orchestration    | Local function call          |
| AWS Security Hub     | Intelligence Layer     | Python MITRE dict            |
| AWS Lambda           | SOAR Engine            | `iptables` subprocess        |
| ClickHouse Cloud     | Managed Analytics DB   | Self-hosted ClickHouse       |
| AWS Amplify          | Frontend Hosting       | Vercel                       |
| AWS App Runner       | WebSocket Server       | Local Socket.io              |

---

## 6. Implementation Stages (Two-Phase)

### Phase 1: Dev/MVP on DigitalOcean

#### Stage 1: Sensor Node (Python / Droplet) — 40% Complete
- Provision DigitalOcean Droplet (1 vCPU, 1GB RAM, Ubuntu 24.04).
- Configure firewall to allow Port 22 globally.
- Deploy open-source **Cowrie Honeypot** as the foundational base structural framework.
- Rewrite/refactor Cowrie codebase 100% to incorporate CloudSentinel specific objectives.
- Customize the deceptive **Virtual File System (VFS)** mimicking Ubuntu 22.04.
- Hook into Cowrie's connection handler for pre-authentication **HASSH fingerprint extraction**.

#### Stage 2: Local SOAR Pipeline (Python) — NEW
- Build Python `analyze(session)` function for real-time MITRE ATT&CK v18 mapping.
- Implement `iptables`-based auto-blocking via subprocess (target MTTB < 0.1s).
- Enrich sessions with MaxMind GeoIP2 (local database file).
- Persist enriched logs to **ClickHouse** (OLAP-optimized threat analytics).
- Deploy Socket.io on the same Droplet for live event streaming.

#### Stage 3: War Room Dashboard (Next.js / Vercel) — 20% Complete
- Deploy Next.js cloud_sentinel_ui to **Vercel** with CI/CD.
- Wire mock data to live ClickHouse/WebSocket feeds from the Droplet.
- Prove all KPIs with real attack data (MTTB, TTP coverage, uptime).

### Phase 2: Production-Ready on AWS

#### Stage 4: AWS Migration
- Migrate sensor to **AWS EC2 t3.micro**.
- Replace local function calls with **EventBridge** event publishing (boto3).
- Replace Python MITRE dict with **Security Hub** ingestion.
- Convert SOAR blocking logic to **AWS Lambda** function with Provisioned Concurrency.
- Migrate ClickHouse to **ClickHouse Cloud** (managed, or self-hosted on EC2).
- Redeploy dashboard to **AWS Amplify**, WebSocket to **App Runner**.

---

## 6.1 Work Breakdown Structure (WBS)

```
PROJECT: CLOUDSENTINEL
│
├── PHASE 1: DEV/MVP (DigitalOcean) ──────────────── Target: Working Demo
│   │
│   ├── STAGE 1: SENSOR NODE (40%)
│   │   ├── [x] DigitalOcean Droplet provisioning
│   │   ├── [ ] Deploy open-source Cowrie honeypot as foundational base
│   │   ├── [ ] 100% rewrite/refactoring of Cowrie codebase to align with CloudSentinel objectives
│   │   ├── [ ] Deceptive VFS (Ubuntu 22.04 mock) customization
│   │   ├── [ ] HASSH fingerprint extraction integration
│   │   └── [ ] Stress test 500+ concurrent connections
│   │
│   ├── STAGE 2: LOCAL SOAR PIPELINE (0%)
│   │   ├── [ ] Python MITRE ATT&CK v18 mapping module
│   │   ├── [ ] iptables auto-block function
│   │   ├── [ ] MaxMind GeoIP2 enrichment
│   │   ├── [ ] ClickHouse schema + persistence (MergeTree engine)
│   │   ├── [ ] Socket.io live event streaming
│   │   └── [ ] MTTB benchmark testing (target <0.1s)
│   │
│   ├── STAGE 3: WAR ROOM DASHBOARD (20%)
│   │   ├── [x] Next.js mockup UI (4 pages)
│   │   ├── [ ] Deploy to Vercel
│   │   ├── [ ] Wire to live data (replace mockData.ts)
│   │   └── [ ] End-to-end live demo
│   │
│   └── TESTING & METRICS VALIDATION
│       ├── [ ] Hydra brute-force simulation
│       ├── [ ] Custom Python scanner tests
│       ├── [ ] MTTB measurement (detection → iptables)
│       └── [ ] 15+ MITRE TTP coverage verification
│
├── PHASE 2: PRODUCTION-READY (AWS) ──────────────── Target: Enterprise Architecture
│   │
│   ├── STAGE 4: AWS MIGRATION
│   │   ├── [ ] EC2 sensor deployment
│   │   ├── [ ] EventBridge integration (replace local calls)
│   │   ├── [ ] Security Hub ingestion (replace Python dict)
│   │   ├── [ ] Lambda SOAR function + Provisioned Concurrency
│   │   ├── [ ] ClickHouse Cloud migration (managed tier)
│   │   ├── [ ] Amplify dashboard deployment
│   │   ├── [ ] App Runner WebSocket deployment
│   │   └── [ ] IAM policies & cross-service permissions
│   │
│   └── AWS METRICS VALIDATION
│       ├── [ ] MTTB benchmark on AWS (target <0.86s)
│       ├── [ ] End-to-end AWS pipeline demo
│       └── [ ] Cost analysis vs Phase 1
│
└── DOCUMENTATION & PRESENTATION
    ├── [ ] FYP Report (Chapters 1-5)
    ├── [ ] Updated architecture diagrams (both phases)
    ├── [ ] Evaluation metrics comparison table
    └── [ ] Final presentation slides
```

---

## 7. Mockup UI Architecture (Current State)

The War Room Dashboard is a **Next.js 16 application** with the following route structure:

```
src/
├── app/
│   ├── layout.tsx           # Root layout (Inter font, ThemeProvider, Sidebar)
│   ├── page.tsx             # War Room Dashboard (main page)
│   ├── globals.css          # Global styles
│   ├── intelligence/
│   │   └── page.tsx         # TTP Analysis & HASSH Fingerprinting
│   ├── sessions/
│   │   └── page.tsx         # Captured Sessions with Terminal Replay
│   └── settings/
│       └── page.tsx         # System Configuration (Sensor, HASSH, SOAR)
├── components/
│   ├── Sidebar.tsx          # Collapsible nav + theme toggle + system status
│   ├── ThreatMap.tsx        # Interactive world map with attack lines & tooltips
│   ├── AttackLog.tsx        # Real-time attack event feed (filtered by region)
│   ├── TerminalReplay.tsx   # Terminal emulator for session command replay
│   └── theme-provider.tsx   # next-themes wrapper (dark mode default)
├── lib/
│   ├── mockData.ts          # Mock stats, threat logs, sessions, map data
│   └── utils.ts             # Utility functions (cn/clsx merge)
└── public/
    ├── world-atlas.json     # TopoJSON for the interactive map
    └── logo.svg             # CloudSentinel shield logo
```

### Dashboard Pages

| Route            | Name                | Purpose                                                                              |
|------------------|---------------------|--------------------------------------------------------------------------------------|
| `/`              | War Room            | Real-time KPIs (Connections, MTTB, MITRE TTPs, Uptime), Global Threat Map, Live Feed |
| `/sessions`      | Captured Sessions   | Session list with search, HASSH/IP/client filtering, terminal replay inspector       |
| `/intelligence`  | Threat Intelligence | Attack type distribution (donut chart), MITRE ATT&CK mapping (bar chart), HASSH table|
| `/settings`      | System Config       | Sensor VFS level, Honey-token toggle, HASSH action rules, SOAR thresholds            |

### Key UI Components

- **ThreatMap** — ComposableMap (geoEquirectangular) with animated SVG attack lines, interactive tooltips (IP, TTP, HASSH), expandable fullscreen mode, region click filtering.
- **AttackLog** — Live event feed with MITRE technique IDs, auto-block timestamps (MTTB), country-code filtering synced with ThreatMap selection.
- **TerminalReplay** — Faux terminal emulator rendering captured attacker commands with blinking cursor and copy functionality.
- **Sidebar** — Collapsible navigation, dark/light theme toggle, "FYP Prototype" disclaimer badge, system status indicator.

---

## 8. Data Models

### Entity Relationship Diagram

| Entity         | Primary Key    | Key Fields                                                                    |
|----------------|----------------|-------------------------------------------------------------------------------|
| **SESSIONS**   | `id` (UUID)    | `ip_address`, `country_code`, `hassh_md5` (FK), `start_time`, `block_status`  |
| **HASSH_DNA**  | `hassh_md5`    | `client_software`, `botnet_family`, `threat_score`, `first_seen`, `last_seen` |
| **COMMAND_LOGS**| `id` (UUID)   | `session_id` (FK), `mitre_id`, `input_raw`, `output_raw`, `risk_score`        |

**Relationships:**
- `SESSIONS` → `HASSH_DNA` (many-to-one, identified_by)
- `SESSIONS` → `COMMAND_LOGS` (one-to-many, generates)

### Mock Data Schema (Current Mockup)

```typescript
// Stats (War Room KPIs)
MOCK_STATS: {
  concurrentConnections: 350,   // Target: 500+
  mttb: "0.92s",                // Target: <0.86s
  mitreCoverage: 8,             // Target: 15+ TTPs
  systemUptime: "99.5%"         // Target: 99.9%
}

// Threat Logs (Live Feed Events)
THREAT_LOGS[]: { id, timestamp, ip, country, type, payload, mitreId, action, timeToBlock }

// Active Sessions (Terminal Replay)
ACTIVE_SESSIONS[]: { id, ip, country, duration, client, fingerprint, input[], status }

// Map Data (Geospatial)
MAP_DATA[]: { name, lat, lng, count, color, topIp, dominantTtp, topHassh }
```

---

## 9. Evaluation Metrics

| Objective            | Metric                    | Target           | Current Status          |
|----------------------|---------------------------|------------------|-------------------------|
| Sensor Performance   | Concurrent Connections    | 500+             | 350 (In Testing)        |
| Response Latency     | Mean Time to Block (MTTB) | < 0.86s          | 0.92s                   |
| Intelligence Depth   | MITRE TTP Coverage        | 15+ TTPs         | 8 TTPs Mapped           |
| System Uptime        | Availability              | 99.9%            | 99.5%                   |

---

## 10. Key Terminology

| Term                     | Definition                                                                                          |
|--------------------------|-----------------------------------------------------------------------------------------------------|
| **MTTB**                 | Mean Time to Block — the latency from detection to firewall rule execution.                         |
| **HASSH Fingerprinting** | Identifying SSH clients by unique cryptographic handshake packets (MD5 hash).                       |
| **Honey-tokens**         | Deceptive credentials (e.g., fake AWS API keys) used as tripwires to detect lateral movement.       |
| **Tarpitting**           | Manipulating TCP windows or responses to slow down attacker sessions and waste their resources.      |
| **VFS**                  | Virtual File System — a deceptive, simulated environment provided to the attacker to mask the host. |
| **SOAR**                 | Security Orchestration, Automation, and Response — automated containment triggered by events.       |
| **MITRE ATT&CK**        | A globally standardized knowledge base of adversary tactics, techniques, and procedures (TTPs).     |
| **EventBridge**          | AWS serverless event bus for routing events between decoupled services.                             |
| **ClickHouse**           | Columnar OLAP database optimized for real-time analytics on time-series/log data. Used by Cloudflare, GitLab. |

---

## 11. AI Task Directives

When working on this project, AI assistants **MUST** adhere to the following:

### 11.1 Source of Truth Hierarchy
1. **Pitching Content** (`fyp working paper/Pitching/content/`) — Canonical definitions for architecture, objectives, metrics, research questions, and terminology.
2. **Mockup Codebase** (`fyp_project/mockup/cloud_sentinel_ui/`) — Canonical definitions for UI structure, components, routes, data models, and visual design.
3. **Evaluation & Implementation Plans** (`leman content/`) — Canonical definitions for viability assessment and development stages.

### 11.2 Permitted AI Tasks

| Task Category              | Description                                                                                    |
|----------------------------|------------------------------------------------------------------------------------------------|
| **UI/UX Development**      | Develop, refine, and polish the War Room Dashboard mockup. Maintain dark-mode-first design.    |
| **Component Engineering**  | Build or enhance React/Next.js components. Use existing design patterns from `components/`.    |
| **Data Model Extension**   | Extend mock data in `lib/mockData.ts` to support new features or views.                        |
| **Backend Integration**    | Wire mockup to live services. Phase 1: ClickHouse/Socket.io. Phase 2: AWS services.    |
| **Documentation**          | Generate FYP documentation, diagrams, and report sections based on pitching content.           |
| **Testing & Validation**   | Write attack simulation scripts, measure MTTB, validate MITRE TTP mapping.                    |
| **Sensor Development**     | Assist with Cowrie integration, folder renaming, modifying configurations, parameters, and variables, VFS customization, HASSH extraction, and a 100% rewrite of the codebase to fit CloudSentinel objectives. |
| **SOAR Pipeline**          | Phase 1: Python iptables blocking. Phase 2: Lambda + Security Group.                   |

### 11.3 Prohibited Actions
- **Do NOT hallucinate** metrics, statistics, or capabilities not documented in the pitching content.
- **Do NOT invent** cloud services or architectures not specified in the two-phase system architecture.
- **Do NOT deviate** from the established tech stack without explicit user approval.
- **Do NOT modify** research questions, objectives, or evaluation targets without explicit request.
- **Do NOT remove** the "FYP Prototype" disclaimer badge from the sidebar in the mockup.

### 11.4 Design Guidelines
- **Theme:** Dark mode by default (`defaultTheme="dark"`). Use `#050505` for backgrounds, `#0a0a0a` for cards.
- **Typography:** Inter font family via `next/font/google`.
- **Component Style:** Rounded-xl borders, `border-white/5` in dark mode, `shadow-sm`, `backdrop-blur-md`.
- **Accent Colors:** Blue-600 primary, Red-500 for threats/blocks, Green-500 for active/online, Purple-500 for HASSH, Amber-500 for warnings.
- **Icons:** Lucide React icons exclusively.
- **Charts:** Recharts library (PieChart, BarChart, ResponsiveContainer).
- **Maps:** react-simple-maps with geoEquirectangular projection.
- **Animations:** CSS `animate-ping` for live indicators, `animate-pulse` for status dots, custom `@keyframes dash` for attack lines.

---

## 12. Competitive Differentiation

| Feature                   | Cowrie       | T-Pot        | CloudSentinel         |
|---------------------------|--------------|--------------|-----------------------|
| Interaction Level         | Medium       | High         | **High**              |
| Response Type             | Passive      | Passive      | **Active SOAR**       |
| Identity Tracking         | IP only      | IP only      | **HASSH + IP**        |
| Auto-Blocking             | ❌           | ❌           | **✅ (< 0.1s DO / < 0.86s AWS)**|
| Cloud-Native              | ❌           | ❌           | **✅ (DO → AWS)**     |
| Resource Usage            | Low          | Very High    | **Low (Optimized)**   |
| Deployment Complexity     | Moderate     | High         | **Low (Phased)**      |
| MITRE ATT&CK Mapping     | Manual       | Limited      | **Automated (v18)**   |

---

## 13. Project Folder Structure

```
FYP/
├── cloudsentinel.docx                          # Project overview document
├── fyp working paper/
│   ├── Pitching/
│   │   └── content/
│   │       ├── core content/
│   │       │   ├── FYP Pitching Content.docx   # Full pitching document (source of truth)
│   │       │   ├── FYP Pitching Content.pdf    # PDF export
│   │       │   ├── FYP_content.txt             # Plain-text extract of pitching content
│   │       │   └── leman content/
│   │       │       ├── FYP_evaluation-fromLeman.txt      # External evaluation assessment
│   │       │       └── FYP_implementationPlan-fromLeman.txt  # Staged implementation plan
│   │       ├── diagram/
│   │       │   ├── ENTITY RELATIONSHIP DIAGRAM.png
│   │       │   ├── SEQUENCE DIAGRAM.png
│   │       │   ├── SYSTEM ARCHITECTURE DIAGRAM.png
│   │       │   ├── USE CASE DIAGRAM.png
│   │       │   ├── WORK BREAKDOWN STRUCTURE.png
│   │       │   └── WORKFLOW DIAGRAM.png
│   │       └── presentation slide/
│   │           ├── pitching slides.pptx
│   │           └── pitching slides.pdf
│   ├── Proposal/
│   │   ├── 1st-Proposal FYP.pdf
│   │   └── PPTX/
│   └── borang cadangan/
└── fyp_project/
    └── mockup/
        └── cloud_sentinel_ui/                  # Next.js 16 War Room Dashboard
            ├── src/
            │   ├── app/                        # App Router pages
            │   ├── components/                 # Reusable UI components
            │   └── lib/                        # Mock data & utilities
            ├── public/                         # Static assets (map, logo)
            ├── package.json                    # Dependencies manifest
            └── next.config.ts                  # Next.js configuration
```

---

## 14. Running the Mockup Locally

```bash
cd "c:\Users\RADZ\project io\FYP\fyp_project\mockup\cloud_sentinel_ui"
npm install
npm run dev
# Open http://localhost:3000
```

---

> **Note:** This skill file is a living document derived from the `Pitching` and `mockup` source folders. The two-phase deployment strategy (DigitalOcean Dev/MVP → AWS Production-Ready) was adopted to maximize delivery reliability while maintaining enterprise-grade architecture aspirations. All core cybersecurity innovations (HASSH, MITRE mapping, SOAR blocking) are cloud-provider-agnostic. No information has been fabricated.
