/* Browser-preview transport. Active ONLY when the page was opened from
   `python -m src.desktop --serve` (the URL carries #token=...). It routes every
   window.pywebview.api.<method>(...) call to the real Python Api over HTTP, so
   the browser preview shows the same live data as the desktop window.
   Inside pywebview there is no token, so this file does nothing. */
(function () {
  'use strict';
  if (window.pywebview) return;
  var m = /(?:^#|&)token=([^&]+)/.exec(location.hash || '');
  if (!m || (location.protocol !== 'http:' && location.protocol !== 'https:')) return;
  var token = decodeURIComponent(m[1]);

  function remote(name) {
    return function () {
      var args = Array.prototype.slice.call(arguments);
      return fetch('/api/' + encodeURIComponent(name), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Hunter-Token': token },
        body: JSON.stringify({ args: args })
      }).then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (body) {
          if (!r.ok && !(body && body.error)) return { error: 'HTTP ' + r.status };
          return body;
        });
      }, function () {
        return { error: 'Lost connection to the local server. Is `python -m src.desktop --serve` still running?' };
      });
    };
  }

  var cache = {};
  window.pywebview = {
    api: new Proxy({}, {
      get: function (_, name) {
        if (typeof name !== 'string') return undefined;
        return cache[name] || (cache[name] = remote(name));
      }
    })
  };
})();
