"use client";

import { useEffect } from "react";

/**
 * Registers the service worker (production only — a SW would fight Next's dev
 * HMR). Navigation is network-first in the SW, so new deploys are picked up
 * on the next load. This component adds two things for a seamless update:
 *
 *  1. checks for a new SW on load and when the tab regains focus, and
 *  2. reloads the page once when a new SW takes control, so the fresh HTML +
 *     assets replace the old ones without a manual hard-refresh.
 *
 * The reload is guarded by a flag so it can never loop.
 */
export function ServiceWorkerRegister() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!("serviceWorker" in navigator)) return;
    if (process.env.NODE_ENV !== "production") return;

    let refreshing = false;
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (refreshing) return;
      refreshing = true;
      window.location.reload();
    });

    navigator.serviceWorker
      .register("/sw.js")
      .then((reg) => {
        // Check for an update immediately, and again whenever the tab is
        // refocused — so a redeploy is caught without a full restart.
        reg.update().catch(() => {});
        const onFocus = () => reg.update().catch(() => {});
        window.addEventListener("focus", onFocus);
      })
      .catch(() => {
        // Non-fatal — the app just falls back to network-only.
      });
  }, []);
  return null;
}
