/* Browser-preview fallback only. If window.pywebview is still absent 1.5s after load
   (the page was opened in a normal browser), install a fake api that serves the
   mockup's sample data, then fire 'pywebviewready' the way pywebview does. */
(function () {
  'use strict';

  function delay(v) {
    return new Promise(function (resolve) {
      setTimeout(function () { resolve(JSON.parse(JSON.stringify(v))); }, 120);
    });
  }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function clock(d) { return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds()); }

  function opp(o) {
    return Object.assign({
      id: '', title: '', institution: '', category: '', type: '', deadline: '', deadline_iso: null,
      days_left: null, funding: '', fields: '', link: '', score: null, tier: null, rationale: '',
      action_items: '', source: '', scraped_date: '2026-11-04', deep_checked: false
    }, o);
  }

  var OPPS = [
    opp({ id: 'erasmus-mass', title: 'Erasmus Mundus MSc in Astrophysics & Space Science', institution: 'MASS consortium',
      category: 'Masters', type: 'MSc, two years', deadline: '15 Nov 2026', deadline_iso: '2026-11-15', days_left: 11,
      funding: 'Full — €1,400 / month plus travel', fields: 'Astrophysics, cosmology', link: 'https://example.org/erasmus-mass',
      score: 92, tier: 'fit',
      rationale: 'Open to non-EU applicants including Egypt. Requires a BSc in Physics and matches the astrophysics track closely. IELTS 6.5.',
      action_items: 'Two recommendation letters\nMotivation letter, two pages at most\nIELTS certificate',
      source: 'WhatsApp · Erasmus+ channel' }),
    opp({ id: 'daad-epos', title: 'DAAD EPOS — Theoretical & Mathematical Physics', institution: 'LMU Munich',
      category: 'PhD', type: 'Doctoral', deadline: '20 Nov 2026', deadline_iso: '2026-11-20', days_left: 16,
      funding: 'Full', fields: 'Theoretical physics', link: 'https://example.org/daad-epos', score: 88, tier: 'fit',
      source: 'GradSchoolShopper' }),
    opp({ id: 'padova-data', title: 'Excellence Grant, Physics of Data', institution: 'Univ. of Padova · DSU Veneto',
      category: 'Masters', type: 'MSc', deadline: '28 Nov 2026', deadline_iso: '2026-11-28', days_left: 24,
      funding: 'Partial', fields: 'Data science, physics', link: 'https://example.org/padova-data', score: 71, tier: 'maybe',
      source: 'Scholarships Corner' }),
    opp({ id: 'ictp-hep', title: 'Postgraduate Diploma, High Energy Physics', institution: 'ICTP Trieste',
      category: 'Diploma', type: 'PG Diploma', deadline: '01 Dec 2026', deadline_iso: '2026-12-01', days_left: 27,
      funding: 'Full', fields: 'High energy physics', link: 'https://example.org/ictp-hep', score: 90, tier: 'fit',
      source: 'MastersPortal' }),
    opp({ id: 'york-plasma', title: 'Plasma Physics PhD Studentship', institution: 'University of York',
      category: 'PhD', type: 'Doctoral', deadline: '10 Jan 2027', deadline_iso: '2027-01-10', days_left: null,
      funding: 'Partial', fields: 'Plasma physics', link: 'https://example.org/york-plasma', score: 64, tier: 'maybe',
      source: 'MastersPortal' }),
    opp({ id: 'ie-mba', title: 'MBA Leadership Scholarship', institution: 'IE Business School',
      category: 'MBA', type: 'MBA', deadline: '12 Dec 2026', deadline_iso: '2026-12-12', days_left: null,
      funding: 'Partial', fields: 'Business', link: 'https://example.org/ie-mba', score: 18, tier: 'no',
      source: 'WeMakeScholars' })
  ];

  var SOURCES = [
    { key: 'whatsapp', name: 'WhatsApp channels', method: '6 channels', args: [{ name: 'limit', label: 'msgs each', default: 25 }], last_run: null, new_count: null, base: 'ok' },
    { key: 'catch', name: 'Catch That Scholarship', method: 'JSON feed', args: [], last_run: '07:04', new_count: 12, base: 'ok' },
    { key: 'gss', name: 'GradSchoolShopper', method: 'AIP directory', args: [], last_run: '07:05', new_count: 3, base: 'ok' },
    { key: 'profellow', name: 'ProFellow', method: 'browser · Cloudflare check blocked', args: [{ name: 'pages', label: 'pages', default: 3 }], last_run: '07:09', new_count: 0, base: 'failed' },
    { key: 'wemake', name: 'WeMakeScholars', method: 'browser · paginated', args: [{ name: 'pages', label: 'pages', default: 4 }, { name: 'category', label: 'category', default: 'physics' }], last_run: '07:12', new_count: 17, base: 'ok' },
    { key: 'corner', name: 'Scholarships Corner', method: 'WordPress API', args: [{ name: 'pages', label: 'pages', default: 5 }, { name: 'per_page', label: 'per page', default: 20 }], last_run: '07:13', new_count: 49, base: 'ok' },
    { key: 'masters', name: 'MastersPortal', method: 'browser · physics & astronomy', args: [{ name: 'pages', label: 'pages', default: 6 }, { name: 'discipline', label: 'discipline', default: 'physics' }], last_run: '07:20', new_count: 31, base: 'ok' },
    { key: 'silat', name: 'Hussain Silat', method: '67 Italian universities · DSU', args: [], last_run: '07:21', new_count: 2, base: 'ok' }
  ];

  var running = { whatsapp: { pid: 18244, started: Date.now() - 134000 } };
  var logs = [
    { t: '07:31:02', task: 'whatsapp', text: 'opening persistent session', level: 'info' },
    { t: '07:31:09', task: 'whatsapp', text: 'Erasmus+ — 25 messages read', level: 'ok' },
    { t: '07:31:15', task: 'dedup', text: '19 already seen, 6 queued', level: 'info' },
    { t: '07:31:16', task: 'groq#2', text: 'evaluating "Erasmus Mundus MSc in Astrophysics…"', level: 'info' },
    { t: '07:31:18', task: 'groq#2', text: '429 rate limited, switching to gemini#1', level: 'warn' },
    { t: '07:31:20', task: 'tracker', text: 'scored 92, row written', level: 'ok' }
  ];

  function pushLog(task, text, level) {
    logs.push({ t: clock(new Date()), task: task, text: text, level: level });
  }
  function sourceByKey(key) {
    return SOURCES.filter(function (s) { return s.key === key; })[0] || null;
  }
  function nameOf(key) {
    var s = sourceByKey(key);
    return s ? s.name : key;
  }

  function listOpps(f) {
    f = f || {};
    var q = (f.q || '').toLowerCase();
    var rows = OPPS.filter(function (r) {
      if (q && [r.title, r.institution, r.fields].join(' ').toLowerCase().indexOf(q) === -1) return false;
      if (f.tier && r.tier !== f.tier) return false;
      if (f.funding && r.funding.toLowerCase().indexOf(f.funding) === -1) return false;
      if (f.level && r.category !== f.level && r.type.indexOf(f.level) === -1) return false;
      return true;
    });
    var cmp;
    if (f.sort === 'score') cmp = function (a, b) { return (b.score || 0) - (a.score || 0); };
    else if (f.sort === 'newest') cmp = function (a, b) { return a.id < b.id ? 1 : -1; };
    else cmp = function (a, b) { return (a.deadline_iso || '9999') < (b.deadline_iso || '9999') ? -1 : 1; };
    rows.sort(cmp);
    return { total: OPPS.length, rows: rows };
  }

  var api = {
    get_overview: function () {
      var closing = OPPS.filter(function (r) {
        return r.days_left != null && r.days_left >= 0 && r.days_left <= 30;
      }).sort(function (a, b) { return a.days_left - b.days_left; });
      return delay({
        total: 1284, fit: 96, maybe: 211, no: 980, backlog: 37,
        last_sweep: '07:02', next_sweep: '05 Nov 07:00',
        closing: closing,
        yield: [
          { source: 'WhatsApp channels', count: 64, failed: false },
          { source: 'Scholarships Corner', count: 49, failed: false },
          { source: 'MastersPortal', count: 31, failed: false },
          { source: 'WeMakeScholars', count: 17, failed: false },
          { source: 'Catch That Scholarship', count: 12, failed: false },
          { source: 'ProFellow', count: 7, failed: true }
        ]
      });
    },

    list_opportunities: function (filters) { return delay(listOpps(filters)); },

    get_sources: function () {
      return delay(SOURCES.map(function (s) {
        var r = running[s.key];
        return {
          key: s.key, name: s.name, method: s.method, args: s.args,
          state: r ? 'running' : s.base, last_run: s.last_run, new_count: s.new_count,
          pid: r ? r.pid : null
        };
      }));
    },

    run_task: function (key) {
      if (running[key]) return delay({ error: nameOf(key) + ' is already running' });
      running[key] = { pid: 20000 + Math.floor(Math.random() * 9000), started: Date.now() };
      pushLog(key, 'started', 'info');
      setTimeout(function () {
        if (!running[key]) return;
        delete running[key];
        var s = sourceByKey(key);
        if (s) s.base = 'ok';
        pushLog(key, 'finished', 'ok');
      }, 7000);
      return delay({ ok: true });
    },

    stop_task: function (key) {
      if (running[key]) {
        delete running[key];
        pushLog(key, 'stopped', 'warn');
      }
      return delay({ ok: true });
    },

    get_logs: function (since) {
      var from = Number(since) || 0;
      return delay({ next: logs.length, lines: logs.slice(from) });
    },

    get_status: function () {
      return delay({
        running: Object.keys(running).map(function (k) {
          return {
            key: k,
            name: k === 'whatsapp' ? 'WhatsApp sweep' : nameOf(k),
            pid: running[k].pid,
            elapsed_s: Math.floor((Date.now() - running[k].started) / 1000)
          };
        })
      });
    },

    get_settings: function () {
      return delay({
        keys: [
          { masked: 'gsk_····a91f', provider: 'Groq', state: 'Healthy' },
          { masked: 'gsk_····77c2', provider: 'Groq', state: 'Rate limited' },
          { masked: 'AIza····Q3k', provider: 'Gemini', state: 'Healthy' }
        ],
        daily: { enabled: true, time: '07:00' }
      });
    },

    open_link: function (url) {
      console.info('[preview] open_link', url);
      return delay({ ok: true });
    },

    open_tracker: function () {
      console.info('[preview] open_tracker');
      return delay({ ok: true });
    }
  };

  setTimeout(function () {
    if (window.pywebview) return;
    window.pywebview = { api: api };
    window.dispatchEvent(new Event('pywebviewready'));
  }, 1500);
})();
