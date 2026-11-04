"""Live health check for the model API keys in .env.

Each key is probed with one cheap, read-only request (list models). Keys are
sent only in request headers and are never returned, logged or stored.
"""
from __future__ import annotations

import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable

GROQ_URL = "https://api.groq.com/openai/v1/models"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1"
TIMEOUT_S = 10
USER_AGENT = "ScholarshipsHunter-desktop/1.0"

HEALTHY = "Healthy"
RATE_LIMITED = "Rate limited"
INVALID = "Invalid"
UNREACHABLE = "Unreachable"

_INVALID_MARKERS = ("API_KEY_INVALID", "API key not valid", "invalid_api_key", "Invalid API Key")


def classify(status: int, body: str = "") -> str:
    """Map an HTTP status (and error body) from a list-models probe to a key state."""
    if 200 <= status < 300:
        return HEALTHY
    if status == 429:
        return RATE_LIMITED
    if status in (401, 403) or any(m in body for m in _INVALID_MARKERS):
        return INVALID
    return f"HTTP {status}"


def build_request(provider: str, key: str) -> urllib.request.Request:
    provider = provider.lower()
    if provider == "groq":
        return urllib.request.Request(GROQ_URL, headers={
            "Authorization": f"Bearer {key}", "User-Agent": USER_AGENT})
    if provider == "gemini":
        # header, not ?key=, so the key never appears in a URL
        return urllib.request.Request(GEMINI_URL, headers={
            "x-goog-api-key": key, "User-Agent": USER_AGENT})
    raise ValueError(f"Unknown provider: {provider}")


def probe(provider: str, key: str, timeout: float = TIMEOUT_S,
          opener: Callable = urllib.request.urlopen) -> str:
    try:
        with opener(build_request(provider, key), timeout=timeout) as resp:
            return classify(getattr(resp, "status", 200))
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(4000).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return classify(exc.code, body)
    except (urllib.error.URLError, TimeoutError, OSError):
        return UNREACHABLE


def check_all(pairs: Iterable[tuple[str, str]],
              probe_fn: Callable[[str, str], str] = probe) -> list[str]:
    """Probe every (provider, key) pair concurrently; results keep input order."""
    pairs = list(pairs)
    if not pairs:
        return []
    with ThreadPoolExecutor(max_workers=min(8, len(pairs))) as pool:
        return list(pool.map(lambda p: probe_fn(*p), pairs))
