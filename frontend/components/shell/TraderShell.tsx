"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError, type Me } from "@/lib/api";
import { cn } from "@/lib/cn";
import { MEDIA } from "@/lib/media";
import { MeContext } from "@/lib/useMe";
import { UnsavedGuardProvider, useUnsavedGuard } from "@/lib/useUnsavedGuard";
import { AmbientPhoto } from "@/components/art/AmbientPhoto";
import { FxProvider } from "@/components/fx/FxContext";
import { EASE, SPRING } from "@/components/motion/tokens";
import { LinkButton } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Kbd } from "@/components/ui/Kbd";
import { XMark } from "@/components/ui/Logo";
import { ToastProvider } from "@/components/ui/Toast";
import { CommandPalette } from "@/components/trader/CommandPalette";
import { buildCommands, navigateTo } from "@/components/trader/commands";
import { initials } from "@/components/trader/format";
import { LensProvider, LensSwitch, useLens } from "@/components/trader/lens";

/**
 * Trader surface (cream) — matches the approved portal (/corridor):
 *   • behind everything: the cream ground, the day-port photograph
 *     multiplied in (30%, blurred), drifting warm light and film grain
 *   • top cluster (sticky, fading into the page): the X disc + wordmark,
 *     the Selling/Buying lens on the Corridor home, and a glass pill with
 *     "Search or jump to… ⌘K", the verification state and the avatar
 *   • the glass dock at the bottom: the four places a trader lives
 * Content sits on the cream in relief; glass is only for what floats.
 *
 * `requireAuth` (dashboard) bounces anonymous visitors to /login.
 * Without it (public market), the shell renders signed-out chrome.
 */

const DOCK: ReadonlyArray<{ href: string; label: string; icon: IconName; match: (p: string) => boolean }> = [
  { href: "/dashboard", label: "Corridor", icon: "corridor", match: (p) => p === "/dashboard" },
  { href: "/products", label: "Market", icon: "grain", match: (p) => p.startsWith("/products") },
  { href: "/dashboard/products", label: "Listings", icon: "sack", match: (p) => p.startsWith("/dashboard/products") },
  { href: "/dashboard/business", label: "Business", icon: "building", match: (p) => p.startsWith("/dashboard/business") || p.startsWith("/dashboard/account") },
];

/** The page measure shared by the top cluster and the content. */
const MEASURE = "mx-auto w-full max-w-[1360px] px-4 sm:px-8 lg:px-10";

export function TraderShell({
  children,
  requireAuth = true,
}: {
  children: ReactNode;
  requireAuth?: boolean;
}) {
  return (
    <UnsavedGuardProvider>
      <ToastProvider>
        <TraderShellInner requireAuth={requireAuth}>{children}</TraderShellInner>
      </ToastProvider>
    </UnsavedGuardProvider>
  );
}

function TraderShellInner({ children, requireAuth }: { children: ReactNode; requireAuth: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMe = useCallback(async () => {
    setError(null);
    try {
      setMe(await api.me());
    } catch (err) {
      setMe(null);
      if (err instanceof ApiError && err.status === 401) {
        if (requireAuth) {
          const next = typeof window !== "undefined" ? window.location.pathname + window.location.search : "/dashboard";
          router.replace(`/login?next=${encodeURIComponent(next)}`);
          return;
        }
      } else {
        setError(err instanceof Error ? err.message : "Could not load your account");
      }
    } finally {
      setLoading(false);
    }
  }, [requireAuth, router]);

  useEffect(() => {
    void fetchMe();
    // Session can expire while the tab sits open — recheck on focus.
    const onVisible = () => {
      if (document.visibilityState === "visible") void fetchMe();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [fetchMe]);

  const signedIn = !!me;
  const showDock = signedIn;

  return (
    <MeContext.Provider value={{ me, loading, error, refetch: fetchMe }}>
      <FxProvider>
      <LensProvider me={me}>
        <div data-surface="trader" className="relative min-h-dvh text-fg">
          <AmbientPhoto media={MEDIA.portDay} position="fixed" className="-z-10" />
          <TopCluster me={me} loading={loading} pathname={pathname} />
          <main className={cn(MEASURE, "pt-2", showDock ? "pb-40" : "pb-20")}>
            {requireAuth && loading && !me ? (
              <ShellLoading />
            ) : requireAuth && error && !me ? (
              <ShellError message={error} onRetry={fetchMe} />
            ) : (
              children
            )}
          </main>
          {showDock ? (
            <>
              {/* The page fades out under the dock, as it does under the top cluster. */}
              <div
                aria-hidden="true"
                className="pointer-events-none fixed inset-x-0 bottom-0 z-30 h-36"
                style={{
                  background:
                    "linear-gradient(to top, var(--c-ground) 18%, rgb(244 241 236 / 0.7) 55%, rgb(244 241 236 / 0))",
                }}
              />
              <Dock pathname={pathname} />
            </>
          ) : null}
        </div>
      </LensProvider>
      </FxProvider>
    </MeContext.Provider>
  );
}

// ─── Top cluster ─────────────────────────────────────────────────────

function useSignOut() {
  const router = useRouter();
  const { confirmIfDirty } = useUnsavedGuard();
  return useCallback(
    () =>
      confirmIfDirty(async () => {
        try {
          await api.logout();
        } finally {
          router.replace("/login");
        }
      }),
    [confirmIfDirty, router],
  );
}

function TopCluster({ me, loading, pathname }: { me: Me | null; loading: boolean; pathname: string }) {
  const { confirmIfDirty } = useUnsavedGuard();
  const router = useRouter();
  const { lens, setLens } = useLens();
  const signOut = useSignOut();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const signedIn = !!me;
  const onHome = pathname === "/dashboard";

  // ⌘K / Ctrl+K from anywhere on the trader surface.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && !e.altKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const go = useCallback(
    (href: string) => navigateTo(href, (h) => router.push(h), confirmIfDirty),
    [router, confirmIfDirty],
  );

  const commands = useMemo(
    () => buildCommands({ me, lens, setLens, go, signOut }),
    [me, lens, setLens, go, signOut],
  );

  return (
    <header className="sticky top-0 z-40 pt-[env(safe-area-inset-top,0px)]">
      {/* Content slides under a fade into the ground, not under a bar. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-28"
        style={{
          background:
            "linear-gradient(to bottom, var(--c-ground) 10%, rgb(244 241 236 / 0.6) 55%, rgb(244 241 236 / 0))",
        }}
      />
      <div className={cn(MEASURE, "relative flex items-center justify-between gap-2 py-4 sm:gap-3")}>
        <div className="flex min-w-0 items-center gap-2.5 sm:gap-5">
          <Link
            href={signedIn ? "/dashboard" : "/"}
            onClick={(e) => {
              e.preventDefault();
              confirmIfDirty(() => router.push(signedIn ? "/dashboard" : "/"));
            }}
            aria-label="Corridor One X — home"
            className="flex shrink-0 items-center gap-2.5 rounded-full pr-1"
          >
            <span className="solid grid size-10 place-items-center rounded-full text-lime">
              <XMark size={17} />
            </span>
            <span className="hidden text-[15px] font-medium tracking-[-0.02em] lg:block">Corridor One X</span>
          </Link>
          {signedIn && onHome ? <LensSwitch /> : null}
        </div>

        <div className="glass flex shrink-0 items-center gap-1 rounded-full p-1">
          <SearchButton onOpen={() => setPaletteOpen(true)} />
          {loading ? null : signedIn && me ? (
            <>
              <VerificationState me={me} />
              <AccountMenu me={me} onSignOut={signOut} />
            </>
          ) : (
            <>
              <LinkButton href="/login" variant="quiet" size="sm" className="h-10 rounded-full">
                Sign in
              </LinkButton>
              <LinkButton href="/signup" size="sm" className="h-10 rounded-full">
                Get verified
              </LinkButton>
            </>
          )}
        </div>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} commands={commands} />
    </header>
  );
}

function SearchButton({ onOpen }: { onOpen: () => void }) {
  const [mod, setMod] = useState("⌘");
  useEffect(() => {
    const mac = /mac|iphone|ipad|ipod/i.test(navigator.platform || navigator.userAgent);
    if (!mac) setMod("Ctrl");
  }, []);
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label="Search or jump to"
      aria-keyshortcuts="Meta+K Control+K"
      aria-haspopup="dialog"
      className="flex h-10 items-center gap-2.5 rounded-full px-3 text-fg-3 transition-colors hover:bg-fg/5 hover:text-fg-2 md:min-w-[220px]"
    >
      <Icon name="search" size={17} />
      <span className="t-sub hidden flex-1 text-left md:block">Search or jump to…</span>
      <span className="hidden items-center gap-0.5 md:flex" aria-hidden="true">
        <Kbd>{mod}</Kbd>
        <Kbd>K</Kbd>
      </span>
    </button>
  );
}

/**
 * Where verification stands. Wide: a chip ("4/7 to verify", "In review",
 * "Verified"). Phones: the Passport glyph with an amber dot while
 * something is waiting on you — the reference's bell, made real.
 */
function VerificationState({ me }: { me: Me }) {
  const v = me.verification;
  const s = v.status;
  const filled = v.mandatoryTotal - v.missing.length;
  const yourMove = s === "rejected" || (s !== "verified" && s !== "pending_verification");
  const label =
    s === "verified"
      ? "Verified"
      : s === "pending_verification"
        ? "In review"
        : s === "rejected"
          ? "Needs changes"
          : `${filled} of ${v.mandatoryTotal} items to verify`;
  const chip =
    s === "verified" ? (
      <Chip tone="verified">Verified</Chip>
    ) : s === "pending_verification" ? (
      <Chip tone="move" icon="clock">
        In review
      </Chip>
    ) : s === "rejected" ? (
      <Chip tone="frozen">Needs changes</Chip>
    ) : (
      <Chip tone="move" noIcon>
        {filled}/{v.mandatoryTotal} to verify
      </Chip>
    );
  return (
    <Link
      href="/dashboard/business"
      aria-label={`Business profile — ${label}`}
      className="relative grid h-10 min-w-10 place-items-center rounded-full px-0 text-fg-2 transition-colors hover:bg-fg/5 hover:text-fg sm:px-1.5"
    >
      <span className="hidden sm:inline-flex">{chip}</span>
      <span className="sm:hidden">
        <Icon name={s === "verified" ? "shield" : "passport"} size={18} />
        {yourMove ? (
          <span className="absolute right-2 top-2 size-2 rounded-full bg-amber ring-2 ring-[var(--glass-solid)]" />
        ) : null}
      </span>
    </Link>
  );
}

function AccountMenu({ me, onSignOut }: { me: Me; onSignOut: () => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const reduce = useReducedMotion();
  const { confirmIfDirty } = useUnsavedGuard();

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const go = (href: string) => {
    setOpen(false);
    confirmIfDirty(() => router.push(href));
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="solid t-code grid size-10 place-items-center rounded-full text-[12px]"
        aria-label="Account menu"
      >
        {initials(me)}
      </button>
      <AnimatePresence>
        {open ? (
          <motion.div
            role="menu"
            initial={reduce ? { opacity: 0 } : { opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, y: -4 }}
            transition={{ duration: 0.35, ease: EASE }}
            className="glass absolute right-0 top-[calc(100%+12px)] w-64 rounded-[22px] p-2"
          >
            <div className="flex items-center gap-3 px-3 pb-3 pt-2">
              <span className="solid t-code grid size-9 shrink-0 place-items-center rounded-full text-[11px]">
                {initials(me)}
              </span>
              <div className="min-w-0">
                <p className="t-headline truncate text-fg">{me.primary.fullName || "Your account"}</p>
                <p className="t-foot truncate text-fg-3">{me.email}</p>
              </div>
            </div>
            <MenuItem icon="passport" onClick={() => go("/dashboard/account")}>
              Passport
            </MenuItem>
            <MenuItem icon="settings" onClick={() => go("/dashboard/settings")}>
              Settings &amp; security
            </MenuItem>
            <div className="my-1.5 h-px bg-line" />
            <MenuItem
              icon="logout"
              onClick={() => {
                setOpen(false);
                onSignOut();
              }}
            >
              Sign out
            </MenuItem>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function MenuItem({ icon, onClick, children }: { icon: IconName; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-[14px] px-3 py-2.5 text-left text-[14px] text-fg-2 transition-colors hover:bg-fg/5 hover:text-fg"
    >
      <Icon name={icon} size={17} />
      {children}
    </button>
  );
}

// ─── Dock ────────────────────────────────────────────────────────────

function Dock({ pathname }: { pathname: string }) {
  const router = useRouter();
  const reduce = useReducedMotion();
  const { confirmIfDirty } = useUnsavedGuard();
  return (
    <nav
      aria-label="Primary"
      className="glass fixed inset-x-3 z-40 flex justify-between rounded-[26px] p-1.5 sm:inset-x-auto sm:left-1/2 sm:-translate-x-1/2 sm:gap-1"
      style={{ bottom: "max(14px, env(safe-area-inset-bottom))" }}
    >
      {DOCK.map((d) => {
        const active = d.match(pathname);
        return (
          <Link
            key={d.href}
            href={d.href}
            onClick={(e) => {
              e.preventDefault();
              confirmIfDirty(() => router.push(d.href));
            }}
            aria-current={active ? "page" : undefined}
            className={cn(
              "relative flex h-[56px] flex-1 flex-col items-center justify-center gap-1 rounded-[20px] transition-colors duration-300 sm:w-[84px] sm:flex-none",
              active ? "text-cream" : "text-fg-2 hover:text-fg",
            )}
          >
            {active ? (
              <motion.span
                layoutId="dock-active"
                className="solid absolute inset-0 rounded-[20px]"
                transition={reduce ? { duration: 0 } : SPRING}
              />
            ) : null}
            <Icon name={d.icon} size={19} className="relative" />
            <span className="relative text-[11px] font-medium tracking-[-0.005em]">{d.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

// ─── Loading / error ─────────────────────────────────────────────────

function ShellLoading() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center" aria-busy="true">
      <div className="relief-sm grid size-14 place-items-center rounded-full">
        <svg width="20" height="20" viewBox="0 0 24 24" className="animate-spin text-fg-2" aria-hidden="true">
          <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity=".2" strokeWidth="2" />
          <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </div>
      <span className="sr-only">Loading your corridor…</span>
    </div>
  );
}

function ShellError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="mx-auto flex min-h-[50vh] max-w-md flex-col items-center justify-center text-center">
      <span className="grid size-14 place-items-center rounded-full bg-danger-soft text-danger">
        <Icon name="alert" size={22} />
      </span>
      <p className="t-title3 mt-5">We couldn&rsquo;t reach the corridor</p>
      <p className="t-callout mt-2 text-fg-2">{message}</p>
      <button type="button" onClick={onRetry} className="t-callout mt-6 font-medium text-fg underline underline-offset-4">
        Try again
      </button>
    </div>
  );
}
