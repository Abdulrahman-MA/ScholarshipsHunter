"""Task registry and subprocess manager for the desktop app.

Commands and default arguments mirror HunterMenu.bat. Scripts run with the
repo's Python, cwd set to the repo root, and an argument list (no shell).
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import tracker

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
STATE_PATH = DATA_DIR / "desktop_state.json"
VENV_PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
LOG_CAP = 5000
SCHEDULE_TASK_MARK = "rundaily.bat"
SCHEDULE_CACHE_S = 60

IS_WIN = os.name == "nt"
CREATE_NO_WINDOW = 0x08000000 if IS_WIN else 0
CREATE_NEW_CONSOLE = 0x00000010 if IS_WIN else 0

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$", re.IGNORECASE)
_URL = re.compile(r"^https?://\S+$", re.IGNORECASE)
_ERR = re.compile(r"error|fail|traceback|exception|fatal|critical", re.IGNORECASE)
_WARN = re.compile(r"\b429\b|warn|rate.?limit|quota", re.IGNORECASE)
_OK = re.compile(r"saved|written|success|completed|\bok\b", re.IGNORECASE)


@dataclass(frozen=True)
class Arg:
    name: str
    label: str
    default: str
    kind: str = "text"  # int | slug | url


@dataclass(frozen=True)
class Task:
    key: str
    name: str
    method: str
    argv: Callable[[dict], list]  # first item is the script path relative to repo root
    args: tuple = ()
    console: bool = False  # runs in its own console window (no log capture)
    stdin: Callable[[dict], str] | None = None


TASKS: dict[str, Task] = {t.key: t for t in [
    Task("whatsapp", "WhatsApp channels", "Live browser",
         lambda a: ["src/main.py", "--mode", "live", "--channel", "all", "--limit", a["limit"]],
         (Arg("limit", "Messages per channel", "25", "int"),)),
    Task("catch", "Catch That Scholarship", "Fast JSON",
         lambda a: ["src/scrapers/catchthatscholarship.py"]),
    Task("gss", "GradSchoolShopper", "Fast CSV",
         lambda a: ["src/scrapers/gradschoolshopper.py"]),
    Task("profellow", "ProFellow", "Hybrid Browser/AI",
         lambda a: ["src/scrapers/profellow.py", "--pages", a["pages"]],
         (Arg("pages", "Search pages", "1", "int"),)),
    Task("wemake", "WeMakeScholars", "Hybrid Browser/AI",
         lambda a: ["src/scrapers/wemakescholars.py", "--pages", a["pages"], "--category", a["category"]],
         (Arg("pages", "Search pages", "3", "int"), Arg("category", "Discipline slug", "physics", "slug"))),
    Task("corner", "Scholarships Corner", "Fast REST API",
         lambda a: ["src/scrapers/scholarshipscorner.py", "--pages", a["pages"], "--per-page", a["per_page"]],
         (Arg("pages", "Pages", "5", "int"), Arg("per_page", "Posts per page (max 100)", "50", "int"))),
    Task("masters", "MastersPortal", "Hybrid Browser/AI",
         lambda a: ["src/scrapers/mastersportal.py", "--pages", a["pages"], "--discipline", a["discipline"]],
         (Arg("pages", "Search pages", "3", "int"), Arg("discipline", "Discipline slug", "physics", "slug"))),
    Task("silat", "Hussain Silat (Italy)", "Directory scraper",
         lambda a: ["src/scrapers/hussainsilat.py"]),
    Task("backlog", "Process backlog", "Groq AI",
         lambda a: ["src/main.py", "--mode", "backlog"]),
    Task("deep_eval", "Deep website evaluator", "Groq 120B",
         lambda a: ["src/utils/deep_evaluator.py", "--auto", "--all-sources", "--limit", a["limit"]],
         (Arg("limit", "Rows to check", "100", "int"),)),
    Task("run_all", "Run all scrapers", "Async orchestrator",
         lambda a: ["run_all.py"]),
    Task("daily", "Daily sweep (now)", "Scheduled sweep",
         lambda a: ["src/utils/daily_runner.py", "--force"]),
    Task("login", "Browser logins", "Interactive browser",
         lambda a: ["src/utils/manual_login.py"], console=True),
    Task("clean", "Clean Excel sheet", "Interactive console",
         lambda a: ["src/utils/clean_excel.py"], console=True),
    Task("evaluate_url", "Manual URL evaluator", "Manual AI",
         lambda a: ["src/utils/manual_url_evaluator.py"],
         (Arg("url", "Scholarship URL", "", "url"),),
         stdin=lambda a: a["url"] + "\n"),
]}


def guess_level(text: str) -> str:
    if _ERR.search(text):
        return "error"
    if _WARN.search(text):
        return "warn"
    if _OK.search(text):
        return "ok"
    return "info"


def validate_args(task: Task, args: Any) -> dict[str, str]:
    """Check user-supplied args against the task's schema and fill defaults."""
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ValueError("args must be an object")
    out: dict[str, str] = {}
    for arg in task.args:
        raw = args.get(arg.name)
        value = arg.default if raw in (None, "") else str(raw).strip()
        if arg.kind == "int":
            if not value.isdigit() or not 1 <= int(value) <= 500:
                raise ValueError(f"{arg.label} must be a whole number from 1 to 500")
        elif arg.kind == "slug":
            if not _SLUG.match(value):
                raise ValueError(f"{arg.label} must be a slug such as 'physics'")
        elif arg.kind == "url":
            if len(value) > 2000 or not _URL.match(value):
                raise ValueError("Enter a valid http(s) URL")
        out[arg.name] = value
    return out


def _python_exe() -> str:
    return str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def _count_rows() -> int | None:
    try:
        return tracker.row_count()
    except Exception:
        return None


def _kill_tree(proc: subprocess.Popen) -> None:
    if IS_WIN:
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=30, creationflags=CREATE_NO_WINDOW)
            return
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        proc.kill()
    except OSError:
        pass


class LogBuffer:
    """Thread-safe ring buffer of log lines, addressed by a running sequence number."""

    def __init__(self, cap: int = LOG_CAP):
        self._items: deque = deque(maxlen=cap)
        self._seq = 0
        self._lock = threading.Lock()

    def add(self, task: str, text: str, level: str | None = None) -> None:
        entry = {
            "t": dt.datetime.now().strftime("%H:%M:%S"),
            "task": task,
            "text": text,
            "level": level or guess_level(text),
        }
        with self._lock:
            self._seq += 1
            self._items.append((self._seq, entry))

    def since(self, seq: int) -> dict:
        with self._lock:
            lines = [dict(entry) for s, entry in self._items if s > seq]
            return {"next": self._seq, "lines": lines}


@dataclass
class _Run:
    key: str
    proc: subprocess.Popen
    started: float
    rows_before: int | None


def _load_state(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        tasks = data.get("tasks", {}) if isinstance(data, dict) else {}
        return {k: v for k, v in tasks.items() if isinstance(v, dict)}
    except (OSError, ValueError):
        return {}


class TaskManager:
    """Starts, watches and stops task subprocesses. One run per key at a time."""

    def __init__(self, row_count: Callable[[], int | None] = _count_rows,
                 state_path: Path = STATE_PATH, python: str | None = None,
                 root: Path = REPO_ROOT):
        self._row_count = row_count
        self._state_path = Path(state_path)
        self._python = python or _python_exe()
        self._root = Path(root)
        self._lock = threading.Lock()
        self._runs: dict[str, _Run] = {}
        self._stopping: set[str] = set()
        self._state: dict[str, str] = {}
        self._info: dict[str, dict] = _load_state(self._state_path)
        self._logs = LogBuffer()

    def start(self, key: str, args: Any = None) -> int:
        task = TASKS.get(key)
        if task is None:
            raise ValueError(f"Unknown task: {key}")
        vals = validate_args(task, args)
        parts = [str(p) for p in task.argv(vals)]
        cmd = [self._python, str(self._root / parts[0]), *parts[1:]]
        stdin_text = task.stdin(vals) if task.stdin else None
        env = os.environ.copy()
        env.update(PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        rows_before = self._row_count()

        with self._lock:
            if key in self._runs:
                raise RuntimeError(f"{task.name} is already running")
            if task.console:
                proc = subprocess.Popen(cmd, cwd=str(self._root), env=env,
                                        creationflags=CREATE_NEW_CONSOLE)
            else:
                proc = subprocess.Popen(
                    cmd, cwd=str(self._root), env=env,
                    stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", bufsize=1,
                    creationflags=CREATE_NO_WINDOW,
                )
            run = _Run(key, proc, time.time(), rows_before)
            self._runs[key] = run
            self._state[key] = "running"

        if stdin_text is not None:
            try:
                proc.stdin.write(stdin_text)
                proc.stdin.close()
            except OSError:
                pass
        self._logs.add(key, f"Started {task.name} (pid {proc.pid})", "info")
        threading.Thread(target=self._watch, args=(task, run), daemon=True).start()
        return proc.pid

    def stop(self, key: str) -> None:
        with self._lock:
            run = self._runs.get(key)
            if run is None:
                raise RuntimeError("Task is not running")
            self._stopping.add(key)
        _kill_tree(run.proc)

    def _watch(self, task: Task, run: _Run) -> None:
        proc = run.proc
        if proc.stdout is not None:
            try:
                for line in proc.stdout:
                    text = line.rstrip("\r\n")
                    if text.strip():
                        self._logs.add(task.key, text)
            except (OSError, ValueError):
                pass
        self._finish(task, run, proc.wait())

    def _finish(self, task: Task, run: _Run, rc: int) -> None:
        after = self._row_count()
        new_count = 0
        if run.rows_before is not None and after is not None:
            new_count = max(0, after - run.rows_before)
        with self._lock:
            stopped = run.key in self._stopping
            self._stopping.discard(run.key)
            self._runs.pop(run.key, None)
            if stopped:
                state = "idle"
            else:
                state = "ok" if rc == 0 else "failed"
            self._state[run.key] = state
            info = self._info.setdefault(run.key, {})
            info["last_run"] = dt.datetime.now().isoformat(timespec="seconds")
            info["new_count"] = new_count
            self._save()
        if stopped:
            self._logs.add(run.key, "Stopped by user", "warn")
        else:
            self._logs.add(run.key, f"Finished with exit code {rc}",
                           "ok" if state == "ok" else "error")

    def _save(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._state_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({"tasks": self._info}, indent=2), encoding="utf-8")
            os.replace(tmp, self._state_path)
        except OSError:
            pass

    def logs(self, since: int = 0) -> dict:
        return self._logs.since(int(since or 0))

    def status(self) -> dict:
        now = time.time()
        with self._lock:
            running = [{"key": r.key, "name": TASKS[r.key].name, "pid": r.proc.pid,
                        "elapsed_s": int(now - r.started)} for r in self._runs.values()]
        return {"running": running}

    def sources(self) -> list[dict]:
        with self._lock:
            out = []
            for t in TASKS.values():
                run = self._runs.get(t.key)
                info = self._info.get(t.key, {})
                out.append({
                    "key": t.key,
                    "name": t.name,
                    "method": t.method,
                    "args": [{"name": a.name, "label": a.label, "default": a.default} for a in t.args],
                    "state": "running" if run else self._state.get(t.key, "idle"),
                    "last_run": info.get("last_run"),
                    "new_count": info.get("new_count", 0),
                    "pid": run.proc.pid if run else None,
                })
            return out


_sched_lock = threading.Lock()
_sched_cache: dict[str, Any] = {"at": 0.0, "value": None}


def daily_schedule(force: bool = False) -> dict:
    """Read the Windows Task Scheduler entry that runs RunDaily.bat (cached briefly)."""
    with _sched_lock:
        fresh = time.time() - _sched_cache["at"] < SCHEDULE_CACHE_S
        if force or not fresh or _sched_cache["value"] is None:
            _sched_cache["value"] = _query_schedule()
            _sched_cache["at"] = time.time()
        return dict(_sched_cache["value"])


def _query_schedule() -> dict:
    result: dict[str, Any] = {"enabled": False, "time": None, "next_run": None, "task_name": None}
    if not IS_WIN:
        return result
    try:
        proc = subprocess.run(["schtasks", "/Query", "/FO", "CSV", "/V"],
                              capture_output=True, timeout=20, creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return result
    return parse_schedule_csv(proc.stdout.decode("oem", errors="replace"))


def parse_schedule_csv(text: str) -> dict:
    """Pick the RunDaily.bat entry out of `schtasks /Query /FO CSV /V` output."""
    result: dict[str, Any] = {"enabled": False, "time": None, "next_run": None, "task_name": None}
    for row in csv.DictReader(io.StringIO(text)):
        values = [str(v or "") for v in row.values()]
        if not any(SCHEDULE_TASK_MARK in v.lower() for v in values):
            continue
        state = str(row.get("Scheduled Task State") or "Enabled")
        result["enabled"] = state.lower() != "disabled"
        for key, field in (("time", "Start Time"), ("next_run", "Next Run Time")):
            value = str(row.get(field) or "").strip()
            result[key] = value if value and value.upper() != "N/A" else None
        result["time"] = to_hhmm(result["time"])
        result["task_name"] = str(row.get("TaskName") or "").strip() or None
        break
    return result


_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_CLOCK = re.compile(r"^\s*(\d{1,2}):(\d{2})(?::\d{2})?\s*([AaPp][Mm])?\s*$")
DAILY_TASK_NAME = "ScholarshipsHunter Daily Sweep"
DEFAULT_DAILY_TIME = "07:00"


def to_hhmm(value: Any) -> str | None:
    """'7:00:00 AM' / '19:05:00' / '07:00' -> 'HH:MM' (24h); None when unparseable."""
    m = _CLOCK.match(str(value or ""))
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def schedule_command(current: dict, enabled: bool, at: str | None,
                     bat_path: Path | None = None) -> list[str] | None:
    """The schtasks argv that moves the schedule to the requested state (None = nothing to do)."""
    name = current.get("task_name")
    if name is None:
        if not enabled:
            return None  # nothing scheduled, nothing to disable
        bat = bat_path or (REPO_ROOT / "RunDaily.bat")
        return ["schtasks", "/Create", "/SC", "DAILY", "/TN", DAILY_TASK_NAME,
                "/TR", f'"{bat}"', "/ST", at or DEFAULT_DAILY_TIME, "/F"]
    cmd = ["schtasks", "/Change", "/TN", name, "/ENABLE" if enabled else "/DISABLE"]
    if at and at != current.get("time"):
        cmd += ["/ST", at]
    return cmd


def set_daily(enabled: bool, at: Any = None, run: Callable = subprocess.run) -> dict:
    """Enable/disable (or create) the Task Scheduler entry for RunDaily.bat and set its time."""
    if not IS_WIN:
        raise RuntimeError("The daily sweep uses Windows Task Scheduler, which is not available here")
    at = str(at).strip() if at not in (None, "") else None
    if at is not None and not _HHMM.match(at):
        raise ValueError("Time must be HH:MM in 24-hour format, e.g. 07:00")
    cmd = schedule_command(daily_schedule(force=True), bool(enabled), at)
    if cmd is not None:
        proc = run(cmd, capture_output=True, timeout=30, creationflags=CREATE_NO_WINDOW)
        if proc.returncode != 0:
            raw = (proc.stderr or b"") + (proc.stdout or b"")
            msg = raw.decode("oem", errors="replace").strip() if isinstance(raw, bytes) else str(raw)
            raise RuntimeError(msg or f"schtasks failed with exit code {proc.returncode}")
    return daily_schedule(force=True)
