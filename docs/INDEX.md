# Documentation Index

Last reviewed: 2026-11-06.

## Authoritative documents

| Document | Purpose | Owner |
|---|---|---|
| `README.md` | Start here. Status, quick start, doc map. | Project root |
| `docs/ARCHITECTURE.md` | Single source of truth for architecture, trust boundaries, metrics, and known gaps. | Architecture |
| `docs/DEPLOY.md` | Phase 1 DigitalOcean deployment and Phase 2 Azure plan. | Operations |
| `docs/LOCAL_DEMO.md` | Zero-cost local demo with Docker. Use this now that the Phase 1 droplet is offline. | Operations |
| `docs/CLICKHOUSE_TRUTH_QA.md` | How to check that the dashboard shows ClickHouse truth. | Data |
| `src/cloudsentinel/PROJECT_STRUCTURE.md` | Code map for the sensor package. | Code |
| `dashboard/README.md` | Dashboard setup, environment variables, and deploy. | Frontend |
| `cloudsentinel-skill.md` | Working reference for AI-assisted changes. Not a citation source. | Project |
| `artifacts/mttb-benchmark.md` | MTTB evidence. | Evidence |
| `artifacts/mttb-concurrency-threshold.md` | Concurrency evidence. | Evidence |
| `artifacts/ttp-coverage.md` | MITRE coverage evidence. | Evidence |
| `artifacts/phase1-validation.md` | Phase 1 validation evidence. | Evidence |

## FYP documents

| Document | Status |
|---|---|
| `docs/working-paper/report/FYP Pitching Content.docx` | Current report source |
| `docs/working-paper/report/FYP_content.txt` | Plain-text working copy of the report |
| `docs/working-paper/slides/slidecontent.txt` | Current slide content |
| `docs/working-paper/slides/CloudSentinel-slides.pptx` | Current slide deck source |

## Rule

When a fact changes, update `docs/ARCHITECTURE.md` first, then the report and slides. If two current documents disagree, the architecture document wins.
