"""Tests for the pieces that replaced the desktop app's mock/dead paths:
key health probing, daily-schedule control, the real browser-preview server,
and re-evaluate replacing the stale tracker row.

No network: probes use a fake opener, schtasks uses a fake runner, the server
is driven over loopback with a stub Api.
"""
import io
import json
import sys
import threading
import types
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core import exporter  # noqa: E402
from src.desktop import keys, runner, server  # noqa: E402
from src.desktop.bridge import Api  # noqa: E402

SECRET = "gsk_" + "Q" * 40 + "a91f"


# ---------- key health ----------

@pytest.mark.parametrize("status, body, state", [
    (200, "", keys.HEALTHY),
    (429, "", keys.RATE_LIMITED),
    (401, "", keys.INVALID),
    (403, "", keys.INVALID),
    (400, '{"error":{"details":[{"reason":"API_KEY_INVALID"}]}}', keys.INVALID),
    (500, "", "HTTP 500"),
])
def test_classify(status, body, state):
    assert keys.classify(status, body) == state


def test_requests_carry_key_in_headers_never_url():
    g = keys.build_request("groq", SECRET)
    assert g.get_header("Authorization") == f"Bearer {SECRET}" and SECRET not in g.full_url
    m = keys.build_request("gemini", SECRET)
    assert m.get_header("X-goog-api-key") == SECRET and SECRET not in m.full_url
    with pytest.raises(ValueError):
        keys.build_request("openai", SECRET)


class _Resp:
    def __init__(self, status): self.status = status
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _http_error(code, body=b""):
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(body))


def test_probe_maps_transport_outcomes():
    assert keys.probe("groq", SECRET, opener=lambda r, timeout: _Resp(200)) == keys.HEALTHY

    def raise_(exc):
        def opener(req, timeout):
            raise exc
        return opener

    assert keys.probe("groq", SECRET, opener=raise_(_http_error(429))) == keys.RATE_LIMITED
    assert keys.probe("gemini", SECRET, opener=raise_(
        _http_error(400, b"API key not valid. Please pass a valid API key."))) == keys.INVALID
    assert keys.probe("groq", SECRET, opener=raise_(urllib.error.URLError("dns"))) == keys.UNREACHABLE
    assert keys.probe("groq", SECRET, opener=raise_(TimeoutError())) == keys.UNREACHABLE


def test_check_all_keeps_order_and_handles_empty():
    pairs = [("groq", "a"), ("gemini", "b"), ("groq", "c")]
    assert keys.check_all(pairs, lambda p, k: f"{p}:{k}") == ["groq:a", "gemini:b", "groq:c"]
    assert keys.check_all([]) == []


def test_bridge_check_keys_masks_and_never_leaks(monkeypatch):
    import src.desktop.bridge as bridge
    monkeypatch.setattr(bridge, "_key_pairs", lambda: [("groq", SECRET), ("gemini", "AIza" + "z" * 35)])
    monkeypatch.setattr(bridge.keys_mod, "check_all", lambda pairs: [keys.HEALTHY, keys.INVALID])
    out = Api().check_keys()
    assert [k["state"] for k in out["keys"]] == [keys.HEALTHY, keys.INVALID]
    assert out["keys"][0]["masked"] == "gsk_····a91f"
    assert SECRET not in json.dumps(out) and "Q" * 10 not in json.dumps(out)


# ---------- daily schedule ----------

CSV = (
    '"HostName","TaskName","Next Run Time","Status","Task To Run","Start Time","Scheduled Task State"\n'
    '"PC","\\Other","N/A","Ready","C:\\x.exe","9:00:00 AM","Enabled"\n'
    '"PC","\\Hunter","11/5/2026 7:30:00 PM","Ready","\\"C:\\repo\\RunDaily.bat\\"","7:30:00 PM","Disabled"\n'
)


def test_parse_schedule_csv_picks_rundaily_entry():
    s = runner.parse_schedule_csv(CSV)
    assert s == {"enabled": False, "time": "19:30", "next_run": "11/5/2026 7:30:00 PM", "task_name": "\\Hunter"}
    assert runner.parse_schedule_csv(CSV.splitlines()[0] + "\n")["task_name"] is None


@pytest.mark.parametrize("raw, hhmm", [
    ("7:00:00 AM", "07:00"), ("12:05:00 AM", "00:05"), ("12:05:00 PM", "12:05"),
    ("19:45:00", "19:45"), ("07:00", "07:00"), ("N/A", None), (None, None), ("25:00", None),
])
def test_to_hhmm(raw, hhmm):
    assert runner.to_hhmm(raw) == hhmm


def test_schedule_command_branches():
    bat = Path("C:/repo/RunDaily.bat")
    none = {"task_name": None, "time": None}
    create = runner.schedule_command(none, True, "06:15", bat)
    assert create[:4] == ["schtasks", "/Create", "/SC", "DAILY"]
    assert create[create.index("/TR") + 1] == f'"{bat}"' and create[create.index("/ST") + 1] == "06:15"
    assert runner.schedule_command(none, True, None, bat)[-2:] == [runner.DEFAULT_DAILY_TIME, "/F"]
    assert runner.schedule_command(none, False, None, bat) is None

    cur = {"task_name": "\\Hunter", "time": "07:00"}
    assert runner.schedule_command(cur, False, None) == ["schtasks", "/Change", "/TN", "\\Hunter", "/DISABLE"]
    assert runner.schedule_command(cur, True, "07:00") == ["schtasks", "/Change", "/TN", "\\Hunter", "/ENABLE"]
    assert runner.schedule_command(cur, True, "08:00")[-2:] == ["/ST", "08:00"]


def test_set_daily_runs_schtasks_and_surfaces_failure(monkeypatch):
    monkeypatch.setattr(runner, "IS_WIN", True)
    monkeypatch.setattr(runner, "daily_schedule", lambda force=False: {"task_name": "\\Hunter", "time": "07:00",
                                                                     "enabled": True, "next_run": None})
    calls = []
    ok = lambda cmd, **kw: calls.append(cmd) or types.SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
    runner.set_daily(False, None, run=ok)
    assert calls == [["schtasks", "/Change", "/TN", "\\Hunter", "/DISABLE"]]

    bad = lambda cmd, **kw: types.SimpleNamespace(returncode=1, stdout=b"", stderr=b"ERROR: Access is denied.")
    with pytest.raises(RuntimeError, match="Access is denied"):
        runner.set_daily(True, "08:00", run=bad)
    with pytest.raises(ValueError):
        runner.set_daily(True, "8am", run=ok)


def test_bridge_set_daily_rejects_non_bool():
    assert "error" in Api().set_daily("yes", "07:00")


# ---------- browser-preview server ----------

class _StubApi:
    def get_status(self):
        return {"running": []}

    def echo(self, *args):
        return {"args": list(args)}

    def _private(self):
        return {"leak": True}


@pytest.fixture
def live_server():
    srv, url = server.make_server(0, api=_StubApi(), token="T0KEN")
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    base = url.split("/index.html")[0]
    yield srv, base, url
    srv.shutdown()
    srv.server_close()


def _post(base, path, body=b'{"args":[]}', token="T0KEN", host=None):
    req = urllib.request.Request(base + path, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    if token is not None:
        req.add_header("X-Hunter-Token", token)
    if host:
        req.add_header("Host", host)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_server_url_and_bind(live_server):
    srv, base, url = live_server
    assert srv.server_address[0] == "127.0.0.1"
    assert url.endswith("#token=T0KEN") and "T0KEN" not in url.split("#")[0]


def test_server_calls_real_methods_with_token(live_server):
    _, base, _ = live_server
    assert _post(base, "/api/get_status") == (200, {"running": []})
    assert _post(base, "/api/echo", b'{"args":[1,"a",true]}') == (200, {"args": [1, "a", True]})


@pytest.mark.parametrize("kwargs, status", [
    ({"token": None}, 401),
    ({"token": "wrong"}, 401),
    ({"host": "evil.example:80"}, 403),
])
def test_server_rejects_untrusted_callers(live_server, kwargs, status):
    _, base, _ = live_server
    assert _post(base, "/api/get_status", **kwargs)[0] == status


def test_server_blocks_private_and_unknown_and_bad_bodies(live_server):
    _, base, _ = live_server
    assert _post(base, "/api/_private")[0] == 404
    assert _post(base, "/api/nope")[0] == 404
    assert _post(base, "/api/echo", b"not json")[0] == 400
    assert _post(base, "/api/echo", b'{"args":"x"}')[0] == 400
    assert _post(base, "/api/get_status", b'{"args":[1,2,3]}')[1].get("error")  # arity -> error dict


def test_server_serves_ui_without_mock(live_server):
    _, base, _ = live_server
    with urllib.request.urlopen(base + "/index.html", timeout=5) as r:
        html = r.read().decode("utf-8")
    assert "http-bridge.js" in html and "mock.js" not in html
    assert not (server.UI_DIR / "mock.js").exists()


def test_real_api_exposes_new_methods():
    names = set(server.public_methods(Api()))
    assert {"check_keys", "set_daily", "get_settings", "run_task"} <= names
    assert not any(n.startswith("_") for n in names)


# ---------- re-evaluate replaces the stale row ----------

def _opp(score, rationale):
    return types.SimpleNamespace(
        category="Physics", opportunity_title="MSc Physics", opportunity_type="Masters",
        deadline="2026-12-01", funding_status="Fully funded", fields_of_study=["Physics"],
        application_link="https://x.example/msc", action_items="Apply",
        institution_or_country="Univ", match_score=score, reasoning=rationale)


def _export(path, score, rationale, replace=None):
    item = {"opp": _opp(score, rationale), "msg": {"source": "Manual", "text": "t", "scraped_date": "2026-11-04"}}
    exporter.export_to_excel([item], str(path), replace_links=replace)


def test_reevaluate_replaces_existing_row(tmp_path):
    path = tmp_path / "tracker.xlsx"
    _export(path, 40, "old")
    _export(path, 90, "new")  # scraper semantics: keep-first, new evaluation discarded
    df = pd.read_excel(path)
    assert len(df) == 1 and df.loc[0, "AI Rationale"] == "old"

    _export(path, 90, "new", replace=["https://x.example/msc"])
    df = pd.read_excel(path)
    assert len(df) == 1 and df.loc[0, "AI Rationale"] == "new" and df.loc[0, "Match Score"] == 90
