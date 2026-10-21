// Service worker — caches static assets (/static/*) only.
// Pages, posters, thumbs and API calls always go to the network.
// Static URLs carry ?v=<mtime>, so cache-first is safe: an edited file gets a new URL.

const CACHE = 'moviedb-static-v1';

self.addEventListener('install', function () { self.skipWaiting(); });

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(keys.filter(function (k) { return k !== CACHE; })
                               .map(function (k) { return caches.delete(k); }));
      })
      .then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (event) {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith('/static/')) return;

  event.respondWith(
    caches.open(CACHE).then(async function (cache) {
      const hit = await cache.match(req);
      if (hit) return hit;
      const resp = await fetch(req);
      if (resp.ok) {
        // Drop older versions of the same file (different ?v=) before storing
        const old = await cache.keys();
        await Promise.all(old.filter(function (k) {
          const u = new URL(k.url);
          return u.pathname === url.pathname && u.search !== url.search;
        }).map(function (k) { return cache.delete(k); }));
        cache.put(req, resp.clone());
      }
      return resp;
    })
  );
});
