"""Read-only access to the scholarship tracker workbook.

Nothing in this module writes to the Excel file. Parsed rows are cached by
file path and modification time, so the UI can poll cheaply.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import threading
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER_PATH = REPO_ROOT / "scholarships_tracker.xlsx"
BACKLOG_PATH = REPO_ROOT / "data" / "scraped_backlog.json"
DLQ_PATH = REPO_ROOT / "data" / "dead_letter_queue.jsonl"
LAST_RUN_PATH = REPO_ROOT / "data" / "last_daily_run.txt"

# Same thresholds as apply_excel_formatting() in src/core/exporter.py (Green / Yellow / Red).
GREEN_MIN = 75
YELLOW_MIN = 50
MAX_ROWS = 500
CLOSING_DAYS = 30
YIELD_DAYS = 7

# Excel column -> Opportunity field
COLUMN_MAP = {
    "Category": "category",
    "Title": "title",
    "Type": "type",
    "Deadline": "deadline",
    "Funding": "funding",
    "Fields": "fields",
    "Link": "link",
    "Action Items": "action_items",
    "Institution/Country": "institution",
    "Scraped Date": "scraped_date",
    "Web Source": "source",
    "Match Score": "score",
    "AI Rationale": "rationale",
    "Deep Checked": "deep_checked",
}

_lock = threading.Lock()
_cache: dict[str, Any] = {"key": None, "df": None}

_DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y",
    "%d %B %Y", "%d %b %Y", "%d %B, %Y", "%d %b, %Y", "%d-%b-%Y", "%d-%B-%Y",
    "%B %d %Y", "%b %d %Y", "%B %d, %Y", "%b %d, %Y",
)
_DATE_PATTERNS = (
    r"\d{4}-\d{1,2}-\d{1,2}",
    r"\d{4}/\d{1,2}/\d{1,2}",
    r"\d{1,2}[/.-]\d{1,2}[/.-]\d{4}",
    r"\d{1,2}\s+[A-Za-z]{3,9}\.?,?\s+\d{4}",
    r"[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4}",
)
_LEVEL_PATTERNS = {
    "phd": r"\bph\.?\s?d\b|doctoral|doctorate",
    "masters": r"\bmasters?\b|\bmsc\b|\bm\.sc\b|postgraduate",
    "bachelor": r"bachelor|\bbsc\b|undergrad",
    "internship": r"intern|fellowship|research (?:stay|position)",
    "school": r"summer school|winter school|\bschool\b|course|workshop|diploma",
}


def _text(value: Any) -> str:
    if value is None or value is pd.NaT:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def parse_deadline(raw: Any) -> dt.date | None:
    """Parse a deadline cell to a date. Ambiguous slash dates are read as day/month.

    Returns None for anything unparseable (e.g. "rolling", "TBA").
    """
    if raw is None or raw is pd.NaT:
        return None
    if isinstance(raw, dt.datetime):
        return _sane(raw.date())
    if isinstance(raw, dt.date):
        return _sane(raw)
    s = _text(raw)
    if not s:
        return None
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s, flags=re.IGNORECASE)
    s = re.sub(r"(?<=[A-Za-z])\.", "", s)
    s = re.sub(r"\bSept\b", "Sep", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)
    candidates = [s]
    candidates += [m.group(0) for pat in _DATE_PATTERNS if (m := re.search(pat, s))]
    for cand in candidates:
        for fmt in _DATE_FORMATS:
            try:
                return _sane(dt.datetime.strptime(cand, fmt).date())
            except ValueError:
                continue
    return None


def _sane(d: dt.date) -> dt.date | None:
    return d if 2000 <= d.year <= 2100 else None


def score_to_int(raw: Any) -> int | None:
    s = _text(raw).rstrip("%").strip()
    try:
        value = float(s)
    except ValueError:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    rounded = round(value)
    return int(rounded) if 0 <= rounded <= 100 else None


def tier_for(score: int | None) -> str | None:
    if score is None:
        return None
    if score >= GREEN_MIN:
        return "fit"
    if score >= YELLOW_MIN:
        return "maybe"
    return "no"


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(COLUMN_MAP))


def _load_frame(path: Path) -> pd.DataFrame:
    """Read the workbook (read-only), reusing the cached frame while mtime is unchanged."""
    try:
        mtime = path.stat().st_mtime_ns
    except FileNotFoundError:
        return _empty_frame()
    key = (str(path), mtime)
    with _lock:
        if _cache["key"] == key:
            return _cache["df"]
        df = pd.read_excel(path, keep_default_na=False)
        _cache["key"] = key
        _cache["df"] = df
        return df


def row_count(path: Path = TRACKER_PATH) -> int:
    return len(_load_frame(Path(path)))


def map_row(rec: dict, row_id: int, today: dt.date) -> dict:
    """Map one Excel record to an Opportunity dict (see docs/design/desktop-api.md)."""
    row: dict[str, Any] = {"id": row_id}
    for col, field in COLUMN_MAP.items():
        if field not in ("score",):
            row[field] = _text(rec.get(col, ""))
    deadline = parse_deadline(rec.get("Deadline", ""))
    score = score_to_int(rec.get("Match Score", ""))
    row["deadline_iso"] = deadline.isoformat() if deadline else None
    row["days_left"] = (deadline - today).days if deadline else None
    row["score"] = score
    row["tier"] = tier_for(score)
    return row


def load_rows(path: Path = TRACKER_PATH, today: dt.date | None = None) -> list[dict]:
    today = today or dt.date.today()
    rows = []
    for idx, rec in enumerate(_load_frame(Path(path)).to_dict("records")):
        row = map_row(rec, idx + 2, today)  # id = Excel row number
        if row["title"] or row["link"]:
            rows.append(row)
    return rows


def levels_of(row: dict) -> set[str]:
    text = " ".join(row.get(k, "") for k in ("title", "type", "category", "fields")).lower()
    return {name for name, pat in _LEVEL_PATTERNS.items() if re.search(pat, text)}


def _matches(row: dict, f: dict[str, str]) -> bool:
    if f["q"]:
        hay = " ".join(row.get(k, "") for k in ("title", "institution", "fields", "category", "source")).lower()
        if f["q"].lower() not in hay:
            return False
    if f["tier"] and row["tier"] != f["tier"]:
        return False
    if f["funding"] and f["funding"].lower() not in row["funding"].lower():
        return False
    if f["level"] and f["level"].lower() not in levels_of(row):
        return False
    return True


def _sorted(rows: list[dict], sort: str) -> list[dict]:
    if sort == "deadline":
        return sorted(rows, key=lambda r: (r["deadline_iso"] is None, r["deadline_iso"] or ""))
    if sort == "score":
        return sorted(rows, key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    if sort == "newest":
        return sorted(rows, key=lambda r: r["scraped_date"] or "", reverse=True)
    return rows


def query(rows: list[dict], filters: dict | None = None) -> dict:
    """Filter and sort rows. Empty filter strings mean no filter."""
    raw = filters or {}
    f = {k: str(raw.get(k) or "").strip() for k in ("q", "tier", "funding", "level", "sort")}
    matched = _sorted([r for r in rows if _matches(r, f)], f["sort"])
    return {"total": len(matched), "rows": matched[:MAX_ROWS]}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _backlog_count(path: Path) -> int:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return len(data) if isinstance(data, list) else 0
    except (OSError, ValueError):
        return 0


def _dlq_entries(path: Path) -> list[dict]:
    entries = []
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if isinstance(item, dict):
                    entries.append(item)
    except OSError:
        pass
    return entries


def source_yield(rows: list[dict], dlq_path: Path, today: dt.date) -> list[dict]:
    """Per-source count of rows scraped in the last 7 days, plus dead-letter failures."""
    cutoff = today - dt.timedelta(days=YIELD_DAYS)
    counts: Counter = Counter()
    failed: Counter = Counter()
    for r in rows:
        d = parse_deadline(r["scraped_date"])
        if d and cutoff <= d <= today:
            counts[r["source"] or "Unknown"] += 1
    for entry in _dlq_entries(dlq_path):
        d = parse_deadline(str(entry.get("timestamp", ""))[:10])
        if d and cutoff <= d <= today:
            failed[str(entry.get("source") or "Unknown")] += 1
    names = set(counts) | set(failed)
    ordered = sorted(names, key=lambda s: (-counts[s], -failed[s], s))
    return [{"source": s, "count": counts[s], "failed": failed[s]} for s in ordered]


def overview(
    today: dt.date | None = None,
    tracker_path: Path = TRACKER_PATH,
    backlog_path: Path = BACKLOG_PATH,
    dlq_path: Path = DLQ_PATH,
    last_run_path: Path = LAST_RUN_PATH,
) -> dict:
    today = today or dt.date.today()
    rows = load_rows(tracker_path, today)
    tiers = Counter(r["tier"] for r in rows)
    closing = [r for r in rows if r["days_left"] is not None and 0 <= r["days_left"] <= CLOSING_DAYS]
    closing.sort(key=lambda r: r["deadline_iso"])
    return {
        "total": len(rows),
        "fit": tiers["fit"],
        "maybe": tiers["maybe"],
        "no": tiers["no"],
        "backlog": _backlog_count(backlog_path),
        "last_sweep": _read_text(last_run_path) or None,
        "closing": closing,
        "yield": source_yield(rows, dlq_path, today),
    }
