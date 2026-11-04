# Graph Report - ScholarshipsHunter  (2026-11-04)

## Corpus Check
- 34 files · ~27,705 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 285 nodes · 482 edges · 26 communities (15 shown, 6 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2d35b723`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_desktop.py
- app.js
- runner.py
- tracker.py
- Issue index
- matcher.py
- 🎓 Scholarships Hunter: Autonomous Multi-Source Scholarship & Fellowship Intelligence Engine
- main.py
- mock.js
- Desktop app: JS ⇄ Python contract (issue #32)
- ScholarshipsHunter Workspace Guidelines & Privacy Invariants
- manual_login.py
- run_all.py
- hussainsilat.py
- scholarshipscorner.py
- mastersportal.py
- profellow.py
- wemakescholars.py
- daily_runner.py
- deep_evaluator.py
- reconcile_db.py

## God Nodes (most connected - your core abstractions)
1. `Api` - 15 edges
2. `_safe()` - 12 edges
3. `call()` - 12 edges
4. `bind()` - 12 edges
5. `evaluate_opportunity()` - 11 edges
6. `TaskManager` - 11 edges
7. `load_rows()` - 11 edges
8. `OpportunityExtraction` - 10 edges
9. `parse_deadline()` - 10 edges
10. `Issue index` - 10 edges

## Surprising Connections (you probably didn't know these)
- `test_overview_counts_closing_yield_and_backlog()` --calls--> `overview()`  [EXTRACTED]
  tests/test_desktop.py → src/desktop/tracker.py
- `test_mask_key_shows_only_edges()` --calls--> `mask_key()`  [EXTRACTED]
  tests/test_desktop.py → src/desktop/bridge.py
- `test_validate_args_defaults_and_bounds()` --calls--> `validate_args()`  [EXTRACTED]
  tests/test_desktop.py → src/desktop/runner.py
- `test_parse_deadline_formats()` --calls--> `parse_deadline()`  [EXTRACTED]
  tests/test_desktop.py → src/desktop/tracker.py
- `test_parse_deadline_garbage_is_none()` --calls--> `parse_deadline()`  [EXTRACTED]
  tests/test_desktop.py → src/desktop/tracker.py

## Import Cycles
- None detected.

## Communities (26 total, 6 thin omitted)

### Community 0 - "test_desktop.py"
Cohesion: 0.08
Nodes (23): fixture, parametrize, Api, mask_key(), Any, JS-facing API for the pywebview window (see docs/design/desktop-api.md). Every…, Show only the first 4 and last 4 characters of an API key., _safe() (+15 more)

### Community 1 - "app.js"
Cohesion: 0.15
Nodes (37): bind(), evaluateLink(), call(), clearError(), currentFilters(), currentRow(), dash(), dayWord() (+29 more)

### Community 2 - "runner.py"
Cohesion: 0.08
Nodes (22): Popen, Scholarships Hunter desktop app (pywebview). Run with: python -m src.desktop, Arg, _count_rows(), daily_schedule(), _kill_tree(), _load_state(), LogBuffer (+14 more)

### Community 3 - "tracker.py"
Cohesion: 0.13
Nodes (32): DataFrame, date, _backlog_count(), _dlq_entries(), _empty_frame(), levels_of(), _load_frame(), load_rows() (+24 more)

### Community 4 - "Issue index"
Cohesion: 0.07
Nodes (25): 1. Verified starting point (evidence), 2. Honest technical position on the storage choice, 2b. Model tiering — resolved: these are System One *decision* models, 3. Target layout, 4. Phases, tasks, and exit checks, 5. Issue index, 6. Risks and trade-offs, 7. Decisions — status as of 2026-11-03 (+17 more)

### Community 5 - "matcher.py"
Cohesion: 0.21
Nodes (16): BaseModel, clean_scholarship_text(), EligibilityVerdict, evaluate_opportunity(), evaluate_with_gemini(), evaluate_with_groq(), evaluate_with_ollama(), get_gemini_keys() (+8 more)

### Community 6 - "🎓 Scholarships Hunter: Autonomous Multi-Source Scholarship & Fellowship Intelligence Engine"
Cohesion: 0.12
Nodes (16): 1. 8 Multi-Source Crawlers, 1. Clone the Repository, 2. Multi-Key Rotating AI Pool (Groq 120B + Gemini Flash), 2. Set Up Virtual Environment & Dependencies, 3. Concurrency & Fault Tolerance, 3. Configure Your Environment Variables, 📊 Excel Output Structure (`scholarships_tracker.xlsx`), 🌟 Key Architecture & Capabilities (+8 more)

### Community 7 - "main.py"
Cohesion: 0.26
Nodes (11): apply_excel_formatting(), export_to_excel(), main(), extract_channel_messages(), get_text_hash(), load_processed_db(), parse_playwright_live(), parse_whatsapp_export() (+3 more)

### Community 8 - "mock.js"
Cohesion: 0.31
Nodes (5): clock(), nameOf(), pad(), pushLog(), sourceByKey()

### Community 9 - "Desktop app: JS ⇄ Python contract (issue #32)"
Cohesion: 0.40
Nodes (4): Desktop app: JS ⇄ Python contract (issue #32), Methods, Opportunity object, Task keys

### Community 10 - "ScholarshipsHunter Workspace Guidelines & Privacy Invariants"
Cohesion: 0.40
Nodes (4): 1. Zero Secret & Dossier Leaks to Git, 2. API Key Management, 3. Data Integrity & Concurrency, ScholarshipsHunter Workspace Guidelines & Privacy Invariants

### Community 11 - "manual_login.py"
Cohesion: 0.70
Nodes (4): launch_scrapers_session(), launch_whatsapp_channels(), launch_whatsapp_session(), run()

### Community 12 - "run_all.py"
Cohesion: 0.83
Nodes (3): main(), run_pipeline(), stream_output()

### Community 13 - "hussainsilat.py"
Cohesion: 0.83
Nodes (3): fetch_page_html(), get_hash(), run()

### Community 14 - "scholarshipscorner.py"
Cohesion: 0.83
Nodes (3): clean_html(), get_hash(), run()

## Knowledge Gaps
- **41 isolated node(s):** `Arg`, `1. Zero Secret & Dossier Leaks to Git`, `2. API Key Management`, `3. Data Integrity & Concurrency`, `1. 8 Multi-Source Crawlers` (+36 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 86 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Are the 2 inferred relationships involving `bind()` (e.g. with `evaluateLink()` and `loadOpportunities()`) actually correct?**
  _`bind()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Arg`, `1. Zero Secret & Dossier Leaks to Git`, `2. API Key Management` to the rest of the system?**
  _41 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_desktop.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08367071524966262 - nodes in this community are weakly interconnected._
- **Should `runner.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08403361344537816 - nodes in this community are weakly interconnected._
- **Should `tracker.py` be split into smaller, more focused modules?**
  _Cohesion score 0.13068181818181818 - nodes in this community are weakly interconnected._
- **Should `Issue index` be split into smaller, more focused modules?**
  _Cohesion score 0.07407407407407407 - nodes in this community are weakly interconnected._
- **Should `🎓 Scholarships Hunter: Autonomous Multi-Source Scholarship & Fellowship Intelligence Engine` be split into smaller, more focused modules?**
  _Cohesion score 0.11764705882352941 - nodes in this community are weakly interconnected._