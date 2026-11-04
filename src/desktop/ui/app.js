/* Scholarships Hunter desktop UI. Vanilla JS, no build step.
   Every data call goes through window.pywebview.api (contract: docs/design/desktop-api.md).
   Errors come back as {error: "..."} and are shown in the rust line under the page header. */
(function () {
  'use strict';

  var TIER_LABEL = { fit: 'strong fit', maybe: 'second look', no: 'not a fit' };
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var MON_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  var DAY_LONG = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  var STATES = {
    running: ['run', 'Running'],
    ok: ['ok', 'OK'],
    failed: ['err', 'Failed'],
    idle: ['dim', 'Idle']
  };
  var LOG_CAP = 1000;

  var currentView = 'dash';
  var selectedId = null;
  var oppRows = [];
  var oppTotal = null;
  var oppSeq = 0;
  var srcSig = null;
  var logCursor = 0;
  var running = [];
  var runName = '';
  var runPid = null;
  var runStarted = 0;

  /* ---------- helpers ---------- */

  function $(id) { return document.getElementById(id); }

  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  // escaped value for innerHTML, or an em dash when empty
  function dash(v) { return v == null || v === '' ? '—' : esc(v); }
  function fmtNum(n) { return n == null || n === '' ? '—' : Number(n).toLocaleString('en-US'); }
  function tierClass(t) { return t === 'fit' || t === 'maybe' || t === 'no' ? t : 'none'; }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function mmss(sec) {
    sec = Math.max(0, Math.floor(sec));
    return pad(Math.floor(sec / 60)) + ':' + pad(sec % 60);
  }
  function dayWord(n) { return n === 0 ? 'today' : n === 1 ? '1 day' : n + ' days'; }
  // "2026-11-15" -> "15 Nov" (or "15 Nov 2026"); falls back to the raw Excel text
  function fmtDate(iso, raw, withYear) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
    if (!m) return raw || '';
    return m[3] + ' ' + MON[+m[2] - 1] + (withYear ? ' ' + m[1] : '');
  }
  // "action_items" may be a string or a list; split on newlines, bullets and semicolons
  function splitActions(v) {
    if (!v) return [];
    var text = Array.isArray(v) ? v.join('\n') : String(v);
    return text.split(/\r?\n|;|•/).map(function (s) {
      return s.replace(/^\s*(?:[-*•]|\d+[.)])\s+/, '').trim();
    }).filter(Boolean);
  }
  function stateClass(s) {
    if (!s) return 'dim';
    if (/healthy|ok|valid/i.test(s)) return 'ok';
    if (/limit|wait|slow|warn/i.test(s)) return 'run';
    return 'err';
  }

  function whenReady(cb) {
    if (window.pywebview && window.pywebview.api) { cb(); return; }
    window.addEventListener('pywebviewready', function () { cb(); }, { once: true });
  }

  // Calls an api method. Resolves to the result, or null after showing an error.
  function call(name) {
    var args = Array.prototype.slice.call(arguments, 1);
    return Promise.resolve().then(function () {
      var api = window.pywebview.api;
      return api[name].apply(api, args);
    }).then(function (res) {
      if (res && typeof res === 'object' && !Array.isArray(res) && res.error) {
        showError(res.error);
        return null;
      }
      return res;
    }).catch(function (e) {
      showError((e && e.message) || String(e));
      return null;
    });
  }

  function showError(msg) {
    var el = $('err-' + currentView);
    if (!el) return;
    el.textContent = String(msg);
    el.hidden = false;
  }
  function clearError(view) {
    var el = $('err-' + (view || currentView));
    if (el) { el.textContent = ''; el.hidden = true; }
  }
  // success handler for an action: clears the view's error and refreshes status and sources
  function done(view) {
    return function (res) {
      if (!res) return res;
      clearError(view);
      loadSources();
      pollStatus();
      return res;
    };
  }

  /* ---------- views ---------- */

  function switchView(v) {
    currentView = v;
    document.querySelectorAll('nav button').forEach(function (b) {
      b.classList.toggle('active', b.dataset.v === v);
    });
    document.querySelectorAll('.view').forEach(function (s) {
      s.classList.toggle('active', s.id === v);
    });
    if (v === 'dash') loadOverview();
    if (v === 'opps') loadOpportunities();
    if (v === 'runs') loadSources();
    if (v === 'settings') loadSettings();
  }

  /* ---------- overview ---------- */

  function loadOverview() {
    return call('get_overview').then(function (d) {
      if (d) renderOverview(d);
    });
  }

  function renderOverview(d) {
    var now = new Date();
    var h = now.getHours();
    var greet = h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
    $('dash-kicker').textContent = DAY_LONG[now.getDay()] + ', ' + now.getDate() + ' ' + MON_LONG[now.getMonth()];

    var closing = Array.isArray(d.closing) ? d.closing : [];
    var days = closing.map(function (c) { return c.days_left; })
      .filter(function (n) { return typeof n === 'number'; });
    var tail;
    if (days.length) {
      var n = Math.min.apply(null, days);
      tail = n === 0
        ? '<i>Today</i> is the next deadline.'
        : '<i>' + n + (n === 1 ? ' day' : ' days') + '</i> to the next deadline.';
    } else {
      tail = '<i>Nothing</i> closes in the next 30 days.';
    }
    $('dash-title').innerHTML = greet + '. ' + tail;
    $('dash-meta').innerHTML = 'last sweep ' + dash(d.last_sweep) + '<br>next ' + dash(d.next_sweep);

    if (d.total != null) oppTotal = d.total;
    $('fig-total').textContent = fmtNum(d.total);
    $('fig-fit').textContent = fmtNum(d.fit);
    $('fig-maybe').textContent = fmtNum(d.maybe);
    $('fig-backlog').textContent = fmtNum(d.backlog);
    $('btn-backlog').textContent = 'Process backlog · ' + fmtNum(d.backlog);

    var cb = $('closing-body');
    if (!closing.length) {
      cb.innerHTML = '<tr><td colspan="3" class="empty">Nothing closes in the next 30 days.</td></tr>';
    } else {
      cb.innerHTML = closing.map(function (c) {
        return '<tr>' +
          '<td>' + dash(c.title) + '<div class="dim">' + dash(c.institution) + '</div></td>' +
          '<td class="mono">' + dash(fmtDate(c.deadline_iso, c.deadline)) +
            (c.days_left != null ? '<div class="days">' + esc(c.days_left) + ' d</div>' : '') + '</td>' +
          '<td><span class="score ' + tierClass(c.tier) + '">' + dash(c.score) + '</span></td>' +
          '</tr>';
      }).join('');
    }

    var y = Array.isArray(d.yield) ? d.yield : [];
    var yb = $('yield-body');
    if (!y.length) {
      yb.innerHTML = '<tr><td colspan="3" class="empty">Nothing scraped in the last 7 days.</td></tr>';
    } else {
      var max = Math.max.apply(null, [1].concat(y.map(function (r) { return Number(r.count) || 0; })));
      yb.innerHTML = y.map(function (r) {
        var count = Number(r.count) || 0;
        var pct = Math.round(count / max * 100);
        return '<tr>' +
          '<td>' + dash(r.source) + (r.failed ? ' <span class="state err">· failed</span>' : '') + '</td>' +
          '<td style="width:42%"><div class="bar"><i class="' + (r.failed ? 'bad' : '') + '" style="width:' + pct + '%"></i></div></td>' +
          '<td class="mono">' + fmtNum(count) + '</td>' +
          '</tr>';
      }).join('');
    }
  }

  /* ---------- opportunities ---------- */

  function currentFilters() {
    return {
      q: $('f-q').value.trim(),
      tier: $('f-tier').value,
      funding: $('f-funding').value,
      level: $('f-level').value,
      sort: $('f-sort').value
    };
  }

  function loadOpportunities() {
    var seq = ++oppSeq;
    return call('list_opportunities', currentFilters()).then(function (d) {
      if (!d || seq !== oppSeq) return;
      oppRows = Array.isArray(d.rows) ? d.rows : [];
      var keep = oppRows.some(function (r) { return String(r.id) === selectedId; });
      if (!keep) selectedId = oppRows.length ? String(oppRows[0].id) : null;
      $('opps-meta').innerHTML = fmtNum(oppTotal != null ? oppTotal : d.total) + ' rows<br>showing ' + oppRows.length;
      renderOpps();
    });
  }

  function renderOpps() {
    var tb = $('opps-body');
    if (!oppRows.length) {
      tb.innerHTML = '<tr><td colspan="4" class="empty">No opportunities match these filters.</td></tr>';
    } else {
      tb.innerHTML = oppRows.map(function (r) {
        return '<tr data-id="' + esc(r.id) + '" tabindex="0" class="' + (String(r.id) === selectedId ? 'sel' : '') + '">' +
          '<td><span class="score ' + tierClass(r.tier) + '">' + dash(r.score) + '</span></td>' +
          '<td>' + dash(r.title) + '</td>' +
          '<td class="dim">' + dash(r.institution) + '</td>' +
          '<td class="mono">' + dash(fmtDate(r.deadline_iso, r.deadline)) + '</td>' +
          '</tr>';
      }).join('');
    }
    renderDetail();
  }

  function selectRow(id) {
    selectedId = String(id);
    Array.prototype.forEach.call($('opps-body').rows, function (tr) {
      tr.classList.toggle('sel', tr.dataset.id === selectedId);
    });
    renderDetail();
  }

  function currentRow() {
    var found = oppRows.filter(function (r) { return String(r.id) === selectedId; });
    return found[0] || null;
  }

  function renderDetail() {
    var r = currentRow();
    $('detail-empty').hidden = !!r;
    $('detail-body').hidden = !r;
    if (!r) return;

    var label = TIER_LABEL[r.tier];
    $('d-score').className = 'score ' + tierClass(r.tier);
    $('d-score').textContent = (r.score == null ? '—' : r.score) + (label ? ' · ' + label : '');
    $('d-title').textContent = r.title || 'Untitled';
    $('d-inst').textContent = r.institution || '—';
    $('d-level').textContent = [r.category, r.type].filter(Boolean).join(' · ') || '—';
    $('d-funding').textContent = r.funding || '—';
    var closes = fmtDate(r.deadline_iso, r.deadline, true);
    $('d-closes').innerHTML = esc(closes || '—') +
      (r.days_left != null ? ' <span class="days">· ' + esc(dayWord(r.days_left)) + '</span>' : '');
    $('d-fields').textContent = r.fields || '—';
    $('d-source').textContent = r.source || '—';

    $('d-why').textContent = r.rationale || 'No rationale yet. Run Re-evaluate to score it.';
    $('d-why').classList.toggle('dim', !r.rationale);

    var ol = $('d-prep');
    ol.innerHTML = '';
    var items = splitActions(r.action_items);
    if (!items.length) {
      var none = document.createElement('li');
      none.className = 'dim';
      none.textContent = 'Nothing listed yet.';
      ol.appendChild(none);
    } else {
      items.forEach(function (t) {
        var li = document.createElement('li');
        li.textContent = t;
        ol.appendChild(li);
      });
    }

    $('d-open').disabled = !r.link;
    $('d-reeval').disabled = !r.link;
  }

  /* ---------- sources ---------- */

  function loadSources() {
    return call('get_sources').then(function (list) {
      if (Array.isArray(list)) renderSources(list);
    });
  }

  function renderSources(list) {
    var runningCount = list.filter(function (s) { return s.state === 'running'; }).length;
    $('runs-kicker').textContent = list.length + ' sources · ' + runningCount + ' running';

    // Rebuild the rows only when the set of sources changes, so typed args survive the 2s refresh.
    var sig = list.map(function (s) { return s.key; }).join('|');
    if (sig !== srcSig) {
      srcSig = sig;
      $('ledger-body').innerHTML = list.length
        ? list.map(rowHtml).join('')
        : '<tr><td colspan="6" class="empty">No sources configured.</td></tr>';
    }
    list.forEach(updateRow);
  }

  function rowHtml(s) {
    var args = (s.args || []).map(function (a) {
      var def = a.default == null ? '' : String(a.default);
      var numeric = /^\d+$/.test(def);
      return '<label class="arg"><input data-arg="' + esc(a.name) + '" value="' + esc(def) + '"' +
        (numeric ? '' : ' class="wide"') + '> <span>' + esc(a.label || a.name) + '</span></label>';
    }).join('');
    return '<tr data-key="' + esc(s.key) + '">' +
      '<td class="name">' + esc(s.name) + '</td>' +
      '<td class="how"><div>' + esc(s.method || '') + '</div>' + (args ? '<div class="args">' + args + '</div>' : '') + '</td>' +
      '<td class="mono" data-f="last"></td>' +
      '<td class="mono" data-f="new"></td>' +
      '<td data-f="state"></td>' +
      '<td data-f="action"></td>' +
      '</tr>';
  }

  function rowFor(key) {
    var rows = $('ledger-body').rows;
    for (var i = 0; i < rows.length; i++) {
      if (rows[i].dataset.key === key) return rows[i];
    }
    return null;
  }

  function updateRow(s) {
    var tr = rowFor(s.key);
    if (!tr) return;
    tr.querySelector('[data-f=last]').textContent = s.last_run || '—';
    tr.querySelector('[data-f=new]').textContent = s.new_count == null ? '—' : String(s.new_count);

    var st = STATES[s.state] || STATES.idle;
    var stEl = tr.querySelector('[data-f=state]');
    stEl.className = 'state ' + st[0];
    stEl.textContent = st[1];

    var want = s.state === 'running' ? 'stop' : s.state === 'failed' ? 'retry' : 'run';
    var cell = tr.querySelector('[data-f=action]');
    if (cell.dataset.act !== want) {
      cell.dataset.act = want;
      var label = want === 'stop' ? 'Stop' : want === 'retry' ? 'Retry' : 'Run';
      cell.innerHTML = '<button class="btn line sm" data-act="' + want + '">' + label + '</button>';
    }
  }

  function readArgs(tr) {
    var out = {};
    tr.querySelectorAll('input[data-arg]').forEach(function (i) {
      var v = i.value.trim();
      if (v === '') return;
      out[i.dataset.arg] = /^-?\d+(\.\d+)?$/.test(v) ? Number(v) : v;
    });
    return out;
  }

  function runTask(key, args, view) {
    return call('run_task', key, args || {}).then(done(view || currentView));
  }

  /* ---------- log ---------- */

  function pollLogs() {
    return call('get_logs', logCursor).then(function (d) {
      if (!d || !Array.isArray(d.lines)) return;
      if (d.next != null) logCursor = d.next;
      if (!d.lines.length) return;

      var log = $('log');
      var empty = $('log-empty');
      if (empty) empty.parentNode.removeChild(empty);

      // follow the tail only while the user is already at the bottom
      var atBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 24;
      var frag = document.createDocumentFragment();
      d.lines.forEach(function (l) {
        var line = document.createElement('div');
        line.className = 'ln';
        var t = document.createElement('span');
        t.className = 't';
        t.textContent = l.t || '';
        var task = document.createElement('span');
        task.className = 'task';
        task.textContent = l.task || '';
        var msg = document.createElement('span');
        msg.textContent = l.text || '';
        var cls = { ok: 'ok', warn: 'warn', error: 'err' }[l.level];
        if (cls) msg.className = cls;
        line.appendChild(t);
        line.appendChild(document.createTextNode('  '));
        line.appendChild(task);
        line.appendChild(document.createTextNode('  '));
        line.appendChild(msg);
        frag.appendChild(line);
      });
      log.appendChild(frag);
      while (log.childElementCount > LOG_CAP) log.removeChild(log.firstElementChild);
      if (atBottom) log.scrollTop = log.scrollHeight;
    });
  }

  /* ---------- sidebar status ---------- */

  function pollStatus() {
    return call('get_status').then(function (d) {
      if (!d) return;
      var list = Array.isArray(d.running) ? d.running : [];
      var was = running.length;
      running = list;
      if (list.length) {
        var first = list[0];
        runName = first.name || first.key || 'Running';
        runPid = first.pid;
        runStarted = Date.now() - (Number(first.elapsed_s) || 0) * 1000;
      }
      renderStatus();
      if (list.length || was || currentView === 'runs') loadSources();
      if (was && !list.length) {
        loadOverview();
        if (currentView === 'opps') loadOpportunities();
      }
    });
  }

  function renderStatus() {
    var pulse = $('pulse');
    if (!running.length) {
      pulse.className = 'pulse idle';
      $('st-name').textContent = 'Idle';
      $('st-meta').textContent = 'nothing running';
      return;
    }
    pulse.className = 'pulse';
    $('st-name').textContent = runName;
    var more = running.length > 1 ? ' · +' + (running.length - 1) + ' more' : '';
    $('st-meta').textContent = 'pid ' + (runPid == null ? '—' : runPid) + ' · ' +
      mmss((Date.now() - runStarted) / 1000) + ' elapsed' + more;
  }

  /* ---------- settings ---------- */

  function loadSettings() {
    return call('get_settings').then(function (d) {
      if (!d) return;
      var keys = Array.isArray(d.keys) ? d.keys : [];
      $('keys-body').innerHTML = keys.length
        ? keys.map(function (k) {
            var cls = k.state ? stateClass(k.state) : 'dim';
            return '<tr><td class="mono">' + dash(k.masked) + '</td><td>' + dash(k.provider) + '</td>' +
              '<td class="state ' + cls + '">' + (k.state ? esc(k.state) : '—') + '</td></tr>';
          }).join('')
        : '<tr><td colspan="3" class="empty">No model keys found in .env.</td></tr>';

      var daily = d.daily || {};
      var sel = $('daily-state');
      sel.options[0].textContent = 'On, every day at ' + (daily.time || '—');
      sel.options[1].textContent = 'Off';
      sel.selectedIndex = daily.enabled ? 0 : 1;
    });
  }

  /* ---------- bindings ---------- */

  function bind() {
    document.querySelectorAll('nav button').forEach(function (b) {
      b.addEventListener('click', function () { switchView(b.dataset.v); });
    });

    // Overview
    // (no controls beyond the figures and tables)

    // Opportunities
    var qTimer = null;
    $('f-q').addEventListener('input', function () {
      clearTimeout(qTimer);
      qTimer = setTimeout(loadOpportunities, 200);
    });
    ['f-tier', 'f-funding', 'f-level', 'f-sort'].forEach(function (id) {
      $(id).addEventListener('change', loadOpportunities);
    });
    $('opps-body').addEventListener('click', function (e) {
      var tr = e.target.closest('tr[data-id]');
      if (tr) selectRow(tr.dataset.id);
    });
    $('opps-body').addEventListener('keydown', function (e) {
      if (e.key !== 'Enter') return;
      var tr = e.target.closest('tr[data-id]');
      if (tr) selectRow(tr.dataset.id);
    });
    $('d-open').addEventListener('click', function () {
      var r = currentRow();
      if (!r || !r.link) return;
      call('open_link', r.link).then(function (res) { if (res) clearError('opps'); });
    });
    $('d-reeval').addEventListener('click', function () {
      var r = currentRow();
      if (!r || !r.link) return;
      runTask('evaluate_url', { url: r.link }, 'opps');
    });

    // Sources
    $('btn-deep').addEventListener('click', function () { runTask('deep_eval', {}, 'runs'); });
    $('btn-backlog').addEventListener('click', function () { runTask('backlog', {}, 'runs'); });
    $('btn-all').addEventListener('click', function () { runTask('run_all', {}, 'runs'); });
    $('ledger-body').addEventListener('click', function (e) {
      var btn = e.target.closest('button[data-act]');
      if (!btn) return;
      var tr = btn.closest('tr[data-key]');
      if (!tr) return;
      if (btn.dataset.act === 'stop') {
        call('stop_task', tr.dataset.key).then(done('runs'));
      } else {
        runTask(tr.dataset.key, readArgs(tr), 'runs');
      }
    });

    // Tools
    function evaluateLink() {
      var url = $('tool-url').value.trim();
      if (!/^https?:\/\/\S+$/i.test(url)) {
        showError('Paste a full link that starts with https://');
        return;
      }
      call('run_task', 'evaluate_url', { url: url }).then(function (res) {
        if (!res) return;
        clearError('tools');
        switchView('runs');
        pollStatus();
      });
    }
    $('tool-eval').addEventListener('click', evaluateLink);
    $('tool-url').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') evaluateLink();
    });
    $('tool-login').addEventListener('click', function () { runTask('login', {}, 'tools'); });
    $('tool-clean').addEventListener('click', function () { runTask('clean', {}, 'tools'); });
    $('tool-open').addEventListener('click', function () {
      call('open_tracker').then(function (res) { if (res) clearError('tools'); });
    });

    // Settings
    $('btn-daily').addEventListener('click', function () { runTask('daily', {}, 'settings'); });
  }

  /* ---------- start ---------- */

  function init() {
    bind();
    loadOverview();
    loadSources();
    loadSettings();
    pollStatus();
    pollLogs();
    setInterval(pollLogs, 1000);
    setInterval(pollStatus, 2000);
    setInterval(renderStatus, 1000);
  }

  whenReady(init);
})();
