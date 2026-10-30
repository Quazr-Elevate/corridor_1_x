"use client";

import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type MouseEvent,
  type ReactNode,
} from "react";
import { adminApi, type DashboardStats } from "@/lib/adminApi";
import { cn } from "@/lib/cn";
import { UnsavedGuardProvider, useUnsavedGuard } from "@/lib/useUnsavedGuard";
import { Icon, type IconName } from "@/components/ui/Icon";
import { XMark } from "@/components/ui/Logo";
import { ToastProvider } from "@/components/ui/Toast";
import { SPRING } from "@/components/motion/tokens";
import { TowerBackdrop } from "@/components/admin/TowerBackdrop";

/**
 * Ink · Control Tower — the ops surface, after the approved reference
 * (portal /ops). A floating glass rail on the left from `md` (a glass dock
 * along the bottom on phones), a sticky mono status line on top that fades
 * into the ink, and content in relief over the night-port backdrop. The
 * whole document switches to the tower surface while mounted so portalled
 * sheets and toasts inherit the dark tokens.
 */

interface TowerCtx {
  email: string | null;
  stats: DashboardStats | null;
  refreshStats: () => Promise<void>;
}

const TowerContext = createContext<TowerCtx>({
  email: null,
  stats: null,
  refreshStats: async () => {},
});

export const useTower = () => useContext(TowerContext);

const NAV: ReadonlyArray<{
  href: string;
  label: string;
  icon: IconName;
  count?: (s: DashboardStats) => number;
  match: (p: string) => boolean;
}> = [
  { href: "/admin", label: "Tower", icon: "radar", match: (p) => p === "/admin" },
  // KYB now points at the full account directory — the old "review queue"
  // page (/admin/verify) has moved into the Docs lane where profile +
  // business cert are reviewed together. Admins come here to list every
  // account, filter by status, and edit a specific business.
  {
    href: "/admin/users",
    label: "KYB",
    icon: "passport",
    match: (p) => p.startsWith("/admin/users") || p.startsWith("/admin/verify"),
  },
  {
    href: "/admin/docs",
    label: "Docs",
    icon: "doc-check",
    count: (s) => s.pendingDocs,
    match: (p) => p.startsWith("/admin/docs"),
  },
  {
    href: "/admin/doc-requirements",
    label: "Doc rules",
    icon: "settings",
    match: (p) => p.startsWith("/admin/doc-requirements"),
  },
];

export function TowerShell({ children }: { children: ReactNode }) {
  return (
    <UnsavedGuardProvider>
      <ToastProvider>
        <TowerShellInner>{children}</TowerShellInner>
      </ToastProvider>
    </UnsavedGuardProvider>
  );
}

/** Apply the tower surface to <html> so portals (sheets, toasts) match. */
export function useTowerSurface() {
  useEffect(() => {
    const el = document.documentElement;
    const prev = el.dataset.surface;
    el.dataset.surface = "tower";
    return () => {
      if (prev) el.dataset.surface = prev;
      else delete el.dataset.surface;
    };
  }, []);
}

function TowerShellInner({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { confirmIfDirty } = useUnsavedGuard();
  const [email, setEmail] = useState<string | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [ready, setReady] = useState(false);
  useTowerSurface();

  const refreshStats = useCallback(async () => {
    try {
      setStats(await adminApi.stats());
    } catch {
      /* counts are decorative — the pages surface their own errors */
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    adminApi
      .me()
      .then((m) => {
        if (cancelled) return;
        setEmail(m.email);
        setReady(true);
        void refreshStats();
      })
      .catch(() => router.replace("/admin/login"));
    return () => {
      cancelled = true;
    };
  }, [router, refreshStats]);

  // Keep the queue counts fresh as the operator moves between lanes.
  useEffect(() => {
    if (ready) void refreshStats();
  }, [pathname, ready, refreshStats]);

  const signOut = () =>
    confirmIfDirty(async () => {
      try {
        await adminApi.logout();
      } finally {
        router.replace("/admin/login");
      }
    });

  return (
    <TowerContext.Provider value={{ email, stats, refreshStats }}>
      <div data-surface="tower" className="relative isolate min-h-dvh bg-ground text-fg">
        <TowerBackdrop />
        <Rail pathname={pathname} stats={stats} onSignOut={signOut} />
        <div className="md:pl-[108px]">
          <StatusLine email={email} />
          <main className="mx-auto w-full max-w-[1500px] px-4 pb-32 sm:px-8 md:pb-16">
            {ready ? children : <TowerLoading />}
          </main>
        </div>
      </div>
    </TowerContext.Provider>
  );
}

/* ───────────────────────────── Rail + dock ────────────────────────── */

function Rail({
  pathname,
  stats,
  onSignOut,
}: {
  pathname: string;
  stats: DashboardStats | null;
  onSignOut: () => void;
}) {
  const router = useRouter();
  const reduce = useReducedMotion();
  const { confirmIfDirty } = useUnsavedGuard();
  const items = NAV.map((n) => {
    const active = n.match(pathname);
    const count = stats && n.count ? n.count(stats) : 0;
    return { ...n, active, count };
  });

  const go = (e: MouseEvent<HTMLAnchorElement>, href: string) => {
    // New-tab / new-window clicks keep the browser's own behaviour.
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    confirmIfDirty(() => router.push(href));
  };

  const pill = (layout: "rail" | "dock") => (
    <motion.span
      layoutId={`tower-${layout}`}
      className="absolute inset-0 rounded-[inherit] bg-cream shadow-[0_12px_30px_-14px_rgb(0_0_0/0.9)]"
      transition={reduce ? { duration: 0 } : SPRING}
    />
  );

  const badge = (count: number, label: string) =>
    count ? (
      <span
        className="t-code absolute -right-3 -top-2 grid h-4 min-w-4 place-items-center rounded-full bg-lime px-1 text-[10px] leading-none text-ink"
        aria-label={`${count} waiting in ${label}`}
      >
        {count > 99 ? "99+" : count}
      </span>
    ) : null;

  return (
    <>
      <nav
        aria-label="Ops lanes"
        className="glass fixed bottom-3 left-3 top-3 z-40 hidden w-[92px] flex-col items-center rounded-[28px] py-4 md:flex"
      >
        <Link
          href="/admin"
          onClick={(e) => go(e, "/admin")}
          aria-label="Control Tower home"
          className="grid size-11 shrink-0 place-items-center rounded-full bg-lime text-ink shadow-[0_10px_24px_-12px_rgb(196_216_46/0.7)]"
        >
          <XMark size={18} />
        </Link>
        <ul className="no-scrollbar mt-6 flex w-full flex-1 flex-col items-center gap-1 overflow-y-auto px-2">
          {items.map((n) => (
            <li key={n.href} className="w-full">
              <Link
                href={n.href}
                onClick={(e) => go(e, n.href)}
                aria-current={n.active ? "page" : undefined}
                className={cn(
                  "relative flex h-[60px] w-full flex-col items-center justify-center gap-1 rounded-[18px] transition-colors duration-300",
                  n.active ? "text-ink" : "text-fg-3 hover:text-fg",
                )}
              >
                {n.active ? pill("rail") : null}
                <span className="relative">
                  <Icon name={n.icon} size={19} />
                  {badge(n.count, n.label)}
                </span>
                <span className="relative text-[10.5px] font-medium">{n.label}</span>
              </Link>
            </li>
          ))}
        </ul>
        <button
          type="button"
          onClick={onSignOut}
          aria-label="Sign out"
          title="Sign out"
          className="mt-3 grid size-11 shrink-0 place-items-center rounded-full text-fg-3 transition-colors duration-300 hover:bg-white/[0.08] hover:text-fg"
        >
          <Icon name="logout" size={18} />
        </button>
      </nav>

      <nav
        aria-label="Ops lanes"
        className="glass no-scrollbar fixed inset-x-3 bottom-[max(12px,env(safe-area-inset-bottom))] z-40 flex gap-1 overflow-x-auto rounded-[22px] p-1.5 md:hidden"
      >
        {items.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            onClick={(e) => go(e, n.href)}
            aria-current={n.active ? "page" : undefined}
            className={cn(
              "relative flex h-12 min-w-[64px] flex-1 flex-col items-center justify-center gap-0.5 rounded-[16px] transition-colors duration-300",
              n.active ? "text-ink" : "text-fg-3 hover:text-fg",
            )}
          >
            {n.active ? pill("dock") : null}
            <span className="relative">
              <Icon name={n.icon} size={18} />
              {badge(n.count, n.label)}
            </span>
            <span className="relative text-[10px] font-medium">{n.label}</span>
          </Link>
        ))}
        <button
          type="button"
          onClick={onSignOut}
          aria-label="Sign out"
          className="relative flex h-12 min-w-[52px] flex-col items-center justify-center gap-0.5 rounded-[16px] text-fg-3 transition-colors hover:text-fg"
        >
          <Icon name="logout" size={18} />
          <span className="text-[10px] font-medium">Exit</span>
        </button>
      </nav>
    </>
  );
}

/* ───────────────────────────── Status line ────────────────────────── */

function useClock(tz: string) {
  const [t, setT] = useState("");
  useEffect(() => {
    const fmt = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: tz });
    const tick = () => setT(fmt.format(new Date()));
    tick();
    const id = window.setInterval(tick, 15_000);
    return () => window.clearInterval(id);
  }, [tz]);
  return t;
}

function StatusLine({ email }: { email: string | null }) {
  const ist = useClock("Asia/Kolkata");
  const gst = useClock("Asia/Dubai");
  return (
    <div className="sticky top-0 z-30">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-[linear-gradient(to_bottom,var(--c-ground)_10%,rgb(10_10_10/0.6)_55%,transparent)]"
      />
      <div className="relative mx-auto flex max-w-[1500px] items-center justify-between gap-3 px-4 py-4 sm:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <span className="t-label shrink-0 whitespace-nowrap rounded-full bg-lime-soft px-3 py-1.5 text-accent">
            Control Tower
          </span>
          <span className="t-label hidden truncate text-fg-3 sm:inline" title={email ?? undefined}>
            Ops · {email ?? "—"}
          </span>
        </div>
        <div className="glass flex shrink-0 items-center gap-3 rounded-full px-3.5 py-2 sm:gap-4 sm:px-4">
          <span className="t-code whitespace-nowrap text-fg-2">
            <span className="text-fg-3">IST</span> <span className="tabular">{ist || "--:--"}</span>
          </span>
          <span className="h-4 w-px bg-line-2" aria-hidden="true" />
          <span className="t-code whitespace-nowrap text-fg-2">
            <span className="text-fg-3">GST</span> <span className="tabular">{gst || "--:--"}</span>
          </span>
          <span className="relative ml-0.5 flex size-2" role="img" aria-label="Live">
            <span className="animate-beacon absolute inset-0 rounded-full bg-lime" />
            <span className="relative size-2 rounded-full bg-lime" />
          </span>
        </div>
      </div>
    </div>
  );
}

function TowerLoading() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center" aria-busy="true">
      <svg width="22" height="22" viewBox="0 0 24 24" className="animate-spin text-fg-3" aria-hidden="true">
        <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity=".2" strokeWidth="2" />
        <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
      <span className="sr-only">Opening the tower…</span>
    </div>
  );
}
