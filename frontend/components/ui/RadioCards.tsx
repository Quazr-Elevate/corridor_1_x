"use client";

import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Icon, type IconName } from "./Icon";

/**
 * RadioCards — pick one of a few big choices (role, trade side, plan).
 * Unselected cards are relief you can touch; the chosen one turns solid,
 * its icon disc lime. A real radiogroup: one tab stop, arrow keys move
 * and select, Home/End jump, Space/Enter select.
 *
 * On phones (size "md") cards collapse to compact rows; from `sm` up they
 * stand as tall tiles.
 *
 *   <RadioCards label="What do you do in this corridor?" value={role}
 *     onChange={setRole} options={[
 *       { value: "producer", label: "Producer", icon: "grain", description: "…" },
 *       { value: "exporter", label: "Exporter", icon: "ship", description: "…" },
 *     ]} />
 */

export interface RadioCardOption<T extends string> {
  value: T;
  label: ReactNode;
  description?: ReactNode;
  icon?: IconName;
  /** Small mono tag top-right (e.g. "Phase 2"). */
  meta?: ReactNode;
  disabled?: boolean;
}

const COLS = {
  1: "grid-cols-1",
  2: "grid-cols-1 sm:grid-cols-2",
  3: "grid-cols-1 sm:grid-cols-3",
  4: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4",
} as const;

export function RadioCards<T extends string>({
  options,
  value,
  onChange,
  label,
  columns = 3,
  size = "md",
  className,
}: {
  options: ReadonlyArray<RadioCardOption<T>>;
  value: T | null | undefined;
  onChange: (v: T) => void;
  /** Accessible name of the group. */
  label: string;
  columns?: 1 | 2 | 3 | 4;
  /** `sm`: compact rows everywhere. `md`: rows on phones, tiles from sm. */
  size?: "sm" | "md";
  className?: string;
}) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedIndex = options.findIndex((o) => o.value === value);
  const firstEnabled = options.findIndex((o) => !o.disabled);
  const tabStop = selectedIndex >= 0 && !options[selectedIndex].disabled ? selectedIndex : firstEnabled;

  const step = (from: number, dir: 1 | -1) => {
    const n = options.length;
    for (let k = 1; k <= n; k++) {
      const i = (from + dir * k + n * k) % n;
      if (!options[i].disabled) return i;
    }
    return from;
  };

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
    let next: number | null = null;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") next = step(i, 1);
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") next = step(i, -1);
    else if (e.key === "Home") next = firstEnabled;
    else if (e.key === "End") {
      for (let j = options.length - 1; j >= 0; j--) {
        if (!options[j].disabled) {
          next = j;
          break;
        }
      }
    }
    if (next === null || next < 0) return;
    e.preventDefault();
    onChange(options[next].value);
    refs.current[next]?.focus();
  };

  const tall = size === "md";

  return (
    <div role="radiogroup" aria-label={label} className={cn("grid gap-3 sm:gap-4", COLS[columns], className)}>
      {options.map((o, i) => {
        const on = i === selectedIndex;
        return (
          <button
            key={o.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={on}
            aria-disabled={o.disabled || undefined}
            disabled={o.disabled}
            tabIndex={i === tabStop ? 0 : -1}
            onClick={() => !o.disabled && onChange(o.value)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={cn(
              "group/rc relative flex min-w-0 items-center gap-4 rounded-[22px] p-4 text-left",
              "transition-[box-shadow,background-color,color,transform] duration-500 ease-expo",
              tall && "sm:min-h-[200px] sm:flex-col sm:items-start sm:gap-0 sm:rounded-card sm:p-6",
              on ? "solid" : "relief text-fg hover:-translate-y-0.5 hover:shadow-[var(--relief-hover)]",
              o.disabled && "cursor-not-allowed opacity-45 hover:translate-y-0",
            )}
          >
            {o.icon ? (
              <span
                className={cn(
                  "grid size-11 shrink-0 place-items-center rounded-full transition-[background-color,color,box-shadow] duration-500 ease-expo",
                  tall && "sm:size-12",
                  on
                    ? "bg-lime text-ink [[data-surface=tower]_&]:bg-ink [[data-surface=tower]_&]:text-lime"
                    : "well text-fg-2 group-hover/rc:text-fg",
                )}
              >
                <Icon name={o.icon} size={21} />
              </span>
            ) : null}
            <span className={cn("flex min-w-0 flex-1 flex-col", tall && "sm:mt-auto sm:w-full sm:flex-none sm:pt-6")}>
              <span className="t-headline sm:t-title3 block">{o.label}</span>
              {o.description ? (
                <span
                  className={cn(
                    "t-sub mt-1 block",
                    on ? "text-cream/65 [[data-surface=tower]_&]:text-ink/60" : "text-fg-3",
                  )}
                >
                  {o.description}
                </span>
              ) : null}
            </span>
            {o.meta ? (
              <span
                className={cn(
                  "t-label shrink-0",
                  tall && "sm:absolute sm:right-6 sm:top-6",
                  on ? "text-cream/60 [[data-surface=tower]_&]:text-ink/55" : "text-fg-3",
                )}
              >
                {o.meta}
              </span>
            ) : null}
            {!o.icon ? (
              <span
                aria-hidden="true"
                className={cn(
                  "grid size-5 shrink-0 place-items-center rounded-full",
                  tall && "sm:absolute sm:right-6 sm:top-6",
                  on ? "bg-lime text-ink" : "shadow-[inset_0_0_0_1.5px_var(--c-line-2)]",
                  o.meta && tall && "sm:hidden",
                )}
              >
                {on ? <Icon name="check" size={12} strokeWidth={2.2} /> : null}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
