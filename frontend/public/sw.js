// Cor1x service worker — NETWORK-FIRST HTML, cache-first immutable assets.
//
// HTML (navigations): always try the network first so a new deploy is picked
// up immediately; fall back to cache only when offline. This is what keeps
// the app from serving a stale build after a redeploy.
// Next.js static assets (/_next/static/*): content-hashed + immutable, so
// cache-first is safe — new builds emit new URLs.
// API: never cached (cookie-authed; would leak between viewers).

const VERSION = "cor1x-v2";
const SHELL_CACHE = `cor1x-shell-${VERSION}`;
const RUNTIME_CACHE = `cor1x-runtime-${VERSION}`;

// Cache "/" so a cold offline load still shows the shell. Everything else is
// filled on demand.
const PRECACHE_URLS = ["/"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting()),
  );
});

// Let the page tell a waiting SW to activate immediately (used on update).
self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((n) => n.startsWith("cor1x-") && !n.endsWith(VERSION))
            .map((n) => caches.delete(n)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // Cross-origin (backend API, fonts) → network-first. Backend calls are
  // authenticated with cookies; caching them would leak between viewers.
  if (url.origin !== self.location.origin) {
    event.respondWith(fetch(req).catch(() => new Response(null, { status: 504 })));
    return;
  }

  // Never cache Next.js runtime endpoints that MUST be live.
  if (url.pathname.startsWith("/_next/webpack-hmr") || url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(req));
    return;
  }

  // Navigation requests (HTML) → NETWORK-FIRST. Always fetch fresh so a new
  // deploy shows immediately; cache the copy for offline; fall back to cache
  // (or "/") only when the network fails.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const clone = res.clone();
            caches.open(SHELL_CACHE).then((c) => c.put(req, clone));
          }
          return res;
        })
        .catch(async () => {
          const cached = (await caches.match(req)) || (await caches.match("/"));
          return (
            cached ||
            new Response("You're offline", {
              status: 503,
              headers: { "Content-Type": "text/plain" },
            })
          );
        }),
    );
    return;
  }

  // Static assets (JS, CSS, fonts, images) → cache-first, add to runtime cache.
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req)
        .then((res) => {
          if (res.ok && (url.pathname.startsWith("/_next/") || url.pathname.startsWith("/icons/") || url.pathname.startsWith("/brand/"))) {
            const clone = res.clone();
            caches.open(RUNTIME_CACHE).then((c) => c.put(req, clone));
          }
          return res;
        })
        .catch(() => new Response(null, { status: 504 }));
    }),
  );
});
