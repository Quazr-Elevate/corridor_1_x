"use client";

import { ReactNode, useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CheckSquare, LayoutDashboard, LogOut, Menu, Moon, Sun, Users, X } from "lucide-react";
import { adminApi } from "@/lib/adminApi";
import { UnsavedGuardProvider, useUnsavedGuard } from "@/lib/useUnsavedGuard";
import { RouteTransition, SpatialField, useAdminTheme, type AdminTheme } from "./spatial";

interface Props {
  children: ReactNode;
}

const NAV = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard, match: (p: string) => p === "/admin" },
  { href: "/admin/verify", label: "Verify queue", icon: CheckSquare, match: (p: string) => p.startsWith("/admin/verify") },
  { href: "/admin/users", label: "Users", icon: Users, match: (p: string) => p.startsWith("/admin/users") },
];

export function AdminShell({ children }: Props) {
  return (
    <UnsavedGuardProvider>
      <AdminShellInner>{children}</AdminShellInner>
    </UnsavedGuardProvider>
  );
}

function AdminShellInner({ children }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const { confirmIfDirty } = useUnsavedGuard();
  const { theme, toggle, cls } = useAdminTheme();
  const [email, setEmail] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [drawer, setDrawer] = useState(false);

  useEffect(() => {
    adminApi
      .me()
      .then((r) => setEmail(r.email))
      .catch(() => router.replace("/admin/login"))
      .finally(() => setReady(true));
  }, [router]);

  // Close the mobile drawer whenever the route changes.
  useEffect(() => setDrawer(false), [pathname]);

  const signOut = () =>
    confirmIfDirty(async () => {
      try {
        await adminApi.logout();
      } finally {
        router.replace("/admin/login");
      }
    });

  const nav = (href: string) => confirmIfDirty(() => router.push(href));

  if (!ready) {
    return (
      <main className={cls + " flex min-h-dvh items-center justify-center"}>
        <p className="text-sm" style={{ color: "var(--sp-text-3)" }}>
          Loading…
        </p>
      </main>
    );
  }
  if (!email) return null;

  return (
    <div className={cls + " relative min-h-dvh"}>
      <SpatialField />

      {/* ── Mobile top bar ── */}
      <div
        className="sticky top-0 z-30 flex items-center gap-3 border-b px-4 py-3 backdrop-blur-xl md:hidden"
        style={{
          borderColor: "var(--sp-border)",
          background: "var(--sp-topbar)",
          paddingTop: "max(env(safe-area-inset-top), 12px)",
        }}
      >
        <button
          type="button"
          aria-label="Open menu"
          onClick={() => setDrawer(true)}
          className="flex h-9 w-9 items-center justify-center rounded-[10px] transition-transform active:scale-95"
          style={{ border: "1px solid var(--sp-border)", background: "var(--sp-surface)" }}
        >
          <Menu className="h-4 w-4" aria-hidden />
        </button>
        <Image
          src="/brand/wordmark.png"
          alt="Corridor One X"
          width={1583}
          height={173}
          priority
          className="h-3.5 w-auto select-none opacity-90"
        />
        <span
          className="ml-auto text-[10px] font-bold uppercase tracking-[0.14em]"
          style={{ color: "var(--sp-text-3)" }}
        >
          Admin
        </span>
      </div>

      <div className="relative mx-auto flex w-full max-w-[1600px]">
        {/* ── Desktop sidebar — integrated into the canvas ── */}
        <Sidebar
          pathname={pathname}
          email={email}
          onNav={nav}
          onSignOut={signOut}
          theme={theme}
          onToggleTheme={toggle}
          className="sticky top-0 hidden h-dvh w-[240px] shrink-0 md:flex"
        />

        {/* ── Mobile drawer ── */}
        {drawer && (
          <div className="fixed inset-0 z-50 md:hidden">
            <button
              type="button"
              aria-label="Close menu"
              onClick={() => setDrawer(false)}
              className="absolute inset-0"
              style={{ background: "var(--sp-scrim)", animation: "dotsIn 0.2s ease both" }}
            />
            <Sidebar
              pathname={pathname}
              email={email}
              onNav={nav}
              onSignOut={signOut}
              theme={theme}
              onToggleTheme={toggle}
              onClose={() => setDrawer(false)}
              className="relative flex h-full w-[260px] max-w-[80vw]"
              style={{
                background: "var(--sp-canvas-elevated)",
                animation: "spDrawerIn 0.32s var(--sp-ease) both",
              }}
            />
          </div>
        )}

        {/* ── Workspace ── */}
        <main className="relative min-w-0 flex-1 px-5 py-6 sm:px-8 sm:py-8">
          <RouteTransition>{children}</RouteTransition>
        </main>
      </div>
    </div>
  );
}

function Sidebar({
  pathname,
  email,
  onNav,
  onSignOut,
  theme,
  onToggleTheme,
  onClose,
  className = "",
  style,
}: {
  pathname: string;
  email: string;
  onNav: (href: string) => void;
  onSignOut: () => void;
  theme: AdminTheme;
  onToggleTheme: () => void;
  onClose?: () => void;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <aside
      className={"flex-col px-4 py-6 " + className}
      style={{
        borderRight: "1px solid var(--sp-border)",
        ...style,
        paddingTop: "max(env(safe-area-inset-top), 24px)",
      }}
    >
      <div className="mb-8 flex items-center gap-2 px-1">
        <button
          type="button"
          onClick={() => onNav("/admin")}
          className="flex items-center gap-2.5 transition-opacity hover:opacity-80"
        >
          <span
            className="flex h-8 w-8 items-center justify-center rounded-[9px]"
            style={{ background: "var(--sp-lime-10)" }}
          >
            <Image src="/brand/x-mark-lime.svg" alt="" width={18} height={18} className="h-[18px] w-[18px]" />
          </span>
          <span className="text-left">
            <span className="block text-[10px] font-bold uppercase tracking-[0.16em]" style={{ color: "var(--sp-text-3)" }}>
              Corridor One X
            </span>
            <span className="block text-[13px] font-semibold" style={{ color: "var(--sp-text)" }}>
              Admin console
            </span>
          </span>
        </button>
        {onClose && (
          <button
            type="button"
            aria-label="Close menu"
            onClick={onClose}
            className="ml-auto flex h-8 w-8 items-center justify-center rounded-[9px] transition-colors"
            style={{ color: "var(--sp-text-3)" }}
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        )}
      </div>

      <nav className="flex flex-col gap-1">
        {NAV.map((item) => {
          const active = item.match(pathname);
          const Icon = item.icon;
          return (
            <button
              key={item.href}
              type="button"
              onClick={() => onNav(item.href)}
              className="group relative flex items-center gap-3 rounded-[10px] px-3 py-2.5 text-[13.5px] transition-colors duration-200"
              style={{
                background: active ? "var(--sp-lime-10)" : "transparent",
                color: active ? "var(--sp-text)" : "var(--sp-text-2)",
                boxShadow: active ? "inset 0 0 0 1px var(--sp-lime-14)" : "none",
              }}
              onMouseEnter={(e) => {
                if (!active) e.currentTarget.style.background = "var(--sp-surface)";
              }}
              onMouseLeave={(e) => {
                if (!active) e.currentTarget.style.background = "transparent";
              }}
            >
              {/* Active indicator — a lime route node on the left rail */}
              <span
                aria-hidden
                className="absolute left-0 top-1/2 h-4 -translate-y-1/2 rounded-full transition-all duration-200"
                style={{
                  width: active ? "2.5px" : "0px",
                  background: "var(--sp-lime)",
                }}
              />
              <Icon
                aria-hidden
                className="h-[18px] w-[18px] transition-colors"
                style={{ color: active ? "var(--sp-lime)" : "var(--sp-text-3)" }}
              />
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* Theme toggle — light | dark, same tokens. */}
      <button
        type="button"
        onClick={onToggleTheme}
        aria-label={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}
        className="mt-auto flex items-center gap-2.5 rounded-[10px] px-3 py-2.5 text-[13px] transition-colors"
        style={{ color: "var(--sp-text-2)" }}
        onMouseEnter={(e) => (e.currentTarget.style.background = "var(--sp-surface)")}
        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
      >
        {theme === "light" ? (
          <Moon aria-hidden className="h-[18px] w-[18px]" style={{ color: "var(--sp-text-3)" }} />
        ) : (
          <Sun aria-hidden className="h-[18px] w-[18px]" style={{ color: "var(--sp-lime)" }} />
        )}
        {theme === "light" ? "Dark theme" : "Light theme"}
      </button>

      <div className="mt-2 pt-4" style={{ borderTop: "1px solid var(--sp-border)" }}>
        <p className="text-[10px] font-bold uppercase tracking-[0.12em]" style={{ color: "var(--sp-text-3)" }}>
          Signed in
        </p>
        <p className="mt-1 truncate text-[12.5px] font-medium" style={{ color: "var(--sp-text)" }}>
          {email}
        </p>
        <button
          type="button"
          onClick={onSignOut}
          className="mt-3 inline-flex items-center gap-2 text-[12.5px] transition-colors"
          style={{ color: "var(--sp-text-2)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--sp-text)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--sp-text-2)")}
        >
          <LogOut aria-hidden className="h-3.5 w-3.5" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
