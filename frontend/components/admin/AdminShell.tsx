"use client";

import { ReactNode, useEffect, useState } from "react";
import Image from "next/image";
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
        <p className="text-sm" style={{ color: "var(--sp-text-3)" }}>Loading…</p>
      </main>
    );
  }
  if (!email) return null;

  return (
    <div className={cls + " relative min-h-dvh"}>
      <SpatialField />

      {/* ── Mobile top bar ── */}
      <div
        className="sticky top-0 z-30 flex items-center gap-3 px-4 py-3 backdrop-blur-xl md:hidden"
        style={{
          borderBottom: "1px solid var(--sp-border)",
          background: "var(--sp-topbar)",
          paddingTop: "max(env(safe-area-inset-top), 12px)",
        }}
      >
        <button
          type="button"
          aria-label="Open menu"
          onClick={() => setDrawer(true)}
          className="sp-icon-btn h-9 w-9"
        >
          <Menu className="h-4 w-4" aria-hidden />
        </button>
        <Image src="/brand/wordmark.png" alt="Corridor One X" width={1583} height={173} priority className="h-3.5 w-auto select-none opacity-90 [.sp-light_&]:brightness-0 [.sp-light_&]:opacity-90" />
        <span className="ml-auto text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: "var(--sp-text-3)" }}>
          Admin
        </span>
      </div>

      <div className="relative flex w-full">
        {/* ── Desktop floating icon rail ── */}
        <IconRail pathname={pathname} theme={theme} onNav={nav} onSignOut={signOut} onToggleTheme={toggle} />

        {/* ── Mobile drawer (labelled) ── */}
        {drawer && (
          <div className="fixed inset-0 z-50 md:hidden">
            <button type="button" aria-label="Close menu" onClick={() => setDrawer(false)} className="absolute inset-0" style={{ background: "var(--sp-scrim)", animation: "dotsIn 0.2s ease both" }} />
            <DrawerNav pathname={pathname} email={email} theme={theme} onNav={nav} onSignOut={signOut} onToggleTheme={toggle} onClose={() => setDrawer(false)} />
          </div>
        )}

        {/* ── Workspace ── */}
        <main className="relative min-w-0 flex-1 px-5 py-6 sm:px-8 sm:py-8 md:pl-2">
          <RouteTransition>{children}</RouteTransition>
        </main>
      </div>
    </div>
  );
}

// ── Desktop: floating, elevated, icon-only rail ──────────────────────────────

function IconRail({
  pathname,
  theme,
  onNav,
  onSignOut,
  onToggleTheme,
}: {
  pathname: string;
  theme: AdminTheme;
  onNav: (href: string) => void;
  onSignOut: () => void;
  onToggleTheme: () => void;
}) {
  return (
    <aside className="sticky top-4 z-20 my-4 ml-4 hidden h-[calc(100dvh-32px)] w-[68px] shrink-0 flex-col items-center md:flex">
      <div className="sp-airy flex h-full w-full flex-col items-center gap-1 rounded-[24px] px-2.5 py-4">
        {/* Brand mark */}
        <button
          type="button"
          onClick={() => onNav("/admin")}
          aria-label="Corridor One X — Dashboard"
          className="mb-3 flex h-11 w-11 items-center justify-center rounded-[14px] transition-transform hover:scale-105"
          style={{ background: "var(--sp-lime-10)" }}
        >
          <Image src="/brand/x-mark-lime.svg" alt="" width={22} height={22} className="h-[22px] w-[22px]" />
        </button>

        {/* Nav — icon only, black active + lime icon */}
        <nav className="flex flex-col items-center gap-2">
          {NAV.map((item) => {
            const active = item.match(pathname);
            const Icon = item.icon;
            return (
              <RailButton key={item.href} label={item.label} active={active} onClick={() => onNav(item.href)}>
                <Icon className="h-[19px] w-[19px]" aria-hidden />
              </RailButton>
            );
          })}
        </nav>

        {/* Bottom — theme + sign out */}
        <div className="mt-auto flex flex-col items-center gap-2">
          <RailButton label={theme === "light" ? "Dark theme" : "Light theme"} onClick={onToggleTheme}>
            {theme === "light" ? <Moon className="h-[18px] w-[18px]" aria-hidden /> : <Sun className="h-[18px] w-[18px]" aria-hidden />}
          </RailButton>
          <RailButton label="Sign out" onClick={onSignOut} danger>
            <LogOut className="h-[18px] w-[18px]" aria-hidden />
          </RailButton>
        </div>
      </div>
    </aside>
  );
}

function RailButton({
  label,
  active,
  danger,
  onClick,
  children,
}: {
  label: string;
  active?: boolean;
  danger?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      aria-current={active ? "page" : undefined}
      className="group relative flex h-11 w-11 items-center justify-center rounded-[14px] transition-all duration-200"
      style={{
        background: active ? "#0c0e0c" : "transparent",
        boxShadow: active ? "0 6px 16px -6px rgba(0,0,0,0.4)" : "none",
        color: active ? "var(--sp-lime)" : danger ? "var(--sp-text-3)" : "var(--sp-text-2)",
        transform: active ? "translateY(-1px)" : "none",
      }}
      onMouseEnter={(e) => {
        if (!active) {
          e.currentTarget.style.background = "var(--sp-card-2)";
          e.currentTarget.style.color = danger ? "var(--sp-error)" : "var(--sp-text)";
        }
      }}
      onMouseLeave={(e) => {
        if (!active) {
          e.currentTarget.style.background = "transparent";
          e.currentTarget.style.color = danger ? "var(--sp-text-3)" : "var(--sp-text-2)";
        }
      }}
    >
      {children}
      {/* Tooltip */}
      <span
        className="pointer-events-none absolute left-[54px] z-50 hidden whitespace-nowrap rounded-[8px] px-2.5 py-1.5 text-[11px] font-medium shadow-lg group-hover:block"
        style={{ background: "#0c0e0c", color: "#f2f4ee" }}
      >
        {label}
      </span>
    </button>
  );
}

// ── Mobile: labelled drawer ──────────────────────────────────────────────────

function DrawerNav({
  pathname,
  email,
  theme,
  onNav,
  onSignOut,
  onToggleTheme,
  onClose,
}: {
  pathname: string;
  email: string;
  theme: AdminTheme;
  onNav: (href: string) => void;
  onSignOut: () => void;
  onToggleTheme: () => void;
  onClose: () => void;
}) {
  return (
    <aside
      className="relative flex h-full w-[260px] max-w-[80vw] flex-col px-4 py-6"
      style={{ background: "var(--sp-canvas-elevated)", animation: "spDrawerIn 0.32s var(--sp-ease) both", paddingTop: "max(env(safe-area-inset-top),24px)" }}
    >
      <div className="mb-8 flex items-center gap-2.5 px-1">
        <span className="flex h-8 w-8 items-center justify-center rounded-[9px]" style={{ background: "var(--sp-lime-10)" }}>
          <Image src="/brand/x-mark-lime.svg" alt="" width={18} height={18} className="h-[18px] w-[18px]" />
        </span>
        <span>
          <span className="block text-[10px] font-bold uppercase tracking-[0.16em]" style={{ color: "var(--sp-text-3)" }}>Corridor One X</span>
          <span className="block text-[13px] font-semibold" style={{ color: "var(--sp-text)" }}>Admin console</span>
        </span>
        <button type="button" aria-label="Close menu" onClick={onClose} className="ml-auto flex h-8 w-8 items-center justify-center rounded-[9px]" style={{ color: "var(--sp-text-3)" }}>
          <X className="h-4 w-4" aria-hidden />
        </button>
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
              className="flex items-center gap-3 rounded-[12px] px-3 py-2.5 text-[13.5px] transition-colors"
              style={{
                background: active ? "#0c0e0c" : "transparent",
                color: active ? "#f2f4ee" : "var(--sp-text-2)",
              }}
            >
              <Icon className="h-[18px] w-[18px]" aria-hidden style={{ color: active ? "var(--sp-lime)" : "var(--sp-text-3)" }} />
              {item.label}
            </button>
          );
        })}
      </nav>

      <button type="button" onClick={onToggleTheme} className="mt-auto flex items-center gap-2.5 rounded-[12px] px-3 py-2.5 text-[13px]" style={{ color: "var(--sp-text-2)" }}>
        {theme === "light" ? <Moon className="h-[18px] w-[18px]" aria-hidden /> : <Sun className="h-[18px] w-[18px]" aria-hidden style={{ color: "var(--sp-lime)" }} />}
        {theme === "light" ? "Dark theme" : "Light theme"}
      </button>
      <div className="mt-2 pt-4" style={{ borderTop: "1px solid var(--sp-border)" }}>
        <p className="text-[10px] font-bold uppercase tracking-[0.12em]" style={{ color: "var(--sp-text-3)" }}>Signed in</p>
        <p className="mt-1 truncate text-[12.5px] font-medium" style={{ color: "var(--sp-text)" }}>{email}</p>
        <button type="button" onClick={onSignOut} className="mt-3 inline-flex items-center gap-2 text-[12.5px]" style={{ color: "var(--sp-text-2)" }}>
          <LogOut aria-hidden className="h-3.5 w-3.5" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
