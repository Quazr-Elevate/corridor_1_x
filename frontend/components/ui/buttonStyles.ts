import { cn } from "@/lib/cn";

/**
 * Button style maps — server-safe (no "use client"), so server components
 * can style a <Link>, <a> or <summary> like a button:
 *
 *   <Link href="/x" className={buttonClass("secondary", "sm")}>…</Link>
 *
 * Variants:
 *   primary     Solid ink. The default "do this" action.
 *   secondary   Relief. Actionable, but not the main path.
 *   commit      Lime fill — only for moves that make something certain
 *               (verify, submit, approve). Use sparingly.
 *   quiet       Text-only, for tertiary actions.
 *   danger      Text in danger, soft fill on hover.
 *   night       Primary on night glass (auth screens).
 *   night-quiet Outline on night glass.
 */
export type ButtonVariant =
  | "primary"
  | "secondary"
  | "commit"
  | "quiet"
  | "danger"
  | "night"
  | "night-quiet";
export type ButtonSize = "sm" | "md" | "lg";

const base =
  "relative inline-flex select-none items-center justify-center gap-2 whitespace-nowrap font-medium tracking-[-0.01em] " +
  "transition-[transform,box-shadow,background-color,color,opacity] duration-300 ease-expo active:scale-[0.98] " +
  "disabled:pointer-events-none disabled:opacity-45 aria-disabled:pointer-events-none aria-disabled:opacity-45";

const sizes: Record<ButtonSize, string> = {
  sm: "h-9 rounded-[12px] px-3.5 text-[13px]",
  md: "h-11 rounded-control px-5 text-[14px]",
  lg: "h-[52px] rounded-field px-6 text-[15px]",
};

const variants: Record<ButtonVariant, string> = {
  primary: "solid hover:bg-[#1a1a1a] [[data-surface=tower]_&]:hover:bg-white",
  secondary: "relief-sm text-fg hover:shadow-[var(--relief)]",
  commit:
    "bg-lime text-ink shadow-[0_14px_30px_-14px_rgb(120_140_10/0.7),inset_0_1px_0_rgb(255_255_255/0.45)] hover:bg-lime-hover",
  quiet: "text-fg-2 hover:bg-fg/5 hover:text-fg",
  danger: "text-danger hover:bg-danger-soft",
  night: "bg-cream text-ink hover:bg-white",
  "night-quiet":
    "text-cream shadow-[inset_0_0_0_1px_rgb(255_255_255/0.14)] hover:bg-white/[0.06]",
};

export function buttonClass(
  variant: ButtonVariant = "primary",
  size: ButtonSize = "md",
  className?: string,
) {
  return cn(base, sizes[size], variants[variant], className);
}

/** Icon size that matches a button size. */
export function buttonIconSize(size: ButtonSize = "md") {
  return size === "lg" ? 18 : 16;
}

/* ───────────────────────────── Icon buttons ───────────────────────────
   Round, icon-only. `night` sits on night glass; `glass` floats over
   photography or busy content (carousel arrows, image actions). */

export type IconButtonVariant = "quiet" | "secondary" | "primary" | "night" | "glass";
export type IconButtonSize = "sm" | "md" | "lg";

const iconVariants: Record<IconButtonVariant, string> = {
  quiet: "text-fg-2 hover:bg-fg/5 hover:text-fg",
  secondary: "relief-sm text-fg hover:shadow-[var(--relief)]",
  primary: "solid",
  night: "text-cream/60 hover:bg-white/[0.07] hover:text-cream",
  glass: "glass text-fg hover:text-fg",
};

const iconSizes: Record<IconButtonSize, string> = {
  sm: "size-8",
  md: "size-10",
  lg: "size-12",
};

export function iconButtonClass(
  variant: IconButtonVariant = "quiet",
  size: IconButtonSize = "md",
  className?: string,
) {
  return cn(
    "inline-grid shrink-0 place-items-center rounded-full transition-[background-color,box-shadow,color,opacity] duration-300 ease-expo",
    "disabled:pointer-events-none disabled:opacity-45",
    iconSizes[size],
    iconVariants[variant],
    className,
  );
}

export function iconButtonGlyphSize(size: IconButtonSize = "md") {
  return size === "sm" ? 16 : size === "lg" ? 20 : 18;
}
