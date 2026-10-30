"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Icon, type IconName } from "@/components/ui/Icon";

/**
 * Control Tower pieces shared by the lanes — after the approved reference
 * (portal /ops): queue tiles with a big count, attention rows, and the
 * "where things are sitting" column chart.
 */

/* ───────────────────────────── Queue tile ─────────────────────────── */

/**
 * A lane or a number you can open. Relief, 26px corners; an amber ring when
 * something in it is past its target.
 */
export function QueueTile({
  href,
  icon,
  count,
  title,
  sub,
  alert,
  className,
}: {
  href: string;
  icon: IconName;
  count: number | undefined;
  title: string;
  sub: ReactNode;
  /** Something here is past its target — amber ring and amber sub-line. */
  alert?: boolean;
  className?: string;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "relief relief-hover group flex h-full flex-col rounded-[26px] p-5",
        alert && "[box-shadow:var(--relief),inset_0_0_0_1.5px_var(--c-amber)]",
        className,
      )}
    >
      <span className="flex items-center justify-between">
        <span className={cn("grid size-10 place-items-center rounded-full", alert ? "bg-amber-soft text-amber" : "well text-fg-2")}>
          <Icon name={icon} size={18} />
        </span>
        <Icon
          name="arrow-up-right"
          size={17}
          className="text-fg-3 transition-[transform,color] duration-300 ease-expo group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-fg"
        />
      </span>
      <span className="tabular mt-6 block text-[40px] font-medium leading-none tracking-[-0.045em] text-fg">
        {count === undefined ? <span className="text-fg-3">—</span> : count.toLocaleString("en-GB")}
      </span>
      <span className="t-callout mt-2 block font-medium text-fg">{title}</span>
      <span className={cn("t-foot mt-1 block", alert ? "text-amber" : "text-fg-3")}>{sub}</span>
    </Link>
  );
}

/* ───────────────────────────── Attention rows ─────────────────────── */

export type AttentionTone = "move" | "frozen" | "quiet";

export function AttentionRow({
  href,
  icon,
  tone = "quiet",
  title,
  sub,
  meta,
}: {
  href: string;
  icon: IconName;
  tone?: AttentionTone;
  title: ReactNode;
  sub?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <li>
      <Link href={href} className="group -mx-2 flex items-start gap-4 rounded-[18px] px-2 py-4 transition-colors duration-300 hover:bg-white/[0.03]">
        <span
          className={cn(
            "grid size-9 shrink-0 place-items-center rounded-full",
            tone === "move" && "bg-amber-soft text-amber",
            tone === "frozen" && "bg-danger-soft text-danger",
            tone === "quiet" && "well text-fg-2",
          )}
        >
          <Icon name={icon} size={16} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="t-callout block truncate font-medium text-fg">{title}</span>
          {sub ? <span className="t-sub mt-0.5 line-clamp-2 block text-fg-3">{sub}</span> : null}
        </span>
        {meta ? <span className="mt-0.5 shrink-0">{meta}</span> : null}
        <Icon
          name="chevron-right"
          size={16}
          className="mt-2 shrink-0 text-fg-3 transition-transform duration-300 ease-expo group-hover:translate-x-0.5"
        />
      </Link>
    </li>
  );
}

/* ───────────────────────────── Column chart ───────────────────────── */

export interface StationBar {
  key: string;
  label: string;
  count: number;
  href?: string;
  /** Quiet bar (off the main path, e.g. rejected). */
  muted?: boolean;
}

/**
 * Where things are sitting — one column per station, the count on top,
 * a lime bar (muted ones in fg), a mono index and the station name below.
 * Every column links to the matching filter when it has an `href`.
 */
export function StationChart({ bars, label }: { bars: ReadonlyArray<StationBar>; label: string }) {
  const max = Math.max(1, ...bars.map((b) => b.count));
  const cols = { gridTemplateColumns: `repeat(${bars.length}, minmax(0, 1fr))` };
  return (
    <div role="group" aria-label={label}>
      <div className="relative grid h-40 items-end border-b border-line-2" style={cols}>
        {bars.map((b) => {
          const pct = (b.count / max) * 100;
          // The count rides on top of the bar, so bar heights stay true to scale.
          const body = (
            <span
              className={cn(
                "relative w-4 shrink-0 rounded-t-[4px] transition-[height] duration-700 ease-expo sm:w-5",
                b.count === 0 ? "h-[2px] bg-line-2" : b.muted ? "bg-[rgb(237_239_234/0.35)]" : "bg-lime",
              )}
              style={b.count === 0 ? undefined : { height: `${Math.max(pct, 3)}%` }}
            >
              <span className="t-sub tabular absolute bottom-full left-1/2 mb-1.5 -translate-x-1/2 font-medium text-fg">
                {b.count.toLocaleString("en-GB")}
              </span>
            </span>
          );
          const a11y = `${b.label}: ${b.count}`;
          return b.href ? (
            <Link
              key={b.key}
              href={b.href}
              aria-label={a11y}
              className="relative flex h-full flex-col items-center justify-end rounded-t-[12px] pt-7 transition-colors hover:bg-white/[0.03]"
            >
              {body}
            </Link>
          ) : (
            <div key={b.key} role="img" aria-label={a11y} className="relative flex h-full flex-col items-center justify-end pt-7">
              {body}
            </div>
          );
        })}
      </div>
      <div className="mt-3 grid" style={cols} aria-hidden="true">
        {bars.map((b, i) => (
          <div key={b.key} className="px-0.5 text-center">
            <span className="t-code block text-[10px] text-fg-3">{String(i + 1).padStart(2, "0")}</span>
            <span className="t-foot mt-0.5 block leading-tight text-fg-2">{b.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ───────────────────────────── Lane header ────────────────────────── */

/** Page header for a lane: mono eyebrow, large title, one-line callout, controls. */
export function LaneHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  className,
}: {
  eyebrow: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("flex flex-wrap items-end justify-between gap-x-8 gap-y-5", className)}>
      <div className="min-w-0 max-w-2xl animate-rise">
        <p className="t-label text-fg-3">{eyebrow}</p>
        <h1 className="t-large mt-2 break-words text-fg">{title}</h1>
        {subtitle ? <p className="t-callout mt-2 max-w-xl text-fg-2">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-3 sm:gap-4">{actions}</div> : null}
    </header>
  );
}
