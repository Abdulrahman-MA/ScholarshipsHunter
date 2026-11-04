# Desktop app: JS ⇄ Python contract (issue #32)

Stack: pywebview. Front end in `src/desktop/ui/`, Python in `src/desktop/`. JS calls `await window.pywebview.api.<method>(...)`; every method returns plain JSON. Errors are returned as `{"error": "message"}`, never raised to JS.

## Opportunity object
```
{ id, title, institution, category, type, deadline,          // deadline = raw text from Excel
  deadline_iso: "YYYY-MM-DD"|null, days_left: int|null,
  funding, fields, link, score: int|null, tier: "fit"|"maybe"|"no"|null,
  rationale, action_items, source, scraped_date, deep_checked }
```
Tier thresholds follow the Green/Yellow/Red colouring in `src/core/exporter.py`.

## Methods
| method | returns |
|---|---|
| `get_overview()` | `{total, fit, maybe, no, backlog, last_sweep, next_sweep, closing:[Opportunity] (days_left 0..30, soonest first), yield:[{source, count, failed}] (scraped in last 7 days)}` |
| `list_opportunities(filters)` filters=`{q, tier, funding, level, sort}` sort ∈ `deadline`,`score`,`newest`; empty string = no filter | `{total, rows:[Opportunity]}` (max 500 rows) |
| `get_sources()` | `[{key, name, method, args:[{name,label,default}], state:"idle"|"running"|"ok"|"failed", last_run, new_count, pid}]` |
| `run_task(key, args)` | `{ok:true}` or `{error}` |
| `stop_task(key)` | `{ok:true}` or `{error}` |
| `get_logs(since)` | `{next, lines:[{t:"HH:MM:SS", task, text, level:"info"|"ok"|"warn"|"error"}]}` |
| `get_status()` | `{running:[{key, name, pid, elapsed_s}]}` |
| `get_settings()` | `{keys:[{masked, provider}], daily:{enabled, time}}` keys masked as `gsk_····a91f`; never return full keys |
| `open_link(url)` / `open_tracker()` | `{ok:true}` |

## Task keys
Scrapers: `whatsapp` (arg `limit`, default 25), `catch`, `gss`, `profellow` (`pages`), `wemake` (`pages`, `category`), `corner` (`pages`, `per_page`), `masters` (`pages`, `discipline`), `silat`.
Others: `backlog`, `deep_eval`, `run_all`, `daily` (run the daily sweep now), `login`, `clean`, `evaluate_url` (arg `url`).
Commands and defaults match `HunterMenu.bat`. `login` and `clean` are interactive, so they open in their own console window. `evaluate_url` passes the URL on stdin.
