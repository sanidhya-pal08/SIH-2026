/**
 * NER Sahayak Service Worker — App Shell Cache
 *
 * Caches:
 *  - Application shell (HTML, JS, CSS bundles)
 *  - Static assets
 *
 * Does NOT cache:
 *  - API responses (those come from IndexedDB operational cache)
 *  - Map tiles (respects tile provider ToS; avoiding unlimited cache growth)
 *  - Authentication endpoints
 */

const CACHE_NAME = 'ner-sahayak-shell-v1';

// Assets to pre-cache on install — Vite build outputs hashed filenames,
// so we cache the root HTML and let navigation requests serve from cache.
const PRECACHE_URLS = [
  '/',
  '/index.html',
];

// ── Install: pre-cache app shell ─────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

// ── Activate: clean up old caches ────────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

// ── Fetch: network-first for API, cache-first for shell ──────────────────────
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Never intercept API calls or external tile requests — let them fail naturally
  // so the application's own error handling (queue) kicks in.
  if (
    url.pathname.startsWith('/api/') ||
    url.hostname.includes('tile.openstreetmap.org') ||
    event.request.method !== 'GET'
  ) {
    return; // pass through, don't intercept
  }

  // For navigation requests (HTML) and static assets — cache-first with network fallback
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;

      return fetch(event.request)
        .then((response) => {
          // Only cache valid same-origin responses (not opaque cross-origin)
          if (
            response.ok &&
            response.type === 'basic' &&
            !url.pathname.startsWith('/api/')
          ) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => {
          // Offline fallback for navigation requests
          if (event.request.mode === 'navigate') {
            return caches.match('/index.html');
          }
          return new Response('', { status: 503 });
        });
    })
  );
});
