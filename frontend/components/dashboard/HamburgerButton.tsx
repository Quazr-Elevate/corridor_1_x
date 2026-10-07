"use client";

interface Props {
  onClick: () => void;
  fullName?: string | null;
}

/**
 * Classic 3-line hamburger. Clicking opens the slide-in drawer with
 * Dashboard + My Account nav.
 */
export function HamburgerButton({ onClick }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Open navigation"
      className="inline-flex h-10 w-10 shrink-0 flex-col items-center justify-center gap-[5px] rounded-field border border-line-soft bg-ink-elevated text-paper transition hover:border-accent hover:shadow-[0_0_0_3px_rgba(211,236,75,0.15)]"
    >
      <span aria-hidden className="block h-[2px] w-5 rounded bg-paper" />
      <span aria-hidden className="block h-[2px] w-5 rounded bg-paper" />
      <span aria-hidden className="block h-[2px] w-5 rounded bg-paper" />
    </button>
  );
}
