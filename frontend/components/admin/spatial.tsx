"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState, type ReactNode } from "react";

/**
 * Admin theme — light | dark, derived from the same --sp-* tokens. Persisted
 * per-viewer in localStorage. Light is the default (the console's chosen
 * look); dark stays one toggle away.
 *
 * Returns the class suffix to append to a `.spatial` root and a toggle. Each
 * spatial root (shell + login) calls this so both surfaces stay in sync
 * across navigations.
 */
export type AdminTheme = "light" | "dark";
const THEME_KEY = "cor1x-admin-theme";

export function useAdminTheme(): { theme: AdminTheme; toggle: () => void; cls: string } {
  const [theme, setTheme] = useState<AdminTheme>("light");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(THEME_KEY);
      if (saved === "dark" || saved === "light") setTheme(saved);
    } catch {
      /* storage blocked — stay on the default */
    }
  }, []);

  const toggle = useCallback(() => {
    setTheme((t) => {
      const next = t === "light" ? "dark" : "light";
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  return { theme, toggle, cls: theme === "light" ? "spatial sp-light" : "spatial" };
}

/**
 * RouteTransition — replays the fade+rise entry every time the admin route
 * changes. Keyed on pathname so React remounts the subtree and the CSS
 * animation restarts. transform+opacity only → 60fps, reduced-motion safe
 * (globals collapses the duration).
 */
export function RouteTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div key={pathname} className="sp-route">
      {children}
    </div>
  );
}

/**
 * SpatialField — the ambient canvas decoration: a soft lime radial field
 * upper-right plus a faint route with nodes, all 2–8% opacity. Fixed behind
 * the workspace; never interferes with data.
 */
export function SpatialField() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 overflow-hidden">
      <div
        className="absolute -right-40 -top-40 h-[520px] w-[520px] rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(196,216,46,0.06), transparent 68%)",
          filter: "blur(20px)",
        }}
      />
      <div
        className="absolute -left-52 bottom-[-10%] h-[460px] w-[460px] rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(196,216,46,0.035), transparent 70%)",
          filter: "blur(24px)",
        }}
      />
      <svg
        className="absolute right-0 top-0 h-[560px] w-[520px] opacity-[0.5]"
        viewBox="0 0 520 560"
        fill="none"
      >
        <path
          d="M540,40 C420,90 350,200 330,320 C316,410 350,500 440,548"
          stroke="var(--sp-lime)"
          strokeOpacity="0.14"
          strokeWidth="1.25"
          strokeDasharray="2 10"
          strokeLinecap="round"
        />
        <path
          d="M545,150 C450,175 400,250 388,340 C378,420 410,486 470,520"
          stroke="var(--sp-lime)"
          strokeOpacity="0.1"
          strokeWidth="1.25"
          strokeDasharray="2 12"
          strokeLinecap="round"
        />
        <circle cx="392" cy="132" r="4" fill="var(--sp-lime)" fillOpacity="0.28" />
        <circle cx="332" cy="322" r="3.5" fill="var(--sp-lime)" fillOpacity="0.22" />
        <circle cx="454" cy="452" r="4" fill="var(--sp-lime)" fillOpacity="0.24" />
      </svg>
    </div>
  );
}

/**
 * Rise — staggered section-entry wrapper. Pass an index; each step delays
 * ~70ms so a page composes in as one coordinated reveal.
 */
export function Rise({
  i = 0,
  className = "",
  children,
}: {
  i?: number;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={className}
      style={{
        animation: `spRise 0.5s var(--sp-ease) ${0.05 + i * 0.07}s both`,
      }}
    >
      {children}
    </div>
  );
}
