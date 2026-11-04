"""JS-facing API for the pywebview window (see docs/design/desktop-api.md).

Every public method returns JSON-ready data, or {"error": message} on failure.
Exceptions never reach the JS side. Only contract methods are public.
"""
from __future__ import annotations

import functools
import os
import webbrowser
from typing import Any
from urllib.parse import urlparse

from . import runner, tracker

IS_WIN = os.name == "nt"
MASK = "·" * 4  # four middle dots, as in the contract


def mask_key(key: Any) -> str:
    """Show only the first 4 and last 4 characters of an API key."""
    k = str(key or "").strip()
    if len(k) <= 8:
        return MASK
    return f"{k[:4]}{MASK}{k[-4:]}"


def _safe(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            return {"error": str(exc) or type(exc).__name__}
    return wrapper


class Api:
    def __init__(self):
        self._tasks = runner.TaskManager()

    @_safe
    def get_overview(self):
        data = tracker.overview()
        data["next_sweep"] = runner.daily_schedule().get("next_run")
        return data

    @_safe
    def list_opportunities(self, filters=None):
        return tracker.query(tracker.load_rows(), filters or {})

    @_safe
    def get_sources(self):
        return self._tasks.sources()

    @_safe
    def run_task(self, key, args=None):
        self._tasks.start(key, args)
        return {"ok": True}

    @_safe
    def stop_task(self, key):
        self._tasks.stop(key)
        return {"ok": True}

    @_safe
    def get_logs(self, since=0):
        return self._tasks.logs(since)

    @_safe
    def get_status(self):
        return self._tasks.status()

    @_safe
    def get_settings(self):
        from src.core import config  # imported lazily; loads .env on first use

        keys = [{"masked": mask_key(k), "provider": "groq"} for k in config.GROQ_API_KEYS]
        keys += [{"masked": mask_key(k), "provider": "gemini"} for k in config.GEMINI_API_KEYS]
        sched = runner.daily_schedule()
        return {"keys": keys, "daily": {"enabled": sched["enabled"], "time": sched["time"]}}

    @_safe
    def open_link(self, url):
        url = str(url or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Only http(s) links can be opened")
        if not webbrowser.open(url):
            raise RuntimeError("Could not open the link")
        return {"ok": True}

    @_safe
    def open_tracker(self):
        path = tracker.TRACKER_PATH
        if not path.exists():
            raise FileNotFoundError("Tracker file does not exist yet")
        if IS_WIN:
            os.startfile(str(path))
        else:
            webbrowser.open(path.as_uri())
        return {"ok": True}
