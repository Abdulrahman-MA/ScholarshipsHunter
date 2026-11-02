# ScholarshipsHunter — Master Implementation Plan

> **Status:** plan only. No production code changed. Execution proceeds one phase at a time with an
> explicit stop for owner review at every phase exit.

**Goal:** Convert a working single-user scraper with an Excel file as its database into a measured,
queryable opportunity platform — DuckDB-backed analytics over an Excel+sites corpus, small-model
"System 1" evaluation, and a small research track that turns collected data into predictions — while
removing duplicate ingestion (aggregator channels) and paying down the structural debt that blocks
all of it.

**Architecture in one paragraph:** one transactional store (SQLite WAL now, Postgres-portable schema)
holds opportunities, raw documents, append-only evaluations, profiles and a leased ingest queue; one
writer module owns every mutation; DuckDB reads Parquet exports of that store for analytics, vector
search and research; Excel becomes a generated projection, not the source of truth; scrapers feed the
queue instead of rewriting a shared JSON file; evaluation is a two-speed pipeline (rules/embeddings/
tiny classifier → small model → 120B) with confidence-driven escalation and a frozen gold set as the
only quality gate.

---

## 1. Verified starting point (evidence)

Everything below was read from the checked-out repo at `41cc78b`, not inferred.

| ID | Finding | Evidence |
| :-- | :--- | :--- |
| E1 | No Excel data exists in this checkout. `*.xlsx` is gitignored; `data/` holds only `.gitkeep` and `raw_messages.txt`; `find -iname '*.xls*'` returns nothing. | `.gitignore` ("Excel Trackers"), `ls data/` |
| E2 | Excel is the system of record and is rewritten whole, three passes per batch (read → concat → write → reload-and-style). | `src/core/exporter.py:89`, `:114`, `:141-204` |
| E3 | Autosave cadence forces those full rewrites constantly: every 3 items in the main loop, every 5 in the deep evaluator. | `src/main.py:186`, `src/utils/deep_evaluator.py:185` |
| E4 | The only persistent identity store is one column: `processed_hashes(hash TEXT PRIMARY KEY)`. No source, title, timestamp, or FK. Created in 9 files. | `src/main.py:128,193,239,267`; `src/scrapers/{catchthatscholarship:116, gradschoolshopper:70, hussainsilat:84, mastersportal:47, profellow:44, scholarshipscorner:58, wemakescholars:47}`; `src/utils/reconcile_db.py:30` |
| E5 | Hashing is copy-pasted in 10 places, and source-specific key conventions exist only inside the reconcile script. Dedupe logic is split-brain. | `src/scrapers/*.py:19-24`, `src/main.py:121`, `src/utils/reconcile_db.py:11`, `:44-64`, `src/scrapers/whatsapp.py:82` |
| E6 | Reconciliation's primary operation is `DELETE FROM processed_hashes`, then rebuild from Excel + two data files that are not in the repo. | `src/utils/reconcile_db.py:104`; missing `data/aip_physics_master.csv`, `data/catchthatscholarship_cache.json` |
| E7 | The work queue is one JSON file, loaded whole and rewritten whole by every scraper; no per-item status, attempts, or atomic write. | `src/main.py:211,247,293`; `src/scrapers/mastersportal.py:175` |
| E8 | Concurrency is file-lock theatre: the Excel lock is **deleted after 30 s even if the holder is alive**; the backlog lock is a PID file with a 30-min validity window. | `src/core/exporter.py:67-85`; `src/main.py:78-113` |
| E9 | The applicant profile is a hardcoded string constant; fit scoring rules are duplicated verbatim in three prompt builders. | `src/core/config.py:24-43`; `src/core/matcher.py:168-187`, `:225-245`, `:280-297` |
| E10 | Model choice is literals in code (`openai/gpt-oss-120b`, a hardcoded Gemini candidate list) plus a global `USE_OLLAMA` boolean that the deep evaluator force-disables. | `src/core/matcher.py:251`, `:299`, `:100`; `src/utils/deep_evaluator.py:111`; `src/core/config.py:20-21` |
| E11 | Every item — a 40-word teaser or a 12 KB programme page — costs the same 120B call plus a 1.5 s pacing sleep. No pre-filter, no confidence, no routing. | `src/core/matcher.py:121`, `:149` |
| E12 | Six WhatsApp channels are hardcoded; at least one (`Scholarships Corner`) duplicates a site this repo already crawls via REST. | `src/scrapers/whatsapp.py:18-25`; `src/scrapers/scholarshipscorner.py` |
| E13 | The orchestrator prints "Data safely exported…" unconditionally, exits 0 even when sources fail, so the daily runner records a successful day. | `run_all.py:45-48`, `:88`; `src/utils/daily_runner.py:59-62`, `:78-79` |
| E14 | `src/main.py` is 306 lines mixing parse/queue/hydrate/hash/LLM/export/SQLite/DLQ/locks in one function; `run_all.py` fans out 8 subprocesses and can only see exit codes. | `src/main.py:18-306`; `run_all.py:59-67` |
| E15 | Deep evaluation overwrites the original score/rationale in the sheet — no evaluation history, so score calibration is impossible after the fact. | `src/utils/deep_evaluator.py:170-178` |
| E16 | Deadlines are free-text LLM output, stored verbatim; nothing is date-typed. | `src/core/matcher.py:27`; `src/core/exporter.py:37` |
| E17 | A second applicant's fit logic is hardcoded regexes + tiers in a generator script, duplicating matching logic outside `matcher.py`. | `src/utils/generate_mazen_tracker.py:18-21`, `:41`, `:57`, `:67-108` |
| E18 | No tests, no CI, no lint config, no lockfile in the tree; on this host `python -m pip` fails (`No module named pip`) and nothing from `requirements.txt` is installed. `uv 0.12.17` is available. | full-tree `find`; `python -m pip --version` |

**What this evidence forces:** the DB work cannot be "migrate at leisure" — E2/E3/E7/E8 mean every
additional source multiplies corruption risk. Measurement (Phase 0) must precede any "faster"/"same
quality" claim (E11/E18). The Excel import (A2) needs sheets the owner supplies (E1).

---

## 2. Honest technical position on the storage choice

The brief asked for "a db like duckdb for horizontal scaling". Stated plainly:

- **DuckDB is not a horizontal write-scale engine.** It is an embedded, single-process, columnar OLAP
  engine. Concurrent writers from multiple processes are not supported; it is excellent at scanning
  millions of rows, joining Parquet, and (via `vss`) vector search.
- **Therefore the plan uses DuckDB where it is strong** — analytics, vector search, statistics,
  experiment data — as a read layer over Parquet exported from the store, and keeps the transactional
  write path on SQLite (WAL) now with a Postgres-portable schema for the day concurrent writers must
  scale out.

Recorded as the `needs-decision` on issue **A1**.

**DECIDED (owner, 2026-11-03):** go with the recommended topology — DuckDB as the analytical
read layer over Parquet, a transactional store underneath with a Postgres-portable schema, and
SQLite (WAL) as the initial writer so Phase 1 can start before any server exists. Revisit only if
parallel scraper writes become the bottleneck; the migration path stays open because the schema
avoids SQLite-only constructs.

---

## 2b. Model tiering — resolved: these are System One *decision* models

The brief named "jev / kev / laya" for fast local/API analysis. They are real, and they are a
different species from generative LLMs. Recorded here because it changes the architecture:

| Model | What it is | Access | Size / context | Notes |
| :-- | :--- | :--- | :--- | :--- |
| **Jev** (TypeSafe AI) | Proprietary non-generative decision model. `POST /v1/systemone`, Bearer key, Python `typesafe-sdk` / Node `@typesafe-ai/sdk`; also resold on OpenRouter as `typesafe/jev-1.13`. | Hosted API (console.typesafe.ai keys); limited early access since 2026-09-15 | hosted; strongest accuracy in the family | Reference implementation of the family's API and calibration semantics |
| **Kev** (jaredpalmer) | Open-weights "Jev-like" decision model family, Apache-2.0, base Qwen3.5/3.8. Same `/v1/systemone` surface, so TypeSafe's SDK drives a local server unchanged. Fine-tunable; ships fitted temperatures. | Local, no PyPI package (name collision — install from source); needs Python 3.12/3.13 (torch has no 3.14 wheels) | 0.8B / 4B / 9B / 27B; validated 8,192 tokens (27B: 65,536); CPU, CUDA, MLX | 0.8B runs on a laptop; 4B is the recommended start |
| **Laya** (Convai Innovations) | Apache-2.0 non-autoregressive decision model on ModernBERT-large (`421M`), multilingual sister checkpoint on mmBERT-base (`322M`). `pip install laya`; also on Ollama (`laya`), GGUF, HTTP/MCP/LangChain extras. | Local, trivial install | 421M EN (512 ctx) / 322M multilingual (1024, up to 8k); ~33 ms per decision, p50 ≈ 33 ms on a T4 | RLCD-trained against strictly proper scoring rules → calibrated probabilities by construction |

**The architectural consequence, and my correction:** I previously framed this phase as "swap in a
smaller generative model". Wrong. All three answer **typed questions about supplied text** — `noul`
(yes/no), `choice` (multi-class), `score` (ordinal rating) — and return calibrated probabilities.
They never generate text, so they cannot extract a title, deadline, link or action item. What they
do extremely well is exactly the expensive half of the current work: *is this an opportunity, is it
in the right field, is it fully funded, is an Egyptian national eligible, does the GPA bar clear,
how urgent is it*. So the pipeline becomes:

```
raw text ──► decision tier (Laya 421M / Kev-0.8B→4B / Jev API)
             typed questions + calibrated probabilities, ~30-500 ms
             │
             ├─ high-confidence reject  ────────────► stored as rejected, no generative call
             ├─ high-confidence accept + needs fields ─► generative tier (small → 120B) for extraction
             └─ probability inside the uncertainty band ─► escalate (Kev-9B/27B or Jev, then 120B)
```

This is the actual "System 1 / System 2" split the project was reaching for: cheap calibrated
gating first, generative extraction only for survivors. Accuracy is verified on the frozen gold set
(C1), never assumed — and the gold set therefore has to carry decision-tier labels, not just scores.

---

## 3. Target layout

```
src/
  store/        schema.sql, migrate.py, db.py, writer.py, identity.py, queue.py,
                import_excel.py, export_excel.py        <- the only write path
  sources/      registry.py (or channels.json)          <- channel/source config as data
  scrapers/     (unchanged adapters, now queue-based)
  pipeline/     ingest.py, hydrate.py, evaluate.py, persist.py, export.py
  ai/           registry.py, decisions.py (Laya/Kev/Jev clients), extract.py, embed.py,
                prompts.py (single prompt builder)
  assist/       review.py, applier.py, rubrics/*.yaml
  analytics/    build_marts.py, duck.py, cli.py
  research/     deadlines.py, funnel.py, predict.py, calibration.py
  telemetry.py  run log (JSONL)
  cli.py        subcommands that replace the scattered entry points
data/
  lake/         parquet partitions (gitignored)
  gold/         committed labels (small, redacted)
  reports/      generated markdown (gitignored)
```

---

## 4. Phases, tasks, and exit checks

Task IDs match the GitHub issues created for this plan (index in §5).

### Phase 0 — Foundations and measurement
Nothing refactored before it can be measured.

- **0.1** Reproducible env: `pyproject.toml` from the 12 deps, `uv.lock`, `ruff` + `pytest`, GH Actions CI.
- **0.2** Baseline telemetry: per-stage ms, LLM calls/tokens, the three Excel passes timed separately, per-source yield.
- **E2** Split the monolith into stages + one CLI (keeps `HunterMenu.bat` / `RunDaily.bat` working).
- **E3** Truthful run summary and exit codes; the daily runner stops claiming success it did not have.
- **E3 requires E2.** `0.2` feeds every later before/after claim.

**Exit check:** `uv sync --frozen && ruff check . && pytest -q` green in CI; a baseline table posted
with real numbers from a real run; killing one scraper makes the orchestrator exit non-zero.

### Phase 1 — Data platform (Excel → store → DuckDB)
- **A1** Canonical schema + idempotent migrations (opportunities, raw_documents, evaluations,
  profiles, applications, ingest_queue, channel_registry, sources).
- **A2** Excel importer: lossless, dry-run first, idempotent, legacy score/rationale preserved as a
  `legacy_import` evaluation (never invented).
- **A3** Excel demoted to a projection with one writer and real locks; deep checks become evaluation
  rows, not cell edits; atomic temp-file writes.
- **A4** DuckDB layer: Parquet marts (`mart_source_funnel`, `mart_score_distribution`,
  `mart_deadline_calendar`, `mart_dup_rate`) + a query CLI.
- **A5** Identity consolidation: one `canonical_key`/`canonical_url`/`content_hash` module, legacy
  key formats preserved as aliases, reconcile rewritten to report instead of delete.
- **E1** DB-backed leased queue replacing `scraped_backlog.json` (migration path from the JSON file).

**Exit check:** every sheet row present exactly once with provenance; `grep` proves no `INSERT INTO`
outside `src/store/`; a 3-process × 50-item concurrency test acks exactly 150 rows with zero double
evaluation; `analytics.cli funnel` answers from Parquet with no Excel in the loop.

### Phase 2 — Source consolidation (aggregator channels → upstream sites)
- **B1** Provenance audit: per channel, item count, % of items linking to an already-crawled domain,
  median lag, and — the number that actually matters — items that exist **only** on the channel.
- **B2** Channel registry as data (`enabled`, `origin_site`, `duplicate_of`); disable the relays the
  audit proves redundant; no channel literals left in code.
- **B3** Backfill upstream sites of removed channels; diff unique coverage before/after.
- **B3 depends on B1 + A5 + E1.**

**Exit check:** published provenance table; channel set changed by config alone; unique qualified
opportunities after cutover ≥ before, at equal or lower AI spend.

### Phase 3 — System-1 decision tier and model tiering
- **C1** Frozen gold set (~300 real items, stratified, hand-labelled) carrying **decision-tier labels**
  (`is_opportunity`, `field_fit` choice, `fully_funded`, `egypt_eligible`, `gpa_clear`, `priority`
  score) plus field-extraction expectations. Freeze before any tuning.
- **C4** Model registry (`config/models.yaml`) covering two distinct roles — decision models
  (Laya/Kev/Jev) and generative extractors — with per-stage routing, replacing the global
  `USE_OLLAMA` boolean.
- **C2** Decision tier as the pre-filter: `consensus` gate from Laya (421M, ~33 ms) over typed
  questions, Kev-0.8B as a second opinion where the two disagree, threshold routing on calibrated
  probabilities with an explicit uncertainty band.
- **C3** Generative extraction tier only for survivors (small → 120B), with escalation driven by
  decision-tier confidence and schema validity; single shared prompt builder replacing the three
  drifted copies.

**Exit check:** decision-tier rejections contain no `is_opportunity=True` gold item beyond the
declared error budget; the tiered pipeline's field-level accuracy is ≥ the 120B-only baseline on the
gold set with a stated delta; mean cost and p50 latency per item are strictly lower per source;
escalation rate and per-tier share are reported.

**Note on the environment:** Kev needs Python 3.12/3.13 (no torch wheels for 3.14, which is this
host's default interpreter) — `uv` pins a 3.13 toolchain for it, or Laya (pure `pip install laya`)
carries the tier until that exists.

### Phase 4 — Embeddings, classifiers, assistants
- **D1** Embedding index over documents/opportunities/profiles (sqlite-vec or `duckdb vss`), versioned
  model ids, near-duplicate report (report only — no auto-merge this phase).
- **D2** Paper-review assistant: rubric as YAML, per-criterion evidence spans quoted from the document,
  unsupported-claim flags citing the opportunity text.
- **D3** Personal-info helper + applier assistant: profiles as data (second applicant without code
  changes), requirements extraction, document/fee/deadline checklist, gap report, ICS calendar.
  Hard boundary: read-only against portals, no submission, no credentials.

**Exit check:** paraphrase retrieval top-3 hit on a fixture; 3 planted false claims in a review fixture
all flagged; a real open opportunity's checklist verified by hand; profile #2 works with zero code edits.

### Phase 5 — Methodology, statistics, prediction (experimental)
- **F1** Typed deadlines: `deadline_raw` kept, `deadline_date` parsed with confidence + source; cycle
  clustering; measured parse rate.
- **F2** Source funnel + cost report (qualified per hour, qualified per dollar), reconciled against the
  orchestrator summary.
- **F3** Reopening-date prediction with two baselines, time-split backtest, MAE in days, honest
  intervals, explicit `no_estimate` where evidence is thin.
- **F4** Score calibration (Brier, reliability, nDCG@10 vs. the owner's manual shortlist), record user
  verdicts that `clean_excel.py` currently throws away, experimental re-ranker, and budget-to-source
  allocation against a random-order control.

**Exit check:** every claim carries an out-of-sample number and a snapshot hash; a "no improvement"
result is an acceptable, recorded outcome.

---

## 5. Issue index

Created on `Abdulrahman-MA/ScholarshipsHunter` — 31 issues, 6 milestones, 14 labels.

| Phase | Epic | Tasks |
| :-- | :-- | :--- |
| 0 — Foundations | [#5 Epic E](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/5) | [#7 0.1 env/CI](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/7), [#8 0.2 baseline](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/8), [#25 E2 modularize](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/25), [#26 E3 truthful exit](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/26) |
| 1 — Data platform | [#1 Epic A](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/1) | [#9 A1 schema](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/9), [#10 A2 Excel import](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/10), [#11 A3 Excel→projection](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/11), [#12 A4 DuckDB marts](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/12), [#13 A5 identity](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/13), [#24 E1 DB queue](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/24) |
| 2 — Sources | [#2 Epic B](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/2) | [#14 B1 provenance audit](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/14), [#15 B2 registry+disable](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/15), [#16 B3 backfill sites](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/16) |
| 3 — System-1 tiering | [#3 Epic C](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/3) | [#17 C1 gold set+harness](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/17), [#18 C2 pre-filter](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/18), [#19 C3 small-model tier](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/19), [#20 C4 model registry](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/20) |
| 4 — Assistants | [#4 Epic D](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/4) | [#21 D1 embeddings](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/21), [#22 D2 paper reviewer](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/22), [#23 D3 applier](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/23) |
| 5 — Research | [#6 Epic F](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/6) | [#27 F1 deadlines](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/27), [#28 F2 funnel/cost](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/28), [#29 F3 reopening prediction](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/29), [#30 F4 calibration](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/30) |

Tracking issue: [#31 Roadmap](https://github.com/Abdulrahman-MA/ScholarshipsHunter/issues/31).

Sequencing constraints that invert numeric order:
- **C1 (freeze gold set) must precede any tuning in C2/C3/C4** — the eval exists to be frozen.
- **B1 must precede B2**; **A5 must precede B3** (canonical keys are what makes the coverage diff meaningful).
- **E1 must precede B3** (backfill writes into the queue).
- **A1 must precede everything in Phase 1**; **A3 requires A2** (import before you can project).

---

## 6. Risks and trade-offs

1. **Two stores during the transition** (SQLite + Parquet). Mitigated by making Parquet strictly
   derived and rebuildable; `A4`'s acceptance requires rebuilding marts from the store alone.
2. **Gold-set overfitting.** Mitigated by freezing, by keeping `gold_v2` separate with a changelog, and
   by never re-labelling during a tuning phase.
3. **Fast-path false negatives** cost real opportunities, unlike false positives. Hence the
   "no opportunity misclassified as non-opportunity beyond a declared budget" criterion in C2 and the
   rule that ambiguous items escalate rather than being guessed.
4. **Channel removal can silently lose coverage.** B1's "unique only on channel" column exists precisely
   to price that loss before B2 merges.
5. **DuckDB does not solve write concurrency.** Addressed head-on in §2; the schema stays portable so
   moving to Postgres is a migration, not a rewrite.
6. **Scope.** Phase 4 and 5 could grow without bound. Rule: an experimental issue that proves nothing
   gets closed with a recorded negative result.
7. **The sheets don't exist in this checkout (E1).** A2 cannot produce real numbers until the owner
   supplies them; the importer is written and unit-tested against fixtures in the meantime. **Owner
   confirmed the sheets/CSVs will be uploaded later** — Phase 1 tasks A2/A3 stay blocked on that
   upload for their real acceptance, but A1/A4/A5 and all of Phase 0 are not.
8. **Decision-model substitution risk.** Laya/Kev/Jev are calibrated and fast but they are not
   extractors; a decision-tier "no" that is wrong silently deletes a real opportunity. Mitigated by
   declared error budgets, by using the probability *band* rather than a single threshold, by
   keeping a second-opinion model for disagreements, and by never letting the decision tier decide
   field values. Jev's third-party price and Kev's Python 3.13 constraint are both unverified against
   the live systems until C4's health check runs.

---

## 7. Decisions — status as of 2026-11-03

**Resolved by the owner:**

2. **Storage topology (A1) — DECIDED:** DuckDB as the analytical read layer over Parquet, transactional
   store underneath with a Postgres-portable schema, SQLite (WAL) as the initial writer. Start here;
   migrate only if parallel writes become the bottleneck.
3. **Small-model naming (C4) — RESOLVED:** the three are the System One decision-model family —
   **Jev** (TypeSafe, hosted API), **Kev** (open weights, 0.8B/4B/9B/27B, local), **Laya** (421M,
   Apache-2.0, ~33 ms, local). See §2b. Consequence: they gate and score, they do not extract.

**Still open:**

1. **Sheets to import (blocks A2/A3's real acceptance):** owner will upload the `.xlsx`/CSV files later.
   When they land: is `Mazen_Scholarships_Tracker.xlsx` a second profile (recommended — it validates
   multi-profile support in D3) or a throwaway?
4. **Channels to drop (B2):** after B1's provenance table. Default rule — drop any channel with ≥70%
   overlap with already-crawled domains and near-zero unique-only items; keep `Erasmus+` and
   `Acadia Italia` unless B1 shows direct coverage.
5. **Gold set location:** committed redacted in-repo (recommended) vs. local-only with metrics
   committed.
6. **Decision-tier deployment order:** Laya first (pure `pip install laya`, no torch, no GPU), then
   Kev-0.8B/4B once a 3.13 toolchain is pinned — versus going straight to Kev-4B for accuracy.
   Recommended: Laya first, because it unblocks C2 without a toolchain fight.
