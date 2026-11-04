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
| `get_settings()` | `{keys:[{masked, provider}], daily:{enabled, time:"HH:MM"|null, next_run, scheduled}}` keys masked as `gsk_····a91f`; never return full keys. Offline: no network calls |
| `check_keys()` | `{keys:[{masked, provider, state}], checked_at:"HH:MM:SS"}`; one live list-models request per key, concurrent, 10 s timeout. `state` ∈ `Healthy`, `Rate limited`, `Invalid`, `Unreachable`, `HTTP <code>` |
| `set_daily(enabled, time)` | `{ok:true, daily:{…as above}}`. `time` is `HH:MM` 24-hour or null. Enables/disables the Task Scheduler entry that runs `RunDaily.bat`; if none exists and `enabled` is true, creates `ScholarshipsHunter Daily Sweep` (daily, default 07:00) |
| `open_link(url)` / `open_tracker()` | `{ok:true}` |

## Browser preview (real data)
`python -m src.desktop --serve [--port 8765] [--no-browser]` serves `ui/` on `127.0.0.1` and exposes the same methods as `POST /api/<method>` with body `{"args":[...]}`. `ui/http-bridge.js` turns `window.pywebview.api` into that transport, but only when the page URL carries the per-launch `#token=…` printed at startup; inside pywebview it does nothing. There is no fake-data mode.

Server hardening, because it can start scrapers: loopback bind only; `Host` must be `127.0.0.1:<port>` or `localhost:<port>` (DNS rebinding); every API call needs the token in `X-Hunter-Token` (constant-time compare). The token sits in the URL fragment, so it is never sent in requests, and the custom header forces a CORS preflight the server never approves.

## Re-evaluate semantics
`evaluate_url` (Tools → Evaluate a link, and Opportunities → Re-evaluate) exports with `replace_links=[url]`: any existing tracker row with the same `Link` is replaced by the new evaluation. Scraper exports keep the old keep-first de-duplication.

## Task keys
Scrapers: `whatsapp` (arg `limit`, default 25), `catch`, `gss`, `profellow` (`pages`), `wemake` (`pages`, `category`), `corner` (`pages`, `per_page`), `masters` (`pages`, `discipline`), `silat`.
Others: `backlog`, `deep_eval`, `run_all`, `daily` (run the daily sweep now), `login`, `clean`, `evaluate_url` (arg `url`).
Commands and defaults match `HunterMenu.bat`. `login` and `clean` are interactive, so they open in their own console window. `evaluate_url` passes the URL on stdin.
