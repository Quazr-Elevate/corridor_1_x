"use client";

import { ReactNode, useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  api,
  clearUserId,
  getStoredUserId,
  storeUserId,
  type Me,
} from "@/lib/api";
import { MeContext } from "@/lib/useMe";
import { UnsavedGuardProvider, useUnsavedGuard } from "@/lib/useUnsavedGuard";
import { Drawer } from "./Drawer";
import { HamburgerButton } from "./HamburgerButton";

export function DashboardShell({ children }: { children: ReactNode }) {
  return (
    <UnsavedGuardProvider>
      <DashboardShellInner>{children}</DashboardShellInner>
    </UnsavedGuardProvider>
  );
}

function DashboardShellInner({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { confirmIfDirty } = useUnsavedGuard();
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const fetchMe = useCallback(async () => {
    setError(null);
    try {
      const data = await api.me();
      setMe(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not load account";
      setError(msg);
      if (msg.toLowerCase().includes("user") || msg.includes("401")) {
        clearUserId();
        router.replace("/");
      }
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    // The user may have landed here via the magic-link redirect, which
    // only sets the HttpOnly session cookie — localStorage is empty.
    // Bootstrap it from /auth/session before deciding to bounce.
    let cancelled = false;
    (async () => {
      if (!getStoredUserId()) {
        try {
          const { userId } = await api.session();
          if (cancelled) return;
          if (userId) {
            storeUserId(userId);
          } else {
            router.replace("/");
            return;
          }
        } catch {
          if (cancelled) return;
          router.replace("/");
          return;
        }
      }
      if (cancelled) return;
      fetchMe();
    })();

    // Guard: if a prior fetch flagged mustChangePassword, make sure the
    // user is on the password screen before touching anything else.
    // Done here rather than in a separate effect to keep the gate close
    // to the fetch that produced the flag.

    // Watch for session expiry: re-check periodically, on tab focus, and when
    // the browser's storage changes (e.g. sign out from another tab).
    const bounce = () => {
      if (!getStoredUserId()) {
        clearUserId();
        router.replace("/");
      }
    };
    const interval = window.setInterval(bounce, 60_000);
    const onVisible = () => {
      if (document.visibilityState === "visible") bounce();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("storage", bounce);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("storage", bounce);
    };
  }, [fetchMe, router]);

  const handleSignOut = () => {
    confirmIfDirty(() => {
      clearUserId();
      router.replace("/");
    });
  };

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-ink text-paper-muted">
        <p className="text-sm">Loading…</p>
      </main>
    );
  }

  if (error && !me) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-ink px-4 text-center text-paper">
        <div>
          <p className="text-sm text-paper-muted">Could not load your account.</p>
          <p className="mt-1 text-xs text-paper-muted/70">{error}</p>
        </div>
      </main>
    );
  }

  const title = titleForPath(pathname);

  return (
    <MeContext.Provider value={{ me, loading, error, refetch: fetchMe }}>
      <div className="min-h-dvh bg-ink text-paper safe-x">
        {/* Sticky top bar with the profile-round hamburger */}
        <header
          className="sticky top-0 z-30 border-b border-line-soft/60 bg-ink/80 backdrop-blur-xl"
          style={{ paddingTop: "env(safe-area-inset-top)" }}
        >
          <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6">
            <HamburgerButton
              onClick={() => setDrawerOpen(true)}
              fullName={me?.primary.fullName ?? null}
            />
            <div className="min-w-0 flex-1">
              <p className="text-[10px] uppercase tracking-widest text-paper-muted">
                <span
                  aria-hidden
                  className="mr-1.5 inline-block h-1 w-1 -translate-y-[2px] rounded-full bg-accent align-middle"
                />
                Cor1x · {title.eyebrow}
              </p>
              <p className="truncate text-sm font-semibold tracking-tight text-paper">
                {title.title}
              </p>
            </div>
          </div>
        </header>

        <Drawer
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          email={me?.email ?? ""}
          businessName={me?.businessName ?? null}
          fullName={me?.primary.fullName ?? null}
          onSignOut={handleSignOut}
        />

        <main
          className="mx-auto max-w-6xl p-5 sm:p-8"
          style={{ paddingBottom: "max(env(safe-area-inset-bottom), 32px)" }}
        >
          {children}
        </main>
      </div>
    </MeContext.Provider>
  );
}

function titleForPath(pathname: string): { eyebrow: string; title: string } {
  if (pathname === "/dashboard") return { eyebrow: "home", title: "Dashboard" };
  if (pathname.startsWith("/dashboard/account")) {
    return { eyebrow: "account", title: "My Account" };
  }
  return { eyebrow: "dashboard", title: "Cor1x" };
}
