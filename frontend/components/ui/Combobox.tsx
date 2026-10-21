"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { EASE } from "@/components/motion/tokens";
import { FieldShell } from "./Field";
import { Icon, type IconName } from "./Icon";

/**
 * Combobox — searchable single select. A well input that filters a glass
 * listbox as you type (ARIA 1.2 combobox: the input owns
 * `aria-activedescendant`, focus never leaves it).
 *
 * Keyboard: ↓/↑ open and move · Enter picks · Esc closes and restores ·
 * Tab leaves. Closed, the field shows the chosen option's label.
 * `allowCustom` accepts free text ("Use “…”" row, or on blur).
 *
 *   <Combobox label="Port of loading" options={ports} value={port}
 *             onChange={setPort} placeholder="Search ports" />
 */

export interface ComboboxOption {
  value: string;
  label: string;
  /** Mono hint on the right (code, country, unit). */
  hint?: string;
  /** Extra words to match on (synonyms, codes). */
  keywords?: string;
  disabled?: boolean;
}

export interface ComboboxProps {
  options: ReadonlyArray<ComboboxOption>;
  value: string | null | undefined;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  required?: boolean;
  optional?: boolean;
  disabled?: boolean;
  /** Accept text that isn't in the list. */
  allowCustom?: boolean;
  /** Show a clear (×) control when something is chosen. */
  clearable?: boolean;
  /** Glyph at the start of the field. Default: search. Pass null for none. */
  icon?: IconName | null;
  emptyText?: string;
  /** Night glass styling (auth screens). */
  night?: boolean;
  size?: "md" | "lg";
  /** Renders a hidden input so plain <form> posts include the value. */
  name?: string;
  id?: string;
  action?: ReactNode;
  className?: string;
  inputClassName?: string;
}

const MAX_RESULTS = 80;

function normalise(s: string) {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .trim();
}

export function Combobox({
  options,
  value,
  onChange,
  placeholder,
  label,
  hint,
  error,
  required,
  optional,
  disabled,
  allowCustom,
  clearable,
  icon = "search",
  emptyText = "No match.",
  night,
  size = "md",
  name,
  id,
  action,
  className,
  inputClassName,
}: ComboboxProps) {
  const auto = useId();
  const inputId = id ?? `${auto}-input`;
  const listId = `${auto}-list`;
  const optId = (i: number) => `${auto}-opt-${i}`;

  const inputRef = useRef<HTMLInputElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  /** null = not typing; the field shows the chosen label. */
  const [query, setQuery] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [placeUp, setPlaceUp] = useState(false);

  const selected = useMemo(() => options.find((o) => o.value === value) ?? null, [options, value]);
  const selectedLabel = selected?.label ?? (value ? value : "");

  const { items, more } = useMemo(() => {
    const q = query === null ? "" : normalise(query);
    type Row = ComboboxOption & { custom?: boolean };
    let rows: Row[];
    if (!q) {
      rows = options.slice();
    } else {
      const starts: Row[] = [];
      const contains: Row[] = [];
      for (const o of options) {
        const l = normalise(o.label);
        if (l.startsWith(q)) starts.push(o);
        else if (
          l.includes(q) ||
          normalise(o.value).includes(q) ||
          (o.hint && normalise(o.hint).includes(q)) ||
          (o.keywords && normalise(o.keywords).includes(q))
        )
          contains.push(o);
      }
      rows = [...starts, ...contains];
    }
    const total = rows.length;
    rows = rows.slice(0, MAX_RESULTS);
    if (allowCustom && query && q && !options.some((o) => normalise(o.label) === q)) {
      rows.push({ value: query.trim(), label: `Use “${query.trim()}”`, custom: true });
    }
    return { items: rows, more: Math.max(0, total - MAX_RESULTS) };
  }, [options, query, allowCustom]);

  const showList = open && !disabled;
  const activeItem = showList ? items[active] : undefined;

  // Keep the highlighted option in view.
  useEffect(() => {
    if (!showList) return;
    listRef.current
      ?.querySelector<HTMLElement>(`[data-index="${active}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [active, showList]);

  const firstEnabled = (from: number, dir: 1 | -1) => {
    if (!items.length) return 0;
    let i = from;
    for (let n = 0; n < items.length; n++) {
      i = (i + items.length) % items.length;
      if (!items[i].disabled) return i;
      i += dir;
    }
    return from;
  };

  const openList = () => {
    if (disabled) return;
    const rect = wrapRef.current?.getBoundingClientRect();
    if (rect) {
      // Leave room for the dock on phones; open upward when cramped below.
      const below = window.innerHeight - rect.bottom - 96;
      setPlaceUp(below < 260 && rect.top > below);
    }
    const idx = selected ? items.findIndex((o) => o.value === selected.value) : -1;
    setActive(firstEnabled(idx >= 0 ? idx : 0, 1));
    setOpen(true);
  };

  const close = () => {
    setOpen(false);
    setQuery(null);
  };

  const pick = (o: ComboboxOption & { custom?: boolean }) => {
    if (o.disabled) return;
    onChange(o.value);
    close();
  };

  const commitOnBlur = () => {
    if (query !== null) {
      const q = normalise(query);
      const exact = q ? options.find((o) => !o.disabled && normalise(o.label) === q) : undefined;
      if (exact) {
        if (exact.value !== value) onChange(exact.value);
      } else if (allowCustom && query.trim() && query.trim() !== value) {
        onChange(query.trim());
      }
    }
    close();
  };

  const move = (dir: 1 | -1) => {
    if (!showList) {
      openList();
      return;
    }
    setActive((i) => firstEnabled(i + dir, dir));
  };

  const h = size === "lg" ? "h-[52px]" : "h-12";
  const hasClear = clearable && !!value && !disabled;

  return (
    <FieldShell
      label={label}
      hint={hint}
      error={error}
      optional={optional}
      required={required}
      night={night}
      htmlFor={inputId}
      className={className}
      action={action}
    >
      <div ref={wrapRef} className="relative">
        {icon ? (
          <span
            className={cn(
              "pointer-events-none absolute left-4 top-1/2 -translate-y-1/2",
              night ? "text-cream/50" : "text-fg-3",
            )}
          >
            <Icon name={icon} size={16} />
          </span>
        ) : null}
        <input
          ref={inputRef}
          id={inputId}
          type="text"
          role="combobox"
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={activeItem ? optId(active) : undefined}
          aria-invalid={error ? true : undefined}
          aria-required={required || undefined}
          disabled={disabled}
          placeholder={placeholder}
          value={query ?? selectedLabel}
          onFocus={() => {
            // Select the shown label so typing replaces it.
            inputRef.current?.select();
          }}
          onClick={() => (showList ? undefined : openList())}
          onBlur={commitOnBlur}
          onChange={(e) => {
            if (!open) openList();
            setQuery(e.target.value);
            setActive(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              move(1);
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              move(-1);
            } else if (e.key === "Enter") {
              if (showList) {
                // Never submit the surrounding form while choosing.
                e.preventDefault();
                if (activeItem) pick(activeItem);
              }
            } else if (e.key === "Escape") {
              if (showList || query !== null) {
                e.preventDefault();
                e.stopPropagation();
                close();
              }
            }
          }}
          className={cn(
            night ? "field-night" : "field",
            h,
            "px-4 text-[15px]",
            icon ? "pl-11" : undefined,
            hasClear ? "pr-[84px]" : "pr-11",
            inputClassName,
          )}
        />
        <span className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center">
          {hasClear ? (
            <button
              type="button"
              aria-label="Clear"
              title="Clear"
              tabIndex={-1}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                onChange("");
                setQuery(null);
                inputRef.current?.focus();
              }}
              className={cn(
                "grid size-8 place-items-center rounded-full transition-colors duration-300 ease-expo",
                night ? "text-cream/55 hover:bg-white/[0.07] hover:text-cream" : "text-fg-3 hover:bg-fg/5 hover:text-fg",
              )}
            >
              <Icon name="close" size={15} />
            </button>
          ) : null}
          <span
            aria-hidden="true"
            className={cn("pointer-events-none grid size-8 place-items-center", night ? "text-cream/50" : "text-fg-3")}
          >
            <Icon name="chevron-down" size={16} />
          </span>
        </span>

        <AnimatePresence>
          {showList ? (
            <motion.ul
              ref={listRef}
              id={listId}
              role="listbox"
              aria-label={typeof label === "string" ? label : undefined}
              initial={{ opacity: 0, y: placeUp ? 4 : -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, transition: { duration: 0.15 } }}
              transition={{ duration: 0.3, ease: EASE }}
              // Keep focus in the input so blur doesn't fire before a pick.
              onMouseDown={(e) => e.preventDefault()}
              className={cn(
                "absolute inset-x-0 z-30 max-h-[min(18rem,50vh)] overflow-y-auto overscroll-contain rounded-[20px] p-1.5",
                placeUp ? "bottom-[calc(100%+8px)]" : "top-[calc(100%+8px)]",
                night ? "glass-night" : "glass",
              )}
            >
              {items.length === 0 ? (
                <li className={cn("t-sub px-3 py-2.5", night ? "text-cream/55" : "text-fg-3")}>{emptyText}</li>
              ) : (
                items.map((o, i) => {
                  const isActive = i === active;
                  const isChosen = !o.custom && o.value === value;
                  return (
                    <li
                      key={`${o.custom ? "custom" : "opt"}-${o.value}`}
                      id={optId(i)}
                      data-index={i}
                      role="option"
                      aria-selected={isActive}
                      aria-disabled={o.disabled || undefined}
                      onMouseMove={() => !o.disabled && i !== active && setActive(i)}
                      onClick={() => pick(o)}
                      className={cn(
                        "flex min-h-10 cursor-pointer items-center gap-3 rounded-[14px] px-3 py-2 text-[14px] transition-colors duration-150",
                        night
                          ? isActive
                            ? "bg-white/[0.08] text-cream"
                            : "text-cream/75"
                          : isActive
                            ? "bg-fg/[0.06] text-fg"
                            : "text-fg-2",
                        o.custom && "font-medium",
                        o.disabled && "cursor-not-allowed opacity-45",
                      )}
                    >
                      {o.custom ? <Icon name="plus" size={15} className="shrink-0" /> : null}
                      <span className="min-w-0 flex-1 truncate">{o.label}</span>
                      {o.hint ? (
                        <span className={cn("t-code shrink-0", night ? "text-cream/45" : "text-fg-3")}>{o.hint}</span>
                      ) : null}
                      {isChosen ? (
                        <Icon name="check" size={15} strokeWidth={2} className={cn("shrink-0", night ? "text-lime" : "text-accent")} />
                      ) : null}
                    </li>
                  );
                })
              )}
              {more > 0 ? (
                <li className={cn("t-foot px-3 pb-1.5 pt-2", night ? "text-cream/45" : "text-fg-3")} aria-hidden="true">
                  {more} more — keep typing to narrow
                </li>
              ) : null}
            </motion.ul>
          ) : null}
        </AnimatePresence>
      </div>
      {name ? <input type="hidden" name={name} value={value ?? ""} /> : null}
    </FieldShell>
  );
}
