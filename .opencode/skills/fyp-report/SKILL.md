---
name: fyp-report
description: "Use when drafting, checking, or planning a Final Year Project (FYP) report for IT at USAS/Universiti Sultan Azlan Shah - Bab 1 Pengenalan, Bab 2 Kajian Literatur, Bab 3 Metodologi, Bab 4 Dapatan dan Perbincangan, Bab 5 Kesimpulan dan Cadangan, or Gantt chart. IT systems only; not multimedia."
---

# FYP Report (IT)

This skill helps write the IT FYP report for this repository. The canonical guide is at `docs/fyp-report-guide.md` (from this skill folder: `../../../docs/fyp-report-guide.md`).

**Stop if the project is multimedia.** This skill is for IT system development projects only.

## First step

**Read `docs/fyp-report-guide.md` before writing.** Do not rely on this summary alone. The guide contains the required components, outlines, checklists, examples, and rules for every chapter.

## Workflow

1. Identify the requested chapter and the project details.
2. Read the matching guide section (table below).
3. Collect missing input; ask the user. Do not invent.
4. Draft using the chapter outline and required components.
5. Check the chapter checklist and alignment; report gaps.

## Chapter map

| Request | Read |
|---|---|
| Gantt chart | §2 |
| Chapter 1 Introduction | §3 |
| Chapter 2 Literature Review | §4 |
| Chapter 3 Methodology | §5 |
| Chapter 4 Findings and Discussion | §6 |
| Chapter 5 Conclusion and Recommendations | §7 |
| Structure conflicts | §1.4 and §2.7 |
| Agent instructions | §10 |

## Non-negotiable rules

- **IT only.** Do not include multimedia content.
- **Never invent** references, data, results, dates, or names.
- Chapters 1, 2, and 3 need source support; Chapter 4 uses the study's own findings; Chapter 5 adds no new data or references.
- **Structure hierarchy:** faculty report template > video content > Gantt template.
- Chapter 1 must have six aspects: background, problem statement, research questions, objectives, scope, and significance/impact.
- Objectives: minimum 2, recommended 3.
- Chapter 4 is written only after the system is complete.
- Do not copy guide examples (Klinik USAS, 50% of respondents, Web 1-6) as the user's project data.
- Mark gaps: `[NEED DATA: ...]` and `[ASSUMPTION: ...]` (or `[PERLU DATA: ...]` / `[ANDAIAN: ...]` for Malay output).

## Minimum input

Project title, problem, users/scope, objectives, methodology model, previous systems, findings data, system shortcomings, recommendations, and the faculty template/format. Ask if missing.

## Output

- Numbered headings according to the faculty template.
- Tables for functions, comparisons, or findings summaries.
- **Report language:** default to formal Malay with Malay headings unless the user asks for English.
- End with checklist status: passed items, failed items, gaps, and follow-up questions.

## Definition of done

All required components are present, the structure follows the chosen template, the chapter checklist passes, no facts are invented, there are no contradictions between chapters, and gaps are reported.

## Reference

- `docs/fyp-report-guide.md` - full guide.
- Original videos and template links are in §9 of the guide.
