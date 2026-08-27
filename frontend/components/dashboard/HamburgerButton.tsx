"use client";

import { Menu } from "lucide-react";

interface Props {
  onClick: () => void;
  fullName?: string | null;
}

/**
 * Circular profile-style button that toggles the nav drawer. If we have the
 * user's name, we show their initial with the hamburger as a small overlay;
 * otherwise plain hamburger.
 */
export function HamburgerButton({ onClick, fullName }: Props) {
  const initial = fullName?.trim()?.[0]?.toUpperCase();

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Open navigation"
      className="group relative inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-line-soft bg-ink-elevated text-paper transition-all hover:border-accent hover:shadow-[0_0_0_3px_rgba(211,236,75,0.15)]"
    >
      {initial ? (
        <>
          <span className="text-sm font-semibold">{initial}</span>
          <span
            aria-hidden
            className="absolute -bottom-0.5 -right-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full border border-line-soft bg-ink text-paper"
          >
            <Menu className="h-2.5 w-2.5" strokeWidth={2.5} />
          </span>
        </>
      ) : (
        <Menu className="h-4 w-4" />
      )}
    </button>
  );
}
