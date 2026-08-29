"use client";

import { useEffect } from "react";

/**
 * Registers the cache-first service worker on mount. Skipped in dev to
 * avoid stale-content headaches; enabled anywhere the origin is served
 * over HTTPS or on localhost in production build. No install prompt
 * here — the browser handles that on its own once the manifest is valid.
 */
export function ServiceWorkerRegister() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!("serviceWorker" in navigator)) return;
    // Only register the SW in production builds. Next dev serves through
    // HMR and a SW would fight it (stale bundles, blocked reloads).
    if (process.env.NODE_ENV !== "production") return;
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Registration failures are non-fatal — the app just falls back to
      // network-only. Nothing to surface to the user.
    });
  }, []);
  return null;
}
