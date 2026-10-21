"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/cn";
import { EASE } from "@/components/motion/tokens";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Kbd } from "@/components/ui/Kbd";

/**
 * Command palette — "Search or jump to…" (reference: portal /corridor,
 * ⌘K). A glass panel over a light ink scrim: one search field, results in
 * mono-labelled groups, the active row in a soft fill.
 *
 * Keyboard: ↑/↓ (and Home/End) move, Enter runs, Esc closes. Focus stays
 * in the search field (ARIA 1.2 combobox + listbox with groups) and goes
 * back to whatever opened the palette when it closes.
 */

export interface Command {
  id: string;
  group: string;
  label: string;
  /** Right-aligned note (mono hint, state). */
  hint?: ReactNode;
  /** Extra words the search should match. */
  keywords?: string;
  icon?: IconName;
  /** A thumbnail in place of the icon (commodity photo). */
  thumb?: ReactNode;
  /** Amber — this one is your move. */
  move?: boolean;
  run: () => void;
}

function matches(c: Command, q: string): boolean {
  if (!q) return true;
  const hay = `${c.label} ${c.group} ${c.keywords ?? ""}`.toLowerCase();
  return q
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((w) => hay.includes(w));
}

export function CommandPalette({
  open,
  onClose,
  commands,
}: {
  open: boolean;
  onClose: () => void;
  commands: ReadonlyArray<Command>;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;
  return createPortal(
    <AnimatePresence>{open ? <Panel key="palette" onClose={onClose} commands={commands} /> : null}</AnimatePresence>,
    document.body,
  );
}

function Panel({ onClose, commands }: { onClose: () => void; commands: ReadonlyArray<Command> }) {
  const reduce = useReducedMotion();
  const auto = useId();
  const listId = `${auto}-list`;
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  const results = useMemo(() => commands.filter((c) => matches(c, query.trim())), [commands, query]);

  // Groups in first-seen order; `index` is the row's place in `results`.
  const groups = useMemo(() => {
    const out: Array<{ name: string; rows: Array<{ c: Command; index: number }> }> = [];
    results.forEach((c, index) => {
      let g = out.find((x) => x.name === c.group);
      if (!g) out.push((g = { name: c.group, rows: [] }));
      g.rows.push({ c, index });
    });
    return out;
  }, [results]);

  useEffect(() => setActive(0), [query]);

  // Lock the page behind, focus the field, give focus back on close —
  // unless a command ran: then the destination (a field, a page) owns focus.
  const ran = useRef(false);
  useEffect(() => {
    const last = document.activeElement as HTMLElement | null;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const t = window.setTimeout(() => inputRef.current?.focus(), 20);
    return () => {
      window.clearTimeout(t);
      document.body.style.overflow = prev;
      if (!ran.current) last?.focus?.({ preventScroll: true });
    };
  }, []);

  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const run = (c: Command | undefined) => {
    if (!c) return;
    ran.current = true;
    onClose();
    // Let the palette start leaving before navigation repaints the page.
    window.setTimeout(() => c.run(), 0);
  };

  const onKeyDown = (e: KeyboardEvent) => {
    const n = results.length;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (n) setActive((i) => (i + 1) % n);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (n) setActive((i) => (i - 1 + n) % n);
    } else if (e.key === "Home" && n) {
      e.preventDefault();
      setActive(0);
    } else if (e.key === "End" && n) {
      e.preventDefault();
      setActive(n - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      run(results[active]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      onClose();
    } else if (e.key === "Tab") {
      // Focus stays in the field; arrows move through results.
      e.preventDefault();
    }
  };

  const activeId = results[active] ? `${auto}-opt-${active}` : undefined;

  return (
    <div className="fixed inset-0 z-[80]" data-surface="trader">
      <motion.div
        aria-hidden="true"
        className="absolute inset-0 bg-ink/20"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.25 }}
        onClick={onClose}
      />
      <div className="pointer-events-none absolute inset-x-0 top-[12vh] flex justify-center px-3">
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-label="Command menu"
          initial={reduce ? { opacity: 0 } : { opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduce ? { opacity: 0 } : { opacity: 0, y: -6 }}
          transition={{ duration: 0.4, ease: EASE }}
          className="glass pointer-events-auto w-full max-w-[640px] overflow-hidden rounded-[26px] text-fg"
          onKeyDown={onKeyDown}
        >
          <div className="flex items-center gap-3 border-b border-line px-5">
            <Icon name="search" size={18} className="shrink-0 text-fg-3" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Type a page, a passport field or a commodity…"
              aria-label="Search or jump to"
              role="combobox"
              aria-expanded="true"
              aria-controls={listId}
              aria-autocomplete="list"
              aria-activedescendant={activeId}
              autoComplete="off"
              spellCheck={false}
              className="h-14 min-w-0 flex-1 bg-transparent text-[16px] outline-none placeholder:text-fg-3 focus-visible:outline-none"
            />
            <button type="button" onClick={onClose} className="shrink-0 rounded-[8px]" aria-label="Close">
              <Kbd>esc</Kbd>
            </button>
          </div>

          <div
            ref={listRef}
            id={listId}
            role="listbox"
            aria-label="Results"
            className="max-h-[56vh] overflow-y-auto overscroll-contain p-2"
          >
            {results.length === 0 ? (
              <p className="t-callout px-3 py-8 text-center text-fg-3">
                Nothing matches &ldquo;{query.trim()}&rdquo;. Try &ldquo;passport&rdquo; or &ldquo;rice&rdquo;.
              </p>
            ) : (
              groups.map((g) => {
                const headId = `${auto}-g-${g.name.replace(/\W+/g, "-")}`;
                return (
                  <div key={g.name} role="group" aria-labelledby={headId} className="px-1">
                    <p id={headId} className="t-label px-3 pb-1.5 pt-3 text-fg-3">
                      {g.name}
                    </p>
                    {g.rows.map(({ c, index }) => {
                      const on = index === active;
                      return (
                          <div
                            key={c.id}
                            id={`${auto}-opt-${index}`}
                            data-index={index}
                            role="option"
                            aria-selected={on}
                            onMouseDown={(e) => e.preventDefault()}
                            onMouseMove={() => !on && setActive(index)}
                            onClick={() => run(c)}
                            className={cn(
                              "t-callout flex cursor-pointer items-center gap-3 rounded-[14px] px-3 py-2.5 transition-colors duration-150",
                              on ? "bg-fg/[0.06] text-fg" : "text-fg-2",
                            )}
                          >
                            {c.thumb ? (
                              <span className="shrink-0">{c.thumb}</span>
                            ) : (
                              <Icon
                                name={c.icon ?? "arrow-right"}
                                size={17}
                                className={cn("shrink-0", c.move ? "text-amber" : on ? "text-fg" : "text-fg-3")}
                              />
                            )}
                            <span className="min-w-0 flex-1 truncate">{c.label}</span>
                            {c.hint ? <span className="t-foot ml-auto shrink-0 text-fg-3">{c.hint}</span> : null}
                            {on ? <Icon name="arrow-right" size={14} className="shrink-0 text-fg-3" /> : null}
                          </div>
                      );
                    })}
                  </div>
                );
              })
            )}
          </div>

          <div className="hidden items-center gap-4 border-t border-line px-5 py-2.5 sm:flex" aria-hidden="true">
            <span className="t-foot flex items-center gap-1.5 text-fg-3">
              <Kbd size="sm">↑</Kbd>
              <Kbd size="sm">↓</Kbd> move
            </span>
            <span className="t-foot flex items-center gap-1.5 text-fg-3">
              <Kbd size="sm">↵</Kbd> open
            </span>
            <span className="t-foot flex items-center gap-1.5 text-fg-3">
              <Kbd size="sm">esc</Kbd> close
            </span>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
