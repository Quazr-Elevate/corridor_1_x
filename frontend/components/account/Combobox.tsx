"use client";

import { useId, useMemo, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Input } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";

/**
 * Searchable pick-one list on a well input with a glass listbox — the
 * search-and-pick pattern shared by the certificate type picker and the
 * country pickers. Picking calls `onPick` and clears the query; the parent
 * owns what was picked.
 *
 * Keyboard: ↑/↓ move, Enter picks, Esc closes. Follows the ARIA 1.2
 * combobox pattern (input owns `aria-activedescendant`).
 */
export interface ComboOption {
  value: string;
  label: string;
  hint?: string;
}

export function Combobox({
  id,
  label,
  hint,
  error,
  required,
  optional,
  action,
  options,
  onPick,
  placeholder,
  allowCustom,
  emptyText = "No match.",
  disabled,
  className,
}: {
  id?: string;
  label?: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  required?: boolean;
  optional?: boolean;
  action?: ReactNode;
  options: ReadonlyArray<ComboOption>;
  onPick: (value: string) => void;
  placeholder?: string;
  /** Offer “Use "<query>"” when nothing matches exactly. */
  allowCustom?: boolean;
  emptyText?: string;
  disabled?: boolean;
  className?: string;
}) {
  const auto = useId();
  const listId = `${auto}-list`;
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matches = q
      ? options.filter(
          (o) => o.label.toLowerCase().includes(q) || o.value.toLowerCase().includes(q) || o.hint?.toLowerCase().includes(q),
        )
      : options.slice();
    const exact = matches.some((o) => o.label.toLowerCase() === q);
    const out: Array<ComboOption & { custom?: boolean }> = matches.slice(0, 60);
    if (allowCustom && q && !exact) {
      out.push({ value: query.trim(), label: `Use “${query.trim()}”`, custom: true });
    }
    return out;
  }, [options, query, allowCustom]);

  const pick = (value: string) => {
    onPick(value);
    setQuery("");
    setActive(0);
    setOpen(false);
  };

  const move = (delta: number) => {
    if (!items.length) return;
    setOpen(true);
    setActive((i) => {
      const next = (i + delta + items.length) % items.length;
      listRef.current?.querySelector<HTMLElement>(`[data-index="${next}"]`)?.scrollIntoView({ block: "nearest" });
      return next;
    });
  };

  const showList = open && !disabled;
  const activeId = showList && items[active] ? `${auto}-opt-${active}` : undefined;

  return (
    <div className={cn("relative", className)}>
      <Input
        id={id}
        label={label}
        hint={hint}
        error={error}
        required={required}
        optional={optional}
        action={action}
        disabled={disabled}
        value={query}
        placeholder={placeholder}
        autoComplete="off"
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={activeId}
        leading={<Icon name="search" size={16} />}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
          setOpen(true);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            move(1);
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            move(-1);
          } else if (e.key === "Enter") {
            // Never submit the surrounding form from the search box.
            e.preventDefault();
            if (showList && items[active]) pick(items[active].value);
          } else if (e.key === "Escape") {
            if (showList) {
              e.stopPropagation();
              setOpen(false);
            }
          }
        }}
      />
      {showList ? (
        <ul
          ref={listRef}
          id={listId}
          role="listbox"
          className="glass absolute inset-x-0 z-30 mt-2 max-h-64 overflow-y-auto rounded-[20px] p-1.5"
        >
          {items.length === 0 ? (
            <li className="t-sub px-3 py-2.5 text-fg-3">{emptyText}</li>
          ) : (
            items.map((o, i) => (
              <li
                key={`${o.value}-${o.custom ? "custom" : "opt"}`}
                id={`${auto}-opt-${i}`}
                data-index={i}
                role="option"
                aria-selected={i === active}
                // Keep focus in the input so blur doesn't close before click.
                onMouseDown={(e) => e.preventDefault()}
                onMouseEnter={() => setActive(i)}
                onClick={() => pick(o.value)}
                className={cn(
                  "flex cursor-pointer items-center justify-between gap-3 rounded-[14px] px-3 py-2.5 text-[14px] transition-colors",
                  i === active ? "bg-fg/[0.06] text-fg" : "text-fg-2",
                  o.custom && "font-medium text-fg",
                )}
              >
                <span className="min-w-0 truncate">{o.label}</span>
                {o.hint ? <span className="t-code shrink-0 text-fg-3">{o.hint}</span> : null}
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
