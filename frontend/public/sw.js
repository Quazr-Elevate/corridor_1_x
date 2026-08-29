// Cor1x service worker — cache-first shell, network-first API.
//
// SHELL cache: HTML shell + all Next.js static assets. Served instantly on
// repeat visits; new versions come in via activate() when we bump VERSION.
// API cache: never; API calls stay network-first and fail hard offline so
// the UI can render its own "you're offline" state instead of stale JSON.

const VERSION = "cor1x-v1";
const SHELL_CACHE = `cor1x-shell-${VERSION}`;
const RUNTIME_CACHE = `cor1x-runtime-${VERSION}`;

// Minimal precache — the important thing is that same-origin static assets
// get cached on-demand as the user visits pages, which we handle in fetch().
const PRECACHE_URLS = ["/", "/login", "/signup", "/products", "/privacy", "/terms"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting()),
  );
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

  // Navigation requests (HTML) → cache-first with background revalidate.
  // Serves the shell instantly offline; new HTML lands on next visit.
  if (req.mode === "navigate") {
    event.respondWith(
      caches.match(req).then((cached) => {
        const fetchAndCache = fetch(req)
          .then((res) => {
            if (res.ok) {
              const clone = res.clone();
              caches.open(SHELL_CACHE).then((c) => c.put(req, clone));
            }
            return res;
          })
          .catch(
            () =>
              cached ||
              caches.match("/") ||
              new Response("You're offline", {
                status: 503,
                headers: { "Content-Type": "text/plain" },
              }),
          );
        return cached || fetchAndCache;
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
