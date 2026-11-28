---
title: "FYP Report Writing Guide - IT (USAS)"
description: "Structured guide for writing an IT Final Year Project report based on the lecturer video series from the Department of Information Technology, Universiti Sultan Azlan Shah (USAS). Covers the Gantt chart, Chapters 1-5, checklists, templates, and AI-agent instructions."
language: en
audience:
  - FYP students
  - AI agents
scope: "IT FYP reports only; multimedia content excluded"
last_updated: "2026-11-28"
verification: "Audio transcripts + visual frame review (2026-11-28)"
sources:
  - title: "Gantt Chart for Final Year Project, FYP - USAS"
    url: "https://youtu.be/u6MzDxlRv-U"
    speaker: "Husaini Bin Ibrahim"
    duration: "15:53"
  - title: "Bab 1: Pengenalan"
    url: "https://www.facebook.com/112651417084816/posts/196588235357800/"
    duration: "11:05"
  - title: "Bab 2: Kajian Literatur"
    url: "https://www.facebook.com/112651417084816/posts/196586912024599/"
    speaker: "Berhanuddin bin Ahmad"
    duration: "9:41"
  - title: "Bab 3: Metodologi Kajian (IT)"
    url: "https://www.facebook.com/112651417084816/posts/196585652024725/"
    duration: "9:40"
  - title: "Bab 4: Dapatan dan Perbincangan (IT)"
    url: "https://www.facebook.com/112651417084816/posts/196581335358490/"
    duration: "5:49"
  - title: "Bab 5: Kesimpulan dan Cadangan"
    url: "https://www.facebook.com/112651417084816/posts/196504138699543/"
    duration: "6:50"
template_links:
  gantt_chart: "https://docs.google.com/spreadsheets/d/1yKwRcezk9JG9PKF5cKIWdR_w8SF5x4lJxPpX1t7BoPE/edit?usp=sharing"
  fyp_report: "https://drive.google.com/file/d/1VWlgWGm9j7xYUYuBSA0m37Da15jE_W6T/view?usp=sharing"
---

# FYP Report Writing Guide - IT (USAS)

> This document is compiled from audio transcripts and a visual frame review of six lecturer videos from the USAS Department of Information Technology. Slides and the Gantt template were reviewed on 2026-11-28.
>
> This guide covers IT FYP reports only. Multimedia report structures are excluded.
>
> There are minor differences between the video content and the Gantt template structure. Sections 1.4 and 2.7 record those differences. Use the faculty report template as the structural reference and the videos as the content reference.
>
> Audience: FYP students and AI agents helping draft reports. Do not add chapters, data, or references that are not supported by the source.
>
> **Language:** This guide is in English. Unless the user asks otherwise, write the actual report in formal Malay and keep the report headings in Malay.

## Contents

- [0. How to Use This Document](#0-how-to-use-this-document)
- [1. Report Map and Workflow](#1-report-map-and-workflow)
- [2. Gantt Chart - Project Planning](#2-gantt-chart---project-planning)
- [3. Chapter 1 - Introduction](#3-chapter-1---introduction)
- [4. Chapter 2 - Literature Review](#4-chapter-2---literature-review)
- [5. Chapter 3 - Methodology](#5-chapter-3---methodology)
- [6. Chapter 4 - Findings and Discussion](#6-chapter-4---findings-and-discussion)
- [7. Chapter 5 - Conclusion and Recommendations](#7-chapter-5---conclusion-and-recommendations)
- [8. Master Checklist](#8-master-checklist)
- [9. Templates and Sources](#9-templates-and-sources)
- [10. AI Agent Instructions](#10-ai-agent-instructions)

## 0. How to Use This Document

### 0.1 Requirement labels

| Label | Meaning |
|---|---|
| **Must** | Requirement explicitly stated in the video. |
| **Should** | Practice recommended by the lecturer. |
| **Avoid** | Mistake criticised in the video. |
| **Note** | Additional explanation for organising the document; not a direct quote. |

### 0.2 For students

1. Start with the Gantt chart (Section 2) to plan the title and chapters.
2. Write Chapters 1 to 3, then build the system.
3. Write Chapter 4 only after the system is complete.
4. Finish with Chapter 5.
5. Check each chapter's checklist before submitting the draft to your supervisor.

### 0.3 For agents

1. Read Section 1 to identify the requested chapter.
2. Read that chapter's section, including its **required components**, **checklist**, and **outline**.
3. Follow Section 10 before generating any text.
4. Do not invent references, data, results, or dates. Mark missing information with `[NEED DATA: ...]` (or `[PERLU DATA: ...]` when writing in Malay).
5. Do not claim the work is complete if the chapter checklist is not satisfied; list the remaining gaps.

## 1. Report Map and Workflow

### 1.1 Purpose of each chapter

| Chapter | Name | Main question answered | When to write |
|---|---|---|---|
| 1 | Introduction (Pengenalan) | What is the problem, why is the project needed, and what are the objectives and scope? | Early, after the title is approved |
| 2 | Literature Review (Kajian Literatur) | What similar systems exist, and what can be learned from them? | After Chapter 1 |
| 3 | Methodology (Metodologi Kajian) | Who are the users, how is the system built, and what model and medium are used? | Before or during development |
| 4 | Findings and Discussion (Dapatan dan Perbincangan) | What are the results, were the objectives achieved, and why? | After the system is complete |
| 5 | Conclusion and Recommendations (Kesimpulan dan Cadangan) | What is the summary, significance, limitations, and recommendations? | Last |

### 1.2 Workflow

```text
Gantt chart -> Chapter 1 -> Chapter 2 -> Chapter 3 -> Build the system -> Chapter 4 -> Chapter 5
```

**Must:** Chapter 4 is written only after the system has been completed (Chapter 4 video).
**Must:** The literature review is not only for Chapter 2. It is needed in every chapter to support arguments (Chapter 1 video).
**Note:** This guide is for IT reports. The Chapter 3 and Chapter 4 videos are IT-specific.

### 1.3 Scope: IT only

This guide covers IT FYP reports only, meaning system development projects. Multimedia report structures are excluded. If your project is multimedia, do not use Chapters 3, 4, or 5 of this guide; consult your lecturer.

### 1.4 Video structure vs Gantt template

The Gantt template shown in the video has a more detailed task list than the components described in the videos. Use this table to avoid confusion.

| Chapter | Video content | Gantt template (sample tasks) |
|---|---|---|
| 1 | Six aspects: background, problem statement, research questions, research objectives, scope, significance/impact. | 1.1 Introduction (Pengenalan), 1.2 Background (Latar Belakang), 1.3 Problem Statement (Pernyataan Masalah), 1.4 Research Questions (Persoalan Kajian), 1.5 Research Objectives (Objektif Kajian), 1.6 Significance (Kepentingan Kajian), 1.7 Scope (Skop Kajian), 1.8 Summary (Rumusan). 1.9 Hypothesis (Hipotesis) is added as a demo, not part of the base template. |
| 2 | Title, concept, and functions of each reviewed system; the number of reviews depends on the university. | 2.1 Introduction, 2.2 Definition, 2.3 Review of Web Systems, 2.4 Related Web Examples (2.4.1-2.4.6), 2.5 Recommended Use of Web Functions, 2.6 Review of System Requirements, 2.7 Summary. |
| 3 | Five models: ADDIE, Spiral, XP, RAD, Agile, with phases and justification for the chosen model. | 3.1 Introduction, 3.2 Methodology Description, 3.2.1 Methodology Selection, 3.3 Project Development Phases (Planning, Requirements, Design and Analysis, Implementation, Testing, Evaluation and Maintenance), 3.4 System Requirements, 3.5 Development Tools and Software Requirements, 3.6 Summary. |
| 4 | System Development, System Model, User Interface Design, Discussion, Charts and Tables. | 4.1 Introduction, 4.2 System Development, 4.3 Web Modelling, 4.4 User Report, 4.5 Customer Report, 4.6 Web Administrator Report, 4.7 Discussion of Findings, 4.8 Summary. |
| 5 | IT: two parts, namely conclusion and recommendations. | 5.1 Introduction, 5.2 Development Constraints, 5.3 System Strengths and Weaknesses, 5.4 Improvement Recommendations, 5.5 Conclusion. |

**Conflict rules:**

1. Use the **faculty report template** as the primary reference for structure and numbering.
2. Use the **videos** as the reference for required content in each section.
3. Use the **Gantt template** as a planning and task-structure example. It was built for a web system project, so terms such as "Web" must be adapted to your system type.
4. If no faculty template is available, use the video structure and mark the Gantt template structure as an example only.

**Final report structure:** Chapters 1 to 5, then Bibliography and Appendices. The Gantt template shows Appendices A to D (Software Use Registration, Domain and Hosting Company Registration, Payment Method Registration, Web Development Method) and the start of Appendix E (Database Development); the full list follows the faculty template.

## 2. Gantt Chart - Project Planning

### 2.1 Purpose

A Gantt chart is a schedule of tasks and subtopics that must be completed within the period agreed with the supervisor. It serves as:

- a discussion plan with the supervisor about the direction, topics, and subtopics of the report;
- a milestone for completing the project by the agreed dates;
- a monitoring tool to keep the project on schedule.

### 2.2 Steps for using the template

1. Get the Gantt chart template through the link in Section 9. The template uses the columns `TUGAS` (Task), `MULA` (Start), `AKHIR` (End), `HARI` (Days), and Gantt bars by date.
2. Set the **semester start date** in the first date cell only. The week, day, and other dates update automatically.
3. Set the **duration in days** for each subtopic. The Gantt bar and end date update automatically.
4. If `#` appears, widen the column because there is not enough space to display the date.
5. If two subtopics can be completed on the same day, remove `+1` from the date formula so both start on the same date.
6. To add a new subtopic, select the last row, press `Ctrl` + `+`, enter the subtopic name, copy the date formula down, and enter the duration in days.
7. If the dates are misaligned, press `F2` on the date cell and check that the formula references the correct cell.
8. For the second semester, unmerge the semester cells and adjust the start date according to the academic calendar.
9. Align all dates with the academic calendar and the scheduled presentation dates.
10. Discuss the schedule with your supervisor. The template keeps the date columns visible when scrolling so the schedule is easy to discuss.

### 2.3 Date and formula rules

- **Must:** Change only the first start date; do not edit every date cell manually.
- **Must:** Enter a duration in days for every subtopic; without a duration, the bar will not appear.
- **Should:** Use the formula `=previous_cell + 1` for tasks that start one day after the previous task.
- **Should:** Remove `+1` if two tasks can be done on the same day.
- **Avoid:** Leaving a formula pointing to the wrong cell, which makes the dates misaligned.

### 2.4 USAS milestones

- At the first presentation, Chapters 1 to 3 should be complete and about **30% of the project** should have been developed.
- Example in the video: the first presentation is on **16 December**; the actual date depends on the academic calendar.
- If exam weeks or holidays fall within the project period, reduce task durations so the presentation date stays fixed.
- Example semester period in the video: **5 October to 3 December**; adjust it to your university calendar.

### 2.5 Gantt chart checklist

- [ ] Semester start date is correct.
- [ ] All Chapter 1 to Chapter 5 subtopics are in the schedule.
- [ ] Every subtopic has a duration in days.
- [ ] No `#` symbols are hiding the dates.
- [ ] Date formulas reference the correct cells.
- [ ] First and final presentation dates match the academic calendar.
- [ ] The schedule has been discussed with the supervisor.

### 2.6 Note for agents

Agents cannot edit Excel or Google Sheets files directly. If asked, produce a Markdown task table with the columns: `Task`, `Start date`, `Duration (days)`, `Dependency`, `End date`. Do not invent academic dates; ask the user for the real dates.

### 2.7 Task structure in the Gantt template

This structure was reviewed from the template's visual frames. It is a planning example for a web system project; task names may differ from the faculty report template. The task names below follow the Malay template, with English translations in parentheses.

#### 2.7.1 Chapter 1 - Introduction

Before Chapter 1, the template lists **Title Discussion (Perbincangan Tajuk)** as a planning task.

| No | Task |
|---|---|
| 1.1 | Introduction (Pengenalan) |
| 1.2 | Background (Latar Belakang) |
| 1.3 | Problem Statement (Pernyataan Masalah) |
| 1.4 | Research Questions (Persoalan Kajian) |
| 1.5 | Research Objectives (Objektif Kajian) |
| 1.6 | Significance (Kepentingan Kajian) |
| 1.7 | Scope (Skop Kajian) |
| 1.8 | Summary (Rumusan) |

**Note:** In the demo, the lecturer adds a `1.9 Hypothesis (Hipotesis)` row to show how to add a task. It is not part of the base template.

#### 2.7.2 Chapter 2 - Literature Review

| No | Task |
|---|---|
| 2.1 | Introduction (Pengenalan) |
| 2.2 | Definition (Definisi) |
| 2.3 | Review of Web Systems (Kajian Terhadap Web) |
| 2.4 | Related Web Examples (Contoh Web yang Berkaitan) |
| 2.4.1-2.4.6 | Web 1 to Web 6 |
| 2.5 | Recommended Use of Web Functions (Cadangan Penggunaan Fungsi Web) |
| 2.6 | Review of System Requirements (Kajian Terhadap Keperluan Sistem) |
| 2.7 | Summary (Rumusan) |

**Note:** The template provides six web examples. The video says the number of reviews depends on the university, typically a minimum of three to five. Adapt "Web" to the type of system being reviewed.

#### 2.7.3 Chapter 3 - Methodology

| No | Task |
|---|---|
| 3.1 | Introduction (Pengenalan) |
| 3.2 | Methodology Description (Penerangan Metodologi) |
| 3.2.1 | Methodology Selection (Pemilihan Metodologi) |
| 3.3 | Project Development Phases (Fasa Pembangunan Projek) |
| 3.3.1 | Planning Phase (Fasa Perancangan) |
| 3.3.1.1 | Use-Case Diagram (Rajah Use-Case) |
| 3.3.1.2 | Sequence Diagram (Rajah Sequence) |
| 3.3.1.3 | Class Diagram (Rajah Class) |
| 3.3.1.4 | DFD (Rajah DFD) |
| 3.3.2 | Requirements Phase (Fasa Keperluan) |
| 3.3.3 | Design and Analysis Phase (Fasa Rekabentuk dan Analisis) |
| 3.3.3.2 | Web Interface Design (Rekabentuk Antaramuka Web) |
| 3.3.3.3 | User Interface (Antaramuka Pengguna) |
| 3.3.3.4 | Service Provider Interface (Antaramuka Penyedia Perkhidmatan) |
| 3.3.3.5 | Payment Interface (Antaramuka Pembayaran) |
| 3.3.3.6 | Administrator Interface (Antaramuka Pentadbir) |
| 3.3.4 | Implementation Phase (Fasa Pelaksanaan) |
| 3.3.4.1 | Web User Manual (Manual Penggunaan Web) |
| 3.3.5 | Testing Phase (Fasa Pengujian) |
| 3.3.6 | Evaluation and Maintenance Phase (Fasa Penilaian dan Penyelenggaraan) |
| 3.4 | System Requirements (Keperluan Sistem) |
| 3.5 | Development Tools and Software Requirements (Keperluan Peralatan dan Perisian Pembangunan) |
| 3.6 | Summary (Rumusan) |

**Note:** The template numbering jumps from 3.3.3 to 3.3.3.2; there is no 3.3.3.1. Correct it according to the faculty format. These phases are an example for a web project; the actual model must be described according to the chosen methodology in the video (ADDIE, Spiral, XP, RAD, or Agile).

#### 2.7.4 Chapter 4 - Findings and Discussion

| No | Task |
|---|---|
| 4.1 | Introduction (Pengenalan) |
| 4.2 | System Development (Pembangunan Sistem) |
| 4.3 | Web Modelling (Pemodelan Web) |
| 4.4 | User Report (Laporan daripada Pengguna) |
| 4.5 | Customer Report (Laporan daripada Pelanggan) |
| 4.6 | Web Administrator Report (Laporan Pentadbir Web) |
| 4.7 | Discussion of Findings (Perbincangan Dapatan Kajian) |
| 4.8 | Summary (Rumusan) |

**Note:** "Web Modelling" corresponds to the system model in the video. Reports from users, customers, and administrators are findings sources that can be obtained through user testing, questionnaires, or interviews.

#### 2.7.5 Chapter 5 and appendices

| No | Task |
|---|---|
| 5.1 | Introduction (Pengenalan) |
| 5.2 | Development Constraints (Kekangan Pembangunan) |
| 5.3 | System Strengths and Weaknesses (Kelebihan dan Kekurangan Sistem) |
| 5.4 | Improvement Recommendations (Cadangan Penambahbaikan) |
| 5.5 | Conclusion (Kesimpulan) |

After Chapter 5, the template lists:

| Section | Visible task |
|---|---|
| Bibliography (Bibliografi) | Reference list |
| Appendix A (Lampiran A) | Software Use Registration (Pendaftaran Penggunaan Perisian) |
| Appendix B (Lampiran B) | Domain and Hosting Company Registration (Pendaftaran Domain dan Syarikat Hosting) |
| Appendix C (Lampiran C) | Payment Method Registration (Pendaftaran Kaedah Pembayaran) |
| Appendix D (Lampiran D) | Web Development Method (Kaedah Pembinaan Web) |
| Appendix E (Lampiran E) | Database Development (Pembinaan Pangkalan Data) - partially visible |

**Note:** The IT video describes two parts of Chapter 5: conclusion and recommendations. The template expands this into five subtopics, including constraints and system strengths/weaknesses. Follow the faculty template, and make sure the conclusion and recommendations content from the video is still present.

## 3. Chapter 1 - Introduction

### 3.1 Purpose

Chapter 1 informs the reader about:

- what the project or study will do;
- the current problem and its causes;
- why the problem must be solved;
- the objectives, scope, and significance of the study;
- the expected outcome.

### 3.2 Required components

| # | Component | Purpose |
|---|---|---|
| 1 | Background (Latar Belakang) | Explain the title, key concepts, current problem, and its causes. |
| 2 | Problem Statement (Penyataan Masalah) | Prove the problem exists using published sources. |
| 3 | Research Questions (Persoalan Kajian) | List the questions the study must answer. |
| 4 | Research Objectives (Objektif Kajian) | State what the study aims to achieve. |
| 5 | Scope (Skop Kajian) | Set the boundaries of the study. |
| 6 | Significance and Impact (Kesan Kajian) | State the impact on individuals, society, the country, and related parties. |

**Note:** The video slide explicitly lists six aspects: background, problem statement, research questions, research objectives, scope, and significance/impact. Some universities merge the significance component with another component, resulting in five components; the minimum is five. Follow your faculty format.

### 3.3 Rules for each component

#### 3.3.1 Background

- **Must:** Explain the key concepts in the project title.
- **Must:** State the current problem, why it occurs, and why the study is needed.
- **Must:** Support the argument with literature: who says the problem exists, related theories, and previous studies.
- Example in the video: for a title about learning during the PKP period, first explain what COVID-19 is, what learning is, and what PKP is before discussing the problem.

#### 3.3.2 Problem statement

- **Must:** Describe the background of the problem with evidence from published articles, journals, or books.
- **Avoid:** Stating the problem based on personal opinion without references. The video stresses that arguments must be supported by sources, not the author's assumptions.

#### 3.3.3 Research questions

- **Must:** List the questions the study intends to answer.
- **Must:** Each question must align with a research objective.

#### 3.3.4 Research objectives

- **Must:** At least two objectives.
- **Should:** Three objectives so that if one objective is not fully achieved, the others can still be assessed.
- **Avoid:** Too many or too few objectives.
- **Note:** The video notes that logically the research questions are formed first, but in practice objectives are often written first. What matters is that both align.

#### 3.3.5 Scope

- **Must:** Set the study boundaries, such as users, population, period, or the system being studied.
- **Avoid:** A scope that is too broad to complete, or too narrow to be meaningful.
- **Must:** If a question concerns a group outside the scope, state that it is outside the scope and recommend it for future study.
- Example in the video: if the study only involves USAS students, a question about students from other institutions is answered as outside the scope and included in future-study recommendations.

#### 3.3.6 Significance and impact

- **Must:** State the impact or significance of the study for individuals, society, the country, and related parties.
- **Note:** This component may be merged with another component if the university format requires five components.

### 3.4 Role of the literature review in Chapter 1

- **Must:** Use literature to prove the problem exists, not to state personal opinion.
- **Must:** Cite theories related to the title.
- **Must:** Cite previous studies that underpin the problem and objectives.
- **Note:** This literature requirement continues in other chapters, for example to justify the choice of methodology in Chapter 3.

### 3.5 Order and alignment

Typical order:

```text
Background -> Problem statement -> Research questions -> Research objectives -> Scope -> Significance and impact
```

**Must:** Keep the following chain consistent:

```text
Problem -> Research questions -> Objectives -> Scope -> Findings -> Conclusion
```

### 3.6 Chapter 1 checklist

- [ ] Key concepts in the title are explained.
- [ ] The current problem and its causes are stated.
- [ ] Every important argument is supported by literature.
- [ ] There is no personal opinion without references.
- [ ] Research questions align with objectives.
- [ ] There are two to three clear objectives.
- [ ] The scope has clear boundaries.
- [ ] Significance and impact are stated for individuals, society, and the country.
- [ ] There is no discussion outside the scope without stating the study limitation.

### 3.7 Chapter 1 outline

These are the actual report headings; keep them in Malay.

```markdown
1.1 Latar Belakang
1.2 Penyataan Masalah
1.3 Persoalan Kajian
1.4 Objektif Kajian
1.5 Skop Kajian
1.6 Kesan Kajian
```

**Note:** The numbering and order must follow the faculty template. The outline above is an example based on the components in the video. The Gantt template uses 1.1 Pengenalan to 1.8 Rumusan (see 2.7.1); if you use it, place the six aspects in 1.2-1.7 and add 1.1 Pengenalan and 1.8 Rumusan. The Gantt template places Significance (1.6) before Scope (1.7), while the video presents scope before impact; follow the faculty template.

### 3.8 Common Chapter 1 mistakes

- Discussing the problem without explaining the basic concepts in the title.
- Using personal opinion as evidence of the problem.
- Objectives that do not align with the research questions.
- A scope that is too broad or not stated at all.
- Missing the significance and impact component.

## 4. Chapter 2 - Literature Review

### 4.1 Definition and purpose

A literature review is a study of previous systems or projects that are similar to the system being developed. It is the second chapter of the student's academic project report.

Purpose:

- understand the concepts, functions, and standards of previous systems;
- ensure the new system is not built in isolation ("syok sendiri");
- ensure the system meets industry standards and external requirements;
- prevent the project concept from drifting away from actual needs.

### 4.2 Reference sources

| Source type | Suitable sources |
|---|---|
| General studies | Reference books, journals, articles, and published original studies |
| IT | Completed systems that have already been built |

**Must:** Sources must match the project type. If you are developing a system, review previous systems.

### 4.3 How to start the literature review

1. **Library research:** refer to books, journals, articles, or magazines related to the project.
2. **Direct observation:** observe completed systems at organisations, with the organisation's permission.

### 4.4 What to write for each system

For every system or study reviewed, write:

- **Title** of the system or project.
- **Concept** used by the system.
- **Functions** provided by the system.
- **Number of functions or reports** the system can produce.
- An understanding of the system from start to finish.

**Must:** The student must understand the reviewed system fully, not merely list its name.

### 4.5 Number of reviews

The number of reviews depends on university requirements. The video says the typical minimum is three to five, depending on the programme. The Gantt template provides six examples (2.4.1-2.4.6). Follow the faculty guidelines.

### 4.6 Chapter structure

**Must:** Follow the format set by the university, including numbering such as 2.1, 2.2, 2.3, and sub-subsections.

Example structure for each system:

```markdown
2.1 Pengenalan Sistem
2.2 Konsep Sistem
2.3 Fungsi Sistem
    2.3.1 Fungsi pertama
    2.3.2 Fungsi kedua
    2.3.3 Fungsi ketiga
```

**Note:** For an IT project, the concept section explains the system concept, and the functions section lists the main system functions.

### 4.7 Chapter 2 checklist

- [ ] Every reviewed system has a clear title.
- [ ] The concept of each system is explained.
- [ ] The functions of each system are explained.
- [ ] Sources match the project type.
- [ ] The number of reviews meets faculty requirements.
- [ ] Numbering and format follow the university template.
- [ ] The review shows an understanding from start to finish.
- [ ] The literature review is used to set the standard for the new system.

### 4.8 Chapter 2 outline

Generic outline based on the video components:

```markdown
2.1 Pengenalan
2.2 Sistem 1
    2.2.1 Pengenalan Sistem
    2.2.2 Konsep
    2.2.3 Fungsi
2.3 Sistem 2
2.4 Sistem 3
2.5 Kesimpulan
```

Gantt template outline for a web project:

```markdown
2.1 Pengenalan
2.2 Definisi
2.3 Kajian Terhadap Web
2.4 Contoh Web yang Berkaitan
    2.4.1 Web 1
    2.4.2 Web 2
    2.4.3 Web 3
    2.4.4 Web 4
    2.4.5 Web 5
    2.4.6 Web 6
2.5 Cadangan Penggunaan Fungsi Web
2.6 Kajian Terhadap Keperluan Sistem
2.7 Rumusan
```

**Note:** The second outline is the Gantt template structure for a web project; replace "Web" with the type of system being studied. If the faculty uses another format, follow the faculty.

### 4.9 Common Chapter 2 mistakes

- Reviewing systems unrelated to the project.
- Listing system names without explaining concepts and functions.
- Not understanding the system from start to finish.
- Not following the faculty numbering format.
- Insufficient number of reviews.

## 5. Chapter 3 - Methodology

### 5.1 Purpose

The methodology chapter explains:

- who the system users are;
- how the developer creates the system;
- the model or method used;
- the medium used to complete the study;
- why the method is suitable and effective for answering the research problem.

### 5.2 Basic structure

1. **Introduction:** briefly explain the method used to solve the research problem.
2. **Implementation model:** explain the chosen model and its phases.
3. **Closing:** state the methodology, data collection and analysis methods, the steps followed, and sample information.

### 5.3 Implementation models

The video lists five models: ADDIE, Spiral, XP, RAD, and Agile.

| Model | Main focus |
|---|---|
| ADDIE | Analysis, design, development, implementation, and evaluation of the system |
| Spiral | Customer communication, planning, risk analysis, and iterative evaluation |
| XP (Extreme Programming) | Rapid software development, simple design, and pair programming |
| RAD | Rapid application system development with analysis and design |
| Agile | Teamwork, continuous collaboration, and adaptation to customer needs |

#### 5.3.1 ADDIE

| Phase | What to write |
|---|---|
| Analysis | Objectives to achieve, materials to be used, and the student's existing capabilities and knowledge. |
| Design | Achieve the learning objectives, build storyboards and prototypes, and connect graphic design, users, and content. |
| Development | Combine the tools and processes used to create the system. |
| Implementation | Explain the meaning of implementation, the activities carried out, and the importance of user training. |
| Evaluation | Collect data to strengthen the problem statement, state the medium used for data collection, and prepare an evaluation report. |

#### 5.3.2 Spiral

- **Communication (Customer Communication):** between the researcher or system analyst and the customer.
- **Planning (Planning):** cost estimates, deadlines, scheduling, and identification of the work environment.
- **Risk Analysis:** identify potential risks, produce technical alternatives, and plan risk management.
- **Construction and Release:** test, record, and develop software; install software; build prototypes; plan documents; summarise software testing; report deficiencies for improvement.
- **Customer Evaluation:** the customer provides input and feedback, evaluates work products, and ensures requirements are met.
- **Must:** If changes occur, all stages are corrected according to customer satisfaction.
- **Must:** Identify and monitor risks such as cost overruns.

#### 5.3.3 XP (Extreme Programming)

- **Must:** Start with requirements gathering to understand the application.
- **Must:** Define the output to be produced, the application features, and the application functions.
- **Must:** Emphasise simple application design.
- **Should:** Use CRC Cards (Class Responsibility Collaborator) to identify and organise classes in object-oriented programming.
- **Programming phase:** this phase emphasises Pair Programming, where more than one person is involved in writing code.
- **Must:** Focus on testing the quality and functions of the application.

#### 5.3.4 RAD

- **Requirements:** identify information needs and problems to determine objectives, system boundaries, constraints, and alternative solutions.
- **Analysis:** determine system behaviour and the activities within the system.
- **Design Workshop phase:** identify alternative solutions, choose the best solution, create a programming plan, and state the tools used.
- **Modelling:** use Unified Modelling Language (UML).
- **Implementation phase:** show the programme or programme units converted from coding; deploy the system until it is ready to operate.

#### 5.3.5 Agile

- **Must:** Explain that Agile is a team process.
- **Must:** State the continuous collaboration with relevant parties and the customer's expectations of the project team.
- **Must:** Explain the team's division into three roles:
  - Project Owner/Client;
  - Manager/Scrum Master;
  - System Analyst.

**Should:** State why the model was chosen and link it to the project requirements. Example in the Chapter 5 video: Agile was chosen because the project required rapid adaptation to change.

**Gantt template structure:** 3.1 Introduction, 3.2 Methodology Description, 3.2.1 Methodology Selection, 3.3 Project Development Phases (Planning, Requirements, Design and Analysis, Implementation, Testing, Evaluation and Maintenance), 3.4 System Requirements, 3.5 Development Tools and Software Requirements, 3.6 Summary (see 2.7.3). This is a web project example; do not mix the template phases with the phases of the chosen model.

### 5.4 Closing the chapter

**Must:** Focus on the methodology used in the study.
**Must:** Explain qualitative research as the method for data collection and analysis.
**Must:** State the steps followed during data collection.
**Must:** Provide information about the study sample.

### 5.5 Chapter 3 checklist

- [ ] The introduction briefly states the method.
- [ ] The system users are identified.
- [ ] The implementation model is stated and explained.
- [ ] Each model phase is explained sufficiently.
- [ ] The reason for choosing the model is stated.
- [ ] The development tools and medium are stated.
- [ ] The data collection and analysis methods are stated.
- [ ] Data collection steps and sample information are included.
- [ ] The methodology aligns with the research problem and objectives.

### 5.6 Chapter 3 outline

These are the actual report headings; keep them in Malay.

```markdown
3.1 Pengenalan
3.2 Metodologi Kajian
    3.2.1 Model [nama model]
    3.2.2 Fasa Analisis
    3.2.3 Fasa Reka Bentuk
    3.2.4 Fasa Pembangunan
    3.2.5 Fasa Pelaksanaan
    3.2.6 Fasa Penilaian
3.3 Kaedah Pengumpulan dan Analisis Data
3.4 Sampel Kajian
3.5 Kesimpulan
```

**Note:** Phase names depend on the chosen model. Do not mix phases from different models in one methodology. If using the Gantt template, see 2.7.3; the template numbering and phases differ from the ADDIE outline above.

### 5.7 Common Chapter 3 mistakes

- Listing models without explaining their phases.
- Choosing a model without justification.
- Mixing phases from different models.
- Not stating the users, tools, or medium.
- Not explaining the data collection method and sample.
- Mixing example template phases with the phases of the actual model.

## 6. Chapter 4 - Findings and Discussion

### 6.1 Subtopics

For the IT programme, the video divides Chapter 4 into the following subtopics:

| Subtopic | Required content |
|---|---|
| System Development | Online data source and system functionality. |
| System Model | The model used during development, such as a use case diagram, data flow diagram, or flowchart. |
| User Interface Design | Screenshots of the system's main pages only. |
| Discussion | Comparison of findings with the hypothesis, objectives, or research problem, with reasons. |
| Charts and Tables | Bar charts, pie charts, line charts, histograms, tables, or diagrams to present data. |

**Gantt template structure:** 4.1 Introduction, 4.2 System Development, 4.3 Web Modelling, 4.4 User Report, 4.5 Customer Report, 4.6 Web Administrator Report, 4.7 Discussion of Findings, 4.8 Summary (see 2.7.4).

### 6.2 Rules

- **Must:** Write Chapter 4 only after the system has been completed.
- **Must:** Use various diagrams to explain the whole system.
- **Must:** Show screenshots of the main pages only, not every page.
- **Must:** In the discussion, state whether the findings match the hypothesis, objectives, or research problem.
- **Must:** If the findings match, explain why.
- **Must:** If the findings do not match, explain the cause and the problem encountered. Example in the video: a problem in the database section.
- **Should:** Use charts and tables to make the findings clearer and more effective.
- **Note:** Unlike Chapters 1 and 2, every argument in Chapter 4 does not need a citation or external evidence. The focus is on the findings from the study itself.

### 6.3 How to obtain findings

The video lists three methods:

1. Testing by target users.
2. Questionnaires.
3. Interviews.

### 6.4 Chapter 4 checklist

- [ ] The online data source is stated.
- [ ] System functionality is explained.
- [ ] The system model is included with suitable diagrams.
- [ ] The diagrams cover the whole system.
- [ ] Screenshots of the main pages are included.
- [ ] Findings are compared with the hypothesis, objectives, or research problem.
- [ ] Reasons are given for findings that match and do not match.
- [ ] Charts or tables are used to present data.
- [ ] User, customer, or administrator reports are included if the template requires them.
- [ ] There is no reliance on external citations for every argument.
- [ ] The chapter is written after the system is complete.

### 6.5 Chapter 4 outline

These are the actual report headings; keep them in Malay.

```markdown
4.1 Pengenalan
4.2 System Development
    4.2.1 Sumber Data Atas Talian
    4.2.2 Functionality
4.3 Model Sistem
4.4 User Interface Design
4.5 Dapatan Kajian
4.6 Perbincangan
4.7 Carta dan Jadual
4.8 Kesimpulan
```

**Note:** The order and numbering must follow the faculty template. The list above follows the topic order in the video. For the Gantt template structure (4.1-4.8), see 2.7.4.

### 6.6 Common Chapter 4 mistakes

- Writing Chapter 4 before the system is complete.
- Including too many screenshots or unimportant pages.
- Not comparing findings with the objectives.
- Not explaining the cause when an objective is not achieved.
- Not including user, customer, or administrator reports if the template requires them.
- Adding unnecessary citations for every finding.

## 7. Chapter 5 - Conclusion and Recommendations

### 7.1 IT structure

For the IT programme, Chapter 5 has two parts: **Conclusion** and **Recommendations**.

#### 7.1.1 Conclusion

**Must:** The conclusion is a summary of Chapter 1 through the findings.

Content:

1. Introduction to the chapter and the reason the project was developed.
2. A statement of whether the research objectives were achieved.
3. A summary of the methodology used and why it was suitable.
4. The significance and implications of the project for society, the community, or the university.
5. A summary of the project findings.

Example in the video: a patient information management system for Klinik USAS was developed because the clinic still recorded patient data manually. The study used Agile because the project required rapid adaptation. The example findings show that 50% of respondents agreed the system was needed. This number is an example only; do not copy it without real data.

#### 7.1.2 Recommendations

**Must:** Recommendations are divided into two types:

1. **Project improvement recommendations:** things that can be improved in the system that has been built.
2. **Future study recommendations:** things that can be studied or developed in the future.

Example in the video: if the system has no appointment section, recommend adding it in the future.

**Gantt template structure:** 5.1 Introduction, 5.2 Development Constraints, 5.3 System Strengths and Weaknesses, 5.4 Improvement Recommendations, 5.5 Conclusion (see 2.7.5). The IT video describes two parts, namely conclusion and recommendations; the template expands this into five subtopics and places the Conclusion at 5.5. Follow the faculty template and make sure the conclusion and recommendations content from the video is present.

### 7.2 Chapter 5 checklist

- [ ] The chapter begins with an introduction and the reason the project was developed.
- [ ] The status of objective achievement is stated.
- [ ] The methodology is summarised with justification.
- [ ] The significance and implications of the project are stated.
- [ ] The findings are summarised.
- [ ] Project improvement recommendations are stated.
- [ ] Future study recommendations are stated.
- [ ] Development constraints and system strengths/weaknesses are stated if the template requires them.
- [ ] There is no new data or results that are not in Chapter 4.
- [ ] There are no new external references that were not discussed earlier.

### 7.3 Chapter 5 outline

These are the actual report headings; keep them in Malay.

```markdown
5.1 Pengenalan
5.2 Kesimpulan
    5.2.1 Pencapaian Objektif
    5.2.2 Rumusan Metodologi
    5.2.3 Kepentingan dan Implikasi
    5.2.4 Rumusan Dapatan
5.3 Cadangan
    5.3.1 Cadangan Penambahbaikan Projek
    5.3.2 Cadangan Kajian Akan Datang
```

**Note:** If using the Gantt template, see 2.7.5 for the 5.1-5.5 structure.

### 7.4 Common Chapter 5 mistakes

- Including new findings or discussion that are not in Chapter 4.
- Not stating whether the objectives were achieved.
- Not summarising the methodology.
- Recommendations that are unrelated to the project's shortcomings.
- Not stating development constraints or system strengths/weaknesses if the template requires them.

## 8. Master Checklist

### 8.1 Before writing

- [ ] The Gantt chart has been prepared and discussed with the supervisor.
- [ ] The title and scope have been agreed.
- [ ] Project type: IT (system development).
- [ ] The faculty report template has been obtained.
- [ ] The numbering and citation format are known.

### 8.2 While writing

- [ ] Chapter 1 has a background, problem statement, research questions, objectives, scope, and significance/impact.
- [ ] Chapter 2 reviews relevant systems according to the faculty format.
- [ ] Chapter 3 explains the model, phases, tools, and data collection method.
- [ ] Chapter 4 is written after the system is complete and compares findings with the objectives.
- [ ] Chapter 5 summarises the whole report and gives recommendations.
- [ ] Chapter structure follows the faculty template; if using the Gantt template, refer to 2.7.
- [ ] The chain of problem, research questions, objectives, scope, findings, and conclusion is consistent.
- [ ] Every argument in Chapters 1, 2, and 3 is supported by sources.
- [ ] No data, references, or results have been invented.

### 8.3 Before submission

- [ ] All chapter checklists have been reviewed.
- [ ] Chapter and subtopic numbering is correct.
- [ ] Diagrams, tables, and screenshots have captions.
- [ ] References are formatted according to the faculty style.
- [ ] The bibliography and appendices are prepared.
- [ ] The report has been proofread for alignment and continuity.
- [ ] The draft has been submitted to the supervisor for review.

## 9. Templates and Sources

### 9.1 Templates

| Template | Link |
|---|---|
| Gantt chart | [Google Sheets](https://docs.google.com/spreadsheets/d/1yKwRcezk9JG9PKF5cKIWdR_w8SF5x4lJxPpX1t7BoPE/edit?usp=sharing) |
| FYP report | [Google Drive](https://drive.google.com/file/d/1VWlgWGm9j7xYUYuBSA0m37Da15jE_W6T/view?usp=sharing) |

The template links come from the Gantt chart video description. A check on 2026-11-28 found that the Google Sheets link returned HTTP 410 (Gone) and the Google Drive link returned HTTP 404 (Not Found). The links may have been moved or deleted; request the latest copy from your lecturer or class representative.

### 9.2 Source videos

| Video | Link | Duration | Focus |
|---|---|---|---|
| Gantt chart | [YouTube](https://youtu.be/u6MzDxlRv-U) | 15:53 | Planning and using the Gantt template |
| Bab 1 | [Facebook](https://www.facebook.com/112651417084816/posts/196588235357800/) | 11:05 | Introduction and Chapter 1 components |
| Bab 2 | [Facebook](https://www.facebook.com/112651417084816/posts/196586912024599/) | 9:41 | Literature review and reference sources |
| Bab 3 | [Facebook](https://www.facebook.com/112651417084816/posts/196585652024725/) | 9:40 | IT methodology models |
| Bab 4 | [Facebook](https://www.facebook.com/112651417084816/posts/196581335358490/) | 5:49 | Findings, discussion, and charts |
| Bab 5 | [Facebook](https://www.facebook.com/112651417084816/posts/196504138699543/) | 6:50 | Conclusion and recommendations |

**Note:** This document was compiled from automatic audio transcripts and a visual frame review. Some terms in the transcripts may have been misheard, but the slides and Gantt template were reviewed on 2026-11-28. Verify important details against the original videos or your lecturer.

**Items confirmed visually:**

- Chapter 1: six aspects and the term "Kesan kajian" (impact on individuals, society, and the country).
- Chapter 2: the speaker's name, Berhanuddin Bin Ahmad; numbering format and system structure confirmed.
- Chapter 3: ADDIE, Spiral, XP, RAD, and Agile phases and the phase terms shown.
- Chapter 4: subtopics System Development, System Model, User Interface Design, Discussion, Charts and Tables.
- Chapter 5: conclusion and recommendation steps.
- Gantt: columns TUGAS/MULA/AKHIR/HARI and the task list for Chapters 1-5, Bibliography, and Appendices A-E.

## 10. AI Agent Instructions

### 10.1 Agent contract

When helping write an FYP report:

1. **Follow the source structure.** Use the components, order, and rules in this document. Do not add chapters or subtopics that were not requested.
2. **Do not invent facts.** Do not create references, quotations, respondent data, test results, dates, organisation names, or statistics.
3. **Ask or mark gaps.** If information is missing, write `[NEED DATA: ...]` (or `[PERLU DATA: ...]` for Malay output) and list questions for the user.
4. **Maintain alignment.** Check the chain of problem, research questions, objectives, scope, findings, and conclusion before submitting a draft.
5. **Use an academic tone.** Write the report in formal Malay by default, and keep technical English terms where standard. Switch to English only if the user asks.
6. **Differentiate citations by chapter.** Chapters 1, 2, and 3 require source support. Chapter 4 prioritises the study's own findings. Chapter 5 does not add new data or references.
7. **Do not claim completion without review.** Run the chapter checklist and report what is still incomplete.
8. **Resolve conflicts by hierarchy.** Faculty report template > video content > Gantt template for structure. If no faculty template is available, use the video and mark the Gantt template structure as an example only.
9. **Do not copy specific examples.** Examples such as Klinik USAS, 50% of respondents, the meeting-room booking system, Web 1-6, and the 2020 dates are illustrations, not the user's project data.

### 10.2 Required input before writing

Ask for the following information if it is not already available:

- IT project title.
- The problem to be solved and its context.
- Target users and study scope.
- Research objectives.
- The methodology model used.
- A list of previous systems or studies for Chapter 2.
- Findings data, data collection method, and sample.
- System shortcomings and improvement recommendations.
- Faculty format: numbering, citation style, and report template.
- Structural source: faculty template or Gantt template (see 1.4 and 2.7).

### 10.3 Text generation rules

- **Chapter 1:** Build the background from the title, problem, and literature provided. Do not include personal opinion without references. Ensure the six video aspects are present: background, problem statement, research questions, objectives, scope, and significance/impact. Provide two to three objectives aligned with the research questions.
- **Chapter 2:** Review each system with its title, concept, and functions. Do not merely list system names. Follow the number of reviews required by the faculty. If using the Gantt template, the 2.1-2.7 structure is in 2.7.2.
- **Chapter 3:** Describe one methodology model unless the user asks for a comparison. Explain the model phases, tools, medium, data collection method, and sample.
- **Chapter 4:** Use only the data provided. Compare findings with the objectives. If the data is insufficient, mark the gap. Do not add external citations.
- **Chapter 5:** Summarise the existing content. Do not introduce new findings or references. Recommendations must relate to the stated shortcomings. If the Gantt template is used, include development constraints and system strengths/weaknesses (see 2.7.5).

### 10.4 Output format

- Use numbered headings according to the faculty template.
- Use tables for comparisons, function lists, or findings summaries.
- Use checklists to report status.
- Mark assumptions clearly: `[ASSUMPTION: ...]` (or `[ANDAIAN: ...]` for Malay output).
- Mark missing information: `[NEED DATA: ...]` (or `[PERLU DATA: ...]` for Malay output).
- End with a summary of gaps and follow-up questions.

### 10.5 Quick prompt for agents

```text
Read fyp-report-guide.md. Write [Chapter X] for the project [title].
Project type: IT. Problem: [...]. Users: [...].
Objectives: [...]. Methodology: [...]. Data/findings: [...].
Structural template: [faculty/Gantt]. Follow the required components, rules, and checklist for that chapter.
Do not invent references, data, or results. Mark [NEED DATA] if information is missing.
Check the alignment of objectives, scope, and findings before submitting the draft.
```

### 10.6 Definition of done

A chapter is complete when:

- all required components are present;
- the structure follows the chosen template;
- the chapter checklist is satisfied;
- no facts, references, or data have been invented;
- there are no contradictions with other chapters;
- remaining gaps have been listed for the user.
