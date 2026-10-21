"use client";

import { motion, useReducedMotion } from "framer-motion";
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { cn } from "@/lib/cn";
import { Icon, type IconName } from "./Icon";

/* ───────────────────────────── Segmented ─────────────────────────────
   A well track with a raised relief thumb that slides to the selection.
   Used for filters, view switches and the mode switch. */

export interface SegmentOption<T extends string> {
  value: T;
  label: ReactNode;
  icon?: IconName;
  count?: number;
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  size = "md",
  className,
}: {
  value: T;
  onChange: (v: T) => void;
  options: ReadonlyArray<SegmentOption<T>>;
  label: string;
  size?: "sm" | "md";
  className?: string;
}) {
  const id = useId();
  const reduce = useReducedMotion();
  return (
    <div role="radiogroup" aria-label={label} className={cn("well no-scrollbar inline-flex max-w-full overflow-x-auto rounded-full p-1", className)}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={cn(
              "relative inline-flex shrink-0 items-center gap-1.5 rounded-full font-medium transition-colors duration-300",
              size === "md" ? "h-9 px-4 text-[14px]" : "h-8 px-3 text-[13px]",
              active ? "text-fg" : "text-fg-3 hover:text-fg-2",
            )}
          >
            {active ? (
              <motion.span
                layoutId={`seg-${id}`}
                className="relief-sm absolute inset-0 rounded-full"
                transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 36 }}
              />
            ) : null}
            <span className="relative inline-flex items-center gap-1.5">
              {o.icon ? <Icon name={o.icon} size={15} /> : null}
              {o.label}
              {typeof o.count === "number" ? (
                <span className="t-code text-fg-3">· {o.count}</span>
              ) : null}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/* ───────────────────────────── Progress ─────────────────────────────
   A sunk track with a lime fill. Lime = certainty gained. */

export function Progress({
  value,
  max = 100,
  className,
  label,
}: {
  value: number;
  max?: number;
  className?: string;
  label?: string;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      className={cn("well h-2 overflow-hidden rounded-full", className)}
    >
      <div
        className="h-full rounded-full bg-lime transition-[width] duration-700 ease-expo"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

/* ───────────────────────────── Corridor rail ─────────────────────────
   Behind you is solid, where you are is lime, ahead is a quiet well. */

export interface RailStep {
  key: string;
  label: ReactNode;
  state: "done" | "current" | "todo" | "blocked";
}

export function Rail({ steps, className }: { steps: ReadonlyArray<RailStep>; className?: string }) {
  return (
    <ol className={cn("flex w-full items-start", className)}>
      {steps.map((s, i) => {
        const last = i === steps.length - 1;
        return (
          <li key={s.key} className={cn("relative flex min-w-0 flex-1 flex-col items-start", last && "flex-none")}>
            <div className="flex w-full items-center">
              <span
                className={cn(
                  "t-code relative z-10 grid size-7 shrink-0 place-items-center rounded-full text-[11px]",
                  s.state === "done" && "solid",
                  s.state === "current" && "bg-lime text-ink shadow-[0_0_0_5px_rgb(196_216_46/0.22)]",
                  s.state === "todo" && "well text-fg-3",
                  s.state === "blocked" && "bg-danger-soft text-danger",
                )}
                aria-current={s.state === "current" ? "step" : undefined}
              >
                {s.state === "done" ? (
                  <Icon name="check" size={13} strokeWidth={2} />
                ) : s.state === "blocked" ? (
                  <Icon name="alert" size={13} />
                ) : (
                  i + 1
                )}
              </span>
              {!last ? (
                <span
                  className={cn(
                    "mx-1.5 h-[3px] flex-1 rounded-full",
                    s.state === "done" ? "bg-ink [[data-surface=tower]_&]:bg-[#edefea]" : "well",
                  )}
                />
              ) : null}
            </div>
            <span
              className={cn(
                "t-sub mt-2.5 pr-3",
                s.state === "current" ? "font-medium text-fg" : s.state === "done" ? "text-fg-2" : "text-fg-3",
              )}
            >
              {s.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/* ───────────────────────────── Hold to commit ────────────────────────
   Replaces every "are you sure?". Press and hold; letting go early
   rewinds. Keyboard: hold Space/Enter.
   Sizes match Button: sm 36px · md 44px · lg 52px (default). */

const HOLD_SIZES = {
  sm: { cls: "h-9 gap-1.5 rounded-[12px] px-3.5 text-[13px]", icon: 15 },
  md: { cls: "h-11 gap-2 rounded-control px-5 text-[14px]", icon: 16 },
  lg: { cls: "h-[52px] gap-2 rounded-field px-6 text-[15px]", icon: 18 },
} as const;

export function HoldButton({
  onCommit,
  children,
  holdMs = 1200,
  disabled,
  loading,
  icon = "check",
  tone = "commit",
  size = "lg",
  block,
  className,
}: {
  onCommit: () => void | Promise<void>;
  children: ReactNode;
  holdMs?: number;
  disabled?: boolean;
  loading?: boolean;
  icon?: IconName;
  tone?: "commit" | "danger" | "primary";
  size?: "sm" | "md" | "lg";
  /** Full width. */
  block?: boolean;
  className?: string;
}) {
  const sz = HOLD_SIZES[size];
  const [progress, setProgress] = useState(0);
  const raf = useRef<number | null>(null);
  const start = useRef<number | null>(null);
  const fired = useRef(false);

  const stop = useCallback(() => {
    if (raf.current) cancelAnimationFrame(raf.current);
    raf.current = null;
    start.current = null;
    if (!fired.current) setProgress(0);
  }, []);

  const tick = useCallback(
    (t: number) => {
      if (start.current == null) start.current = t;
      const p = Math.min(1, (t - start.current) / holdMs);
      setProgress(p);
      if (p >= 1) {
        fired.current = true;
        raf.current = null;
        void Promise.resolve(onCommit()).finally(() => {
          fired.current = false;
          setProgress(0);
        });
        return;
      }
      raf.current = requestAnimationFrame(tick);
    },
    [holdMs, onCommit],
  );

  const begin = useCallback(() => {
    if (disabled || loading || raf.current) return;
    fired.current = false;
    raf.current = requestAnimationFrame(tick);
  }, [disabled, loading, tick]);

  useEffect(() => () => stop(), [stop]);

  const toneCls =
    tone === "commit"
      ? "bg-lime text-ink shadow-[0_14px_30px_-14px_rgb(120_140_10/0.7),inset_0_1px_0_rgb(255_255_255/0.45)]"
      : tone === "danger"
        ? "bg-danger-soft text-danger"
        : "solid";
  const fillCls =
    tone === "commit" ? "bg-ink/15" : tone === "danger" ? "bg-danger/20" : "bg-lime/30";

  return (
    <button
      type="button"
      disabled={disabled || loading}
      onPointerDown={begin}
      onPointerUp={stop}
      onPointerLeave={stop}
      onPointerCancel={stop}
      onKeyDown={(e) => {
        if ((e.key === " " || e.key === "Enter") && !e.repeat) {
          e.preventDefault();
          begin();
        }
      }}
      onKeyUp={(e) => {
        if (e.key === " " || e.key === "Enter") stop();
      }}
      onContextMenu={(e) => e.preventDefault()}
      aria-label={typeof children === "string" ? `${children} — press and hold` : undefined}
      className={cn(
        "relative inline-flex select-none items-center justify-center overflow-hidden font-medium tracking-[-0.01em]",
        "touch-none transition-[opacity,transform] duration-300 ease-expo disabled:pointer-events-none disabled:opacity-45",
        sz.cls,
        block && "w-full",
        toneCls,
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn("absolute inset-y-0 left-0", fillCls)}
        style={{ width: `${progress * 100}%` }}
      />
      <span className={cn("relative inline-flex items-center", size === "sm" ? "gap-1.5" : "gap-2")}>
        {loading ? (
          <svg width={sz.icon} height={sz.icon} viewBox="0 0 24 24" className="animate-spin" aria-hidden="true">
            <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity=".25" strokeWidth="2" />
            <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        ) : (
          <Icon name={icon} size={sz.icon} />
        )}
        {children}
        <span className={cn("t-label opacity-60", size === "sm" ? "ml-0.5 text-[10px]" : "ml-1")}>
          {progress > 0 ? "Keep holding" : "Hold"}
        </span>
      </span>
    </button>
  );
}

/* ───────────────────────────── Toggle / checkbox ───────────────────── */

export function Checkbox({
  checked,
  onChange,
  label,
  description,
  className,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: ReactNode;
  description?: ReactNode;
  className?: string;
}) {
  const id = useId();
  return (
    <label htmlFor={id} className={cn("flex cursor-pointer items-start gap-3", className)}>
      <span className="relative mt-0.5 shrink-0">
        <input
          id={id}
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="peer sr-only"
        />
        <span
          className={cn(
            "grid size-5 place-items-center rounded-[6px] transition-colors duration-200 peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[var(--focus)]",
            checked ? "solid" : "well",
          )}
        >
          {checked ? <Icon name="check" size={13} strokeWidth={2.2} /> : null}
        </span>
      </span>
      <span className="min-w-0">
        <span className="t-callout block text-fg">{label}</span>
        {description ? <span className="t-sub mt-0.5 block text-fg-3">{description}</span> : null}
      </span>
    </label>
  );
}

/** Multi-select chip group (e.g. markets, buyer types). */
export function ChoiceChips<T extends string>({
  options,
  value,
  onChange,
  label,
  className,
}: {
  options: ReadonlyArray<{ value: T; label: ReactNode }>;
  value: ReadonlyArray<T>;
  onChange: (v: T[]) => void;
  label: string;
  className?: string;
}) {
  const toggle = (v: T) =>
    onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  return (
    <div role="group" aria-label={label} className={cn("flex flex-wrap gap-2", className)}>
      {options.map((o) => {
        const on = value.includes(o.value);
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={on}
            onClick={() => toggle(o.value)}
            className={cn(
              "inline-flex h-9 items-center gap-1.5 rounded-full px-3.5 text-[13px] font-medium transition-[box-shadow,background-color,color] duration-300 ease-expo",
              on ? "solid" : "relief-sm text-fg-2 hover:text-fg",
            )}
          >
            {on ? <Icon name="check" size={13} strokeWidth={2} /> : null}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
