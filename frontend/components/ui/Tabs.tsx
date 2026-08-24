"use client";

import { KeyboardEvent, ReactNode, useId, useRef } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/cn";

export interface TabItem<T extends string> {
  value: T;
  label: string;
  icon?: ReactNode;
}

/**
 * Two-way tab switcher with a sliding chartreuse pill.
 * Uses framer-motion's `layoutId` — the pill fluidly moves between tabs
 * on selection, giving a "physical" feel instead of a hard swap.
 */
export function Tabs<T extends string>({
  items,
  value,
  onChange,
  className,
  ariaLabel,
}: {
  items: TabItem<T>[];
  value: T;
  onChange: (next: T) => void;
  className?: string;
  ariaLabel: string;
}) {
  const listRef = useRef<HTMLDivElement>(null);
  const layoutId = useId();

  const handleKey = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const dir = e.key === "ArrowRight" ? 1 : -1;
    const next = (index + dir + items.length) % items.length;
    onChange(items[next].value);
    const btns = listRef.current?.querySelectorAll<HTMLButtonElement>("[role=tab]");
    btns?.[next]?.focus();
  };

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label={ariaLabel}
      className={cn(
        "relative grid grid-cols-2 gap-1 rounded-[14px] border border-line-soft bg-ink-soft/60 p-1 backdrop-blur-sm",
        className,
      )}
    >
      {items.map((it, i) => {
        const active = it.value === value;
        return (
          <button
            key={it.value}
            role="tab"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            data-active={active}
            className="tab"
            onClick={() => onChange(it.value)}
            onKeyDown={(e) => handleKey(e, i)}
            type="button"
          >
            {active && (
              <motion.span
                layoutId={`tab-pill-${layoutId}`}
                className="absolute inset-0 rounded-[10px] bg-accent"
                style={{ zIndex: 0 }}
                transition={{ type: "spring", stiffness: 380, damping: 32 }}
              />
            )}
            <span className="relative z-10 inline-flex items-center gap-2">
              {it.icon}
              {it.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
