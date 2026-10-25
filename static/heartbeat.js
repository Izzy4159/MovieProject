// Tab heartbeat for the local server's watchdog (main.py): every open tab checks
// in, and says goodbye on close, so the server can stop once the last tab is gone.
// On Render the watchdog is off and these requests are simply ignored.
(function () {
  // Not crypto.randomUUID — it's unavailable over plain http on the LAN
  const tab = Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  const body = 'tab=' + tab;
  const opts = { method: 'POST', body: body, keepalive: true,
                 headers: { 'Content-Type': 'application/x-www-form-urlencoded' } };

  function beat() { fetch('/heartbeat', opts).catch(function () {}); }

  beat();
  setInterval(beat, 15000);
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') beat();
  });
  window.addEventListener('pageshow', function (e) { if (e.persisted) beat(); });   // back/forward cache
  window.addEventListener('pagehide', function () {
    const data = new Blob([body], { type: 'application/x-www-form-urlencoded' });
    if (!(navigator.sendBeacon && navigator.sendBeacon('/bye', data))) {
      fetch('/bye', opts).catch(function () {});
    }
  });
})();
