"use client";

import { KeyboardEvent, ReactNode, useRef } from "react";
import { cn } from "@/lib/cn";

export interface TabItem<T extends string> {
  value: T;
  label: string;
  icon?: ReactNode;
}

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
        "grid grid-cols-2 gap-1 rounded-[14px] bg-paper-muted p-1 ring-1 ring-line-soft",
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
            {it.icon}
            <span>{it.label}</span>
          </button>
        );
      })}
    </div>
  );
}
