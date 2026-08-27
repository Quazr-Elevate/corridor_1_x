"use client";

import { ReactNode, useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, clearUserId, getStoredUserId, type Me } from "@/lib/api";
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
    if (!getStoredUserId()) {
      router.replace("/");
      return;
    }
    fetchMe();

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
      <div className="min-h-screen bg-ink text-paper">
        {/* Sticky top bar with the profile-round hamburger */}
        <header className="sticky top-0 z-30 border-b border-line-soft/60 bg-ink/80 backdrop-blur-xl">
          <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6">
            <HamburgerButton
              onClick={() => setDrawerOpen(true)}
              fullName={me?.fullName ?? null}
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
          status={me?.status}
          completion={me?.completion}
          mobile={me?.mobile ?? ""}
          fullName={me?.fullName ?? null}
          onSignOut={handleSignOut}
        />

        <main className="mx-auto max-w-6xl p-5 sm:p-8">{children}</main>
      </div>
    </MeContext.Provider>
  );
}

function titleForPath(pathname: string): { eyebrow: string; title: string } {
  if (pathname === "/dashboard") return { eyebrow: "home", title: "Dashboard" };
  if (pathname.startsWith("/dashboard/profile")) {
    return { eyebrow: "profile", title: "Your profile" };
  }
  if (pathname.startsWith("/dashboard/trust-score")) {
    return { eyebrow: "trust score", title: "Boost your trust" };
  }
  if (pathname.startsWith("/dashboard/products")) {
    return { eyebrow: "products", title: "Your listings" };
  }
  return { eyebrow: "dashboard", title: "Cor1x" };
}
