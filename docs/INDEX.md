# Documentation Index

Last reviewed: 2026-11-26.

## Authoritative documents

| Document | Purpose | Owner |
|---|---|---|
| `README.md` | Start here. Status, quick start, doc map. | Project root |
| `docs/ARCHITECTURE.md` | Single source of truth for architecture, trust boundaries, metrics, and known gaps. | Architecture |
| `docs/MOBILE.md` | Android companion, pairing, mobile API, FCM, build and troubleshooting. | Mobile |
| `docs/DEPLOY.md` | Legacy retirement note and Azure deployment plan. | Operations |
| `docs/LOCAL_DEMO.md` | Zero-cost local demo with Docker. | Operations |
| `docs/CLICKHOUSE_TRUTH_QA.md` | How to check that the dashboard shows ClickHouse truth. | Data |
| `src/cloudsentinel/PROJECT_STRUCTURE.md` | Code map for the sensor package. | Code |
| `dashboard/README.md` | Dashboard setup, environment variables, and deploy. | Frontend |
| `mobile-android/README.md` | Android build and pairing quick start. | Mobile |
| `cloudsentinel-skill.md` | Working reference for AI-assisted changes. Not a citation source. | Project |
| `artifacts/mttb-benchmark.md` | MTTB evidence. | Evidence |
| `artifacts/mttb-concurrency-threshold.md` | Concurrency evidence. | Evidence |
| `artifacts/ttp-coverage.md` | MITRE coverage evidence. | Evidence |
| `artifacts/phase1-validation.md` | Phase 1 validation evidence. | Evidence |

## Active design work

| Document | Status |
|---|---|
| `docs/superpowers/specs/2026-11-24-honeypot-refactor-design.md` | Proposed staged refactor plan; no code changes yet. |

## FYP documents

| Document | Status |
|---|---|
| `docs/working-paper/report/FYP Pitching Content.docx` | Current report source |
| `docs/working-paper/report/FYP_content.txt` | Plain-text working copy of the report |
| `docs/working-paper/slides/slidecontent.txt` | Current slide content |
| `docs/working-paper/slides/CloudSentinel-slides.pptx` | Current slide deck source |

## Rule

When a fact changes, update `docs/ARCHITECTURE.md` first, then the report and slides. If two current documents disagree, the architecture document wins.

