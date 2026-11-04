"""Tests for the desktop app's tracker parsing, filtering, key masking and log levels.

No network, no real scrapers, and the real tracker workbook is never touched.
"""
import datetime as dt
import json
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.desktop import tracker  # noqa: E402
from src.desktop.bridge import Api, _safe, mask_key  # noqa: E402
from src.desktop.runner import TASKS, guess_level, validate_args  # noqa: E402

TODAY = dt.date(2026, 11, 4)


def _sample_rows():
    base = {"Category": "", "Type": "", "Action Items": "", "AI Rationale": "", "Deep Checked": ""}
    return [
        {**base, "Category": "Physics", "Title": "MSc Theoretical Physics", "Type": "Masters",
         "Deadline": "15 December 2026", "Funding": "Fully funded", "Fields": "Cosmology",
         "Link": "https://a.example/1", "Institution/Country": "Univ A, Italy",
         "Scraped Date": "2026-11-01", "Web Source": "WhatsApp", "Match Score": 88},
        {**base, "Category": "Physics", "Title": "Summer school on plasma", "Type": "School",
         "Deadline": "2026-11-10", "Funding": "Partial", "Fields": "Plasma Physics",
         "Link": "https://b.example/2", "Institution/Country": "ICTP",
         "Scraped Date": "2026-10-30", "Web Source": "Corner", "Match Score": 60},
        {**base, "Title": "Engineering PhD", "Deadline": "rolling",
         "Funding": "Fully funded", "Link": "https://c.example/3",
         "Scraped Date": "2026-09-01", "Web Source": "Corner", "Match Score": "20"},
        {**base, "Title": "Data fellowship", "Deadline": "31/12/2026", "Funding": "Fully funded",
         "Link": "https://d.example/4", "Scraped Date": "2026-11-03", "Web Source": "WhatsApp",
         "Match Score": None},
    ]


@pytest.fixture
def tracker_file(tmp_path):
    path = tmp_path / "tracker.xlsx"
    pd.DataFrame(_sample_rows()).to_excel(path, index=False)
    return path


@pytest.mark.parametrize("raw, expected", [
    ("2026-12-15", dt.date(2026, 12, 15)),
    ("15 December 2026", dt.date(2026, 12, 15)),
    ("15th Dec 2026", dt.date(2026, 12, 15)),
    ("Dec 15, 2026", dt.date(2026, 12, 15)),
    ("Sept. 3, 2026", dt.date(2026, 9, 3)),
    ("15/12/2026", dt.date(2026, 12, 15)),
    ("Deadline: 15 Dec 2026 (or until filled)", dt.date(2026, 12, 15)),
    (dt.datetime(2026, 12, 1, 9, 30), dt.date(2026, 12, 1)),
    (pd.Timestamp("2026-06-30"), dt.date(2026, 6, 30)),
])
def test_parse_deadline_formats(raw, expected):
    assert tracker.parse_deadline(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "rolling", "TBA", "99/99/2026", "2026-02-30", "Open all year", pd.NaT])
def test_parse_deadline_garbage_is_none(raw):
    assert tracker.parse_deadline(raw) is None


@pytest.mark.parametrize("raw, expected", [
    (88, 88), ("88", 88), (74.6, 75), ("42%", 42), (None, None), ("", None),
    ("n/a", None), (150, None), (-3, None), (float("nan"), None),
])
def test_score_to_int(raw, expected):
    assert tracker.score_to_int(raw) == expected


@pytest.mark.parametrize("score, tier", [
    (75, "fit"), (100, "fit"), (74, "maybe"), (50, "maybe"), (49, "no"), (0, "no"), (None, None),
])
def test_tier_thresholds_match_exporter(score, tier):
    assert tracker.tier_for(score) == tier


def test_missing_tracker_returns_empty_results(tmp_path):
    missing = tmp_path / "nope.xlsx"
    assert tracker.load_rows(missing, TODAY) == []
    assert tracker.query(tracker.load_rows(missing, TODAY), {"q": "physics"}) == {"total": 0, "rows": []}


def test_load_rows_maps_fields(tracker_file):
    rows = {r["title"]: r for r in tracker.load_rows(tracker_file, TODAY)}
    msc = rows["MSc Theoretical Physics"]
    assert msc["deadline_iso"] == "2026-12-15"
    assert msc["days_left"] == (dt.date(2026, 12, 15) - TODAY).days
    assert msc["score"] == 88 and msc["tier"] == "fit"
    assert msc["institution"] == "Univ A, Italy"
    assert msc["source"] == "WhatsApp"
    assert msc["link"] == "https://a.example/1"
    phd = rows["Engineering PhD"]
    assert phd["deadline_iso"] is None and phd["days_left"] is None
    assert phd["score"] == 20 and phd["tier"] == "no"
    assert rows["Data fellowship"]["score"] is None and rows["Data fellowship"]["tier"] is None


def test_tracker_is_never_written(tracker_file):
    before = (tracker_file.read_bytes(), os.stat(tracker_file).st_mtime_ns)
    tracker.load_rows(tracker_file, TODAY)
    tracker.overview(TODAY, tracker_file, tracker_file.with_name("none.json"),
                     tracker_file.with_name("none.jsonl"), tracker_file.with_name("none.txt"))
    assert (tracker_file.read_bytes(), os.stat(tracker_file).st_mtime_ns) == before


def test_cache_refreshes_when_file_changes(tracker_file):
    assert len(tracker.load_rows(tracker_file, TODAY)) == 4
    pd.DataFrame(_sample_rows()[:1]).to_excel(tracker_file, index=False)
    st = os.stat(tracker_file)
    os.utime(tracker_file, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    assert len(tracker.load_rows(tracker_file, TODAY)) == 1


def test_query_filters_and_sorting(tracker_file):
    rows = tracker.load_rows(tracker_file, TODAY)
    everything = tracker.query(rows, {})
    assert everything["total"] == 4

    assert [r["title"] for r in tracker.query(rows, {"q": "plasma"})["rows"]] == ["Summer school on plasma"]
    assert {r["tier"] for r in tracker.query(rows, {"tier": "fit"})["rows"]} == {"fit"}
    assert tracker.query(rows, {"tier": "no"})["total"] == 1
    assert tracker.query(rows, {"funding": "fully"})["total"] == 3
    assert tracker.query(rows, {"level": "masters"})["total"] == 1
    assert tracker.query(rows, {"level": "phd"})["total"] == 1

    by_deadline = [r["title"] for r in tracker.query(rows, {"sort": "deadline"})["rows"]]
    assert by_deadline == ["Summer school on plasma", "MSc Theoretical Physics",
                           "Data fellowship", "Engineering PhD"]

    by_score = [r["score"] for r in tracker.query(rows, {"sort": "score"})["rows"]]
    assert by_score == [88, 60, 20, None]

    newest = [r["scraped_date"] for r in tracker.query(rows, {"sort": "newest"})["rows"]]
    assert newest == sorted(newest, reverse=True)


def test_overview_counts_closing_yield_and_backlog(tmp_path, tracker_file):
    backlog = tmp_path / "backlog.json"
    backlog.write_text(json.dumps([{"text": "a"}, {"text": "b"}, {"text": "c"}]), encoding="utf-8")
    dlq = tmp_path / "dlq.jsonl"
    dlq.write_text(json.dumps({"timestamp": "2026-11-02T10:00:00", "source": "Corner"}) + "\n"
                   + "not json\n", encoding="utf-8")
    last = tmp_path / "last.txt"
    last.write_text("2026-11-03", encoding="utf-8")

    data = tracker.overview(TODAY, tracker_file, backlog, dlq, last)
    assert (data["total"], data["fit"], data["maybe"], data["no"]) == (4, 1, 1, 1)
    assert data["backlog"] == 3
    assert data["last_sweep"] == "2026-11-03"
    assert [c["title"] for c in data["closing"]] == ["Summer school on plasma"]
    by_source = {y["source"]: y for y in data["yield"]}
    assert by_source["WhatsApp"]["count"] == 2
    assert by_source["Corner"]["failed"] == 1

    empty = tracker.overview(TODAY, tmp_path / "x.xlsx", tmp_path / "x.json", dlq, tmp_path / "x.txt")
    assert empty["total"] == 0 and empty["backlog"] == 0 and empty["last_sweep"] is None


def test_mask_key_shows_only_edges():
    key = "gsk_abcdefghijklmnop1234a91f"
    masked = mask_key(key)
    assert masked == "gsk_" + "·" * 4 + "a91f"
    assert key[4:-4] not in masked
    assert mask_key("short") == "·" * 4
    assert mask_key("") == "·" * 4


def test_api_wrapper_returns_error_dict():
    @_safe
    def boom():
        raise RuntimeError("bad things")

    assert boom() == {"error": "bad things"}


@pytest.mark.parametrize("text, level", [
    ("Traceback (most recent call last):", "error"),
    ("[Step 1/2] Something failed", "error"),
    ("Error: connection reset", "error"),
    ("HTTP 429 Too Many Requests", "warn"),
    ("warning: slow page", "warn"),
    ("Excel saved successfully", "ok"),
    ("Rows written: 12", "ok"),
    ("Loaded 4 pending messages", "info"),
])
def test_guess_level(text, level):
    assert guess_level(text) == level


def test_validate_args_defaults_and_bounds():
    assert validate_args(TASKS["whatsapp"], None) == {"limit": "25"}
    assert validate_args(TASKS["wemake"], {"pages": "2", "category": "applied-physics"}) == {
        "pages": "2", "category": "applied-physics"}
    with pytest.raises(ValueError):
        validate_args(TASKS["whatsapp"], {"limit": "0"})
    with pytest.raises(ValueError):
        validate_args(TASKS["whatsapp"], {"limit": "abc"})
    with pytest.raises(ValueError):
        validate_args(TASKS["masters"], {"discipline": "physics; rm -rf"})
    with pytest.raises(ValueError):
        validate_args(TASKS["evaluate_url"], {"url": "file:///etc/passwd"})
    assert validate_args(TASKS["evaluate_url"], {"url": "https://x.example/a"}) == {
        "url": "https://x.example/a"}
