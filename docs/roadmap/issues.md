# Issue index

> Generated snapshot of the GitHub issue set for the master plan
> ([`docs/plans/2026-11-03-scholarships-hunter-master-implementation-plan.md`](../plans/2026-11-03-scholarships-hunter-master-implementation-plan.md)).
> The live tracker is the issue list; this file exists so the plan and its work breakdown travel together in git.

**31 issues** · 6 milestones · labels: `area/*`, `phase/*`, `experimental`, `needs-decision`

## At a glance

| Phase | Epic | Task keys |
| :-- | :-- | :-- |
| Phase 0 — Foundations and measurement | [#5](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/5) | [0.1](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/7) · [0.2](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/8) · [E2](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/25) · [E3](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/26) · [#31](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/31) |
| Phase 1 — Data platform | [#1](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/1) | [A1](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/9) · [A2](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/10) · [A3](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/11) · [A4](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/12) · [A5](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/13) · [E1](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/24) |
| Phase 2 — Source consolidation | [#2](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/2) | [B1](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/14) · [B2](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/15) · [B3](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/16) |
| Phase 3 — System-1 decision tier and model tiering | [#3](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/3) | [C1](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/17) · [C2](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/18) · [C3](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/19) · [C4](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/20) |
| Phase 4 — Embeddings and assistants | [#4](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/4) | [D1](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/21) · [D2](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/22) · [D3](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/23) |
| Phase 5 — Statistics and prediction (experimental) | [#6](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/6) | [F1](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/27) · [F2](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/28) · [F3](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/29) · [F4](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/30) |

---

## Phase 0 - Foundations and measurement

- [ ] **#5** Epic E - Performance and structure: honest runs, real locks, small modules  
      `area/perf`, `phase/0`
- [ ] **#7** 0.1: Bootstrap reproducible environment, lint and CI  
      `area/infra`, `phase/0`
- [ ] **#8** 0.2: Instrument a baseline: per-stage timings, LLM calls, tokens, Excel IO, source yield  
      `area/perf`, `phase/0`
- [ ] **#25** E2: Split the monolith into pipeline stages with a single CLI  
      `area/perf`, `phase/0`
- [ ] **#26** E3: Make the run summary and exit status truthful per source  
      `area/perf`, `phase/0`
- [ ] **#31** Roadmap: Excel -> DuckDB platform, source consolidation, System-1 tiering, assistants, and prediction research  
      `area/data`, `area/infra`, `phase/0`

## Phase 1 - Data platform

- [ ] **#1** Epic A - Data platform: Excel sheets + site ingestion into a DuckDB-backed store  
      `area/data`, `phase/1`
- [ ] **#9** A1: Canonical schema and migrations for opportunities, sources, raw documents, evaluations, profiles, applications  
      `area/data`, `phase/1`
- [ ] **#10** A2: Import every existing Excel sheet into the store, losslessly and idempotently  
      `area/data`, `phase/1`, `needs-decision`
- [ ] **#11** A3: Demote Excel to a projection: one writer, real locks, no read-modify-write  
      `area/data`, `area/perf`, `phase/1`
- [ ] **#12** A4: DuckDB analytical layer: Parquet marts, vector search, and a query CLI  
      `area/data`, `area/perf`, `phase/1`
- [ ] **#13** A5: Consolidate identity and deduplication: one canonical-key module, one hash table  
      `area/data`, `area/perf`, `phase/1`
- [ ] **#24** E1: Replace the JSON backlog with a leased database queue  
      `area/data`, `area/perf`, `phase/1`

## Phase 2 - Source consolidation

- [ ] **#2** Epic B - Source consolidation: drop aggregator channels, ingest their upstream sites  
      `area/sources`, `phase/2`
- [ ] **#14** B1: Measure channel provenance: which WhatsApp channels merely relay sites we already crawl  
      `area/sources`, `phase/2`
- [ ] **#15** B2: Move the channel list into a registry and disable redundant relay channels  
      `area/sources`, `phase/2`, `needs-decision`
- [ ] **#16** B3: Backfill the upstream sites of removed channels so unique coverage does not drop  
      `area/sources`, `phase/2`

## Phase 3 - System-1 decision tier and model tiering

- [ ] **#3** Epic C - System-1 fast path: cheap models first, escalate only on doubt  
      `area/ai`, `phase/3`
- [ ] **#17** C1: Freeze a gold set and build the model evaluation harness  
      `area/ai`, `area/research`, `phase/3`
- [ ] **#18** C2: System-1 decision gate - calibrated Laya/Kev typed questions decide the easy majority  
      `area/ai`, `phase/3`
- [ ] **#19** C3: Generative extraction for survivors only, with confidence-based escalation  
      `area/ai`, `phase/3`
- [ ] **#20** C4: Model registry and per-stage routing for decision models and extractors  
      `area/ai`, `phase/3`

## Phase 4 - Embeddings and assistants

- [ ] **#4** Epic D - Embeddings and small classifiers: paper reviewer, personal-info helper, applier  
      `area/ai`, `phase/4`
- [ ] **#21** D1: Embedding index over opportunities, raw documents and applicant profiles  
      `area/data`, `area/ai`, `phase/4`
- [ ] **#22** D2: Paper-review assistant with a written rubric and evidence spans  
      `area/ai`, `phase/4`, `experimental`
- [ ] **#23** D3: Personal-info helper and applier assistant: profile, checklists, gap analysis  
      `area/ai`, `phase/4`, `experimental`

## Phase 5 - Statistics and prediction (experimental)

- [ ] **#6** Epic F - Methodology, statistics and prediction (experimental)  
      `area/research`, `phase/5`, `experimental`
- [ ] **#27** F1: Type the deadline and parse it: raw text + a real date + cycle detection  
      `area/data`, `area/research`, `phase/5`
- [ ] **#28** F2: Source funnel and cost analytics: which sources earn their AI spend  
      `area/research`, `phase/5`
- [ ] **#29** F3: Experimental: predict reopening dates and next-cycle deadlines  
      `area/research`, `phase/5`, `experimental`
- [ ] **#30** F4: Experimental: score calibration, ranking quality, and source-yield prediction  
      `area/research`, `phase/5`, `experimental`

---

Tracking issue: **#31 Roadmap** (this file mirrors it).

## Sequencing constraints (they invert numeric order)

- **C1** (freeze the gold set and its decision-tier labels) must precede any tuning in C2/C3/C4.
- **C4** precedes C2/C3 in practice — the registry is what names the models.
- **B1** must precede **B2** (no channel removed without provenance numbers).
- **A5** and **E1** must precede **B3** (canonical keys + queue before backfill).
- **A1** precedes everything in Phase 1; **A3** requires **A2** (import before projection).

## Standing rules

1. No claim of "faster", "cheaper" or "same quality" without a measurement on the frozen gold set.
2. No source removed without a provenance table.
3. Nothing writes opportunity rows outside `src/store/writer.py`.
4. An experimental issue may close with a recorded negative result — that is success, not failure.
