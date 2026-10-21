import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Icon, type IconName } from "./Icon";

/**
 * Status & labels. Tone carries meaning:
 *   verified — lime-soft / olive: certain, approved
 *   move     — amber: your move, waiting on you
 *   frozen   — danger: rejected, blocked, overdue
 *   neutral  — line outline: informational
 *   solid    — ink fill: a selected / strong label
 */
export type ChipTone = "verified" | "move" | "frozen" | "neutral" | "solid" | "quiet";

const tones: Record<ChipTone, string> = {
  verified: "bg-lime-soft text-accent",
  move: "bg-amber-soft text-amber",
  frozen: "bg-danger-soft text-danger",
  neutral: "text-fg-2 shadow-[inset_0_0_0_1px_var(--c-line-2)]",
  solid: "solid",
  quiet: "bg-fg/5 text-fg-2",
};

const defaultIcon: Partial<Record<ChipTone, IconName>> = {
  verified: "shield",
  frozen: "alert",
};

export type ChipSize = "sm" | "md";

const sizes: Record<ChipSize, string> = {
  sm: "h-5 gap-1 px-2 text-[11px]",
  md: "h-6 gap-1.5 px-2.5 text-[12px]",
};

export function Chip({
  tone = "neutral",
  icon,
  noIcon,
  size = "md",
  className,
  children,
}: {
  tone?: ChipTone;
  icon?: IconName;
  noIcon?: boolean;
  /** `sm` for dense rows and table cells; `md` (default) everywhere else. */
  size?: ChipSize;
  className?: string;
  children: ReactNode;
}) {
  const ic = noIcon ? undefined : icon ?? defaultIcon[tone];
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center whitespace-nowrap rounded-full font-medium leading-none tracking-[-0.005em]",
        sizes[size],
        tones[tone],
        className,
      )}
    >
      {ic ? <Icon name={ic} size={size === "sm" ? 12 : 13} strokeWidth={1.8} className="shrink-0" /> : null}
      {children}
    </span>
  );
}

/** Mono step counter pill, e.g. "3/7 Profile". */
export function CountPill({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "t-code inline-flex h-6 items-center gap-1 rounded-full px-2.5 text-fg-2 shadow-[inset_0_0_0_1px_var(--c-line-2)]",
        className,
      )}
    >
      {children}
    </span>
  );
}

/** Small numeric badge (dock / rail notification count). */
export function CountBadge({ count, className }: { count: number; className?: string }) {
  if (!count) return null;
  return (
    <span
      className={cn(
        "t-code grid h-[18px] min-w-[18px] place-items-center rounded-full bg-ink px-1 text-[10px] leading-none text-cream",
        "[[data-surface=tower]_&]:bg-lime [[data-surface=tower]_&]:text-ink",
        className,
      )}
    >
      {count > 99 ? "99+" : count}
    </span>
  );
}
