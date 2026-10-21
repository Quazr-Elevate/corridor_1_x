"use client";

import { motion, useReducedMotion } from "framer-motion";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { EASE } from "@/components/motion/tokens";
import { cn } from "@/lib/cn";

/**
 * Sentence Composer — the style guide's "Tap a word" gesture.
 *
 *   I'm selling [500 MT] of [Rice] — [1121 Basmati] …
 *
 * Every underlined word is a real <button> (aria-haspopup="dialog") that
 * opens a small glass editor under it: a stepper for numbers, a field for
 * text, a radio list for choices. One editor is open at a time.
 *
 * Keyboard: Enter/Space open · Esc closes and returns to the word ·
 * Tab past the end of an editor moves on to the next word · ↑/↓ move
 * through a choice list. Editors write straight to the form's state, so
 * there is no separate "apply" step — Done just closes.
 *
 *   <ComposerSurface openKey={k} onOpenChange={setK}>
 *     <p>I'm selling <Token tokenKey="qty" label="Volume" value="500 MT">
 *       {(close) => <NumberEditor … onDone={close} />}
 *     </Token> of …</p>
 *   </ComposerSurface>
 */

interface ComposerCtx {
  openKey: string | null;
  setOpenKey: (k: string | null) => void;
  container: RefObject<HTMLDivElement>;
  layer: HTMLDivElement | null;
}

const Ctx = createContext<ComposerCtx | null>(null);

export function ComposerSurface({
  openKey,
  onOpenChange,
  className,
  children,
}: {
  openKey: string | null;
  onOpenChange: (k: string | null) => void;
  className?: string;
  children: ReactNode;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [layer, setLayer] = useState<HTMLDivElement | null>(null);
  const value = useMemo(
    () => ({ openKey, setOpenKey: onOpenChange, container, layer }),
    [openKey, onOpenChange, layer],
  );
  return (
    <Ctx.Provider value={value}>
      <div ref={container} className={cn("relative", className)}>
        {children}
        {/* Editors render here — outside the sentence's <p>, inside the form. */}
        <div ref={setLayer} className="absolute inset-x-0 top-0" />
      </div>
    </Ctx.Provider>
  );
}

/** The sentence itself: large, quiet text with the words in ink. */
export function Sentence({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p
      className={cn(
        "text-[clamp(22px,2.6vw,32px)] font-medium leading-[1.62] tracking-[-0.025em] text-fg-2",
        className,
      )}
    >
      {children}
    </p>
  );
}

const TOKEN_BASE =
  "relative inline rounded-[12px] px-1 text-left [box-decoration-break:clone] [-webkit-box-decoration-break:clone] " +
  "underline decoration-2 underline-offset-[7px] transition-[background-color,box-shadow,color,text-decoration-color] duration-300 ease-expo " +
  "hover:bg-surface hover:no-underline hover:shadow-[var(--relief-sm)] focus-visible:rounded-[12px]";

export function Token({
  tokenKey,
  id,
  label,
  value,
  placeholder,
  invalid,
  describedBy,
  editorWidth,
  children,
}: {
  tokenKey: string;
  /** DOM id — the form focuses it when this field has an error. */
  id?: string;
  /** What the word stands for ("Volume"). Names the button and its editor. */
  label: string;
  /** Shown text; null/empty shows the placeholder (dashed, quiet). */
  value: ReactNode | null;
  placeholder: string;
  invalid?: boolean;
  describedBy?: string;
  editorWidth?: number;
  /** The editor. Call `close()` when done. */
  children: (close: () => void) => ReactNode;
}) {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("<Token> must be inside <ComposerSurface>");
  const open = ctx.openKey === tokenKey;
  const btnRef = useRef<HTMLButtonElement>(null);
  const popId = useId();
  const empty = value === null || value === undefined || value === "";
  const shown = empty ? placeholder : value;
  const spoken = typeof shown === "string" ? shown : undefined;

  const close = useCallback(
    (focus: "anchor" | "next" | "none" = "anchor") => {
      ctx.setOpenKey(null);
      if (focus === "none") return;
      const anchor = btnRef.current;
      if (!anchor) return;
      if (focus === "next") {
        const all = Array.from(ctx.container.current?.querySelectorAll<HTMLElement>("[data-token]") ?? []);
        const next = all[all.indexOf(anchor) + 1];
        (next ?? anchor).focus();
        return;
      }
      anchor.focus();
    },
    [ctx],
  );

  return (
    <>
      <button
        ref={btnRef}
        id={id}
        type="button"
        data-token=""
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? popId : undefined}
        aria-label={spoken ? `${label}: ${spoken}. Change` : `${label}: change`}
        aria-describedby={describedBy}
        onClick={() => ctx.setOpenKey(open ? null : tokenKey)}
        className={cn(
          TOKEN_BASE,
          empty
            ? "text-fg-3 decoration-dashed decoration-[rgb(10_10_10/0.28)]"
            : "text-fg decoration-[rgb(10_10_10/0.22)]",
          invalid && "text-danger decoration-[rgb(179_38_30/0.55)]",
          open && "bg-surface no-underline shadow-[var(--relief-sm)]",
        )}
      >
        {shown}
      </button>
      {open && ctx.layer
        ? createPortal(
            <Popover
              id={popId}
              label={label}
              anchor={btnRef}
              container={ctx.container}
              width={editorWidth}
              onClose={close}
            >
              {children(() => close("anchor"))}
            </Popover>,
            ctx.layer,
          )
        : null}
    </>
  );
}

function focusables(root: HTMLElement) {
  return Array.from(
    root.querySelectorAll<HTMLElement>(
      'button:not([disabled]):not([tabindex="-1"]), input:not([disabled]), [tabindex="0"]',
    ),
  ).filter((el) => el.offsetParent !== null || el === document.activeElement);
}

function Popover({
  id,
  label,
  anchor,
  container,
  width = 288,
  onClose,
  children,
}: {
  id: string;
  label: string;
  anchor: RefObject<HTMLButtonElement>;
  container: RefObject<HTMLDivElement>;
  width?: number;
  onClose: (focus?: "anchor" | "next" | "none") => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null);

  // Sit under the last line of the word (words can wrap), clamped inside
  // the composer so it never leaves the card on phones.
  useLayoutEffect(() => {
    const place = () => {
      const a = anchor.current;
      const c = container.current;
      if (!a || !c) return;
      const rects = a.getClientRects();
      const r = rects[rects.length - 1] ?? a.getBoundingClientRect();
      const box = c.getBoundingClientRect();
      const w = Math.max(220, Math.min(width, box.width - 8));
      const left = Math.max(4, Math.min(r.left - box.left - 4, box.width - w - 4));
      setPos({ top: r.bottom - box.top + 10, left, width: w });
    };
    place();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [anchor, container, width]);

  // Move focus in once placed; keep the editor on screen.
  const placed = pos !== null;
  useEffect(() => {
    if (!placed) return;
    const el = ref.current;
    if (!el) return;
    const target =
      el.querySelector<HTMLElement>("[data-autofocus]") ??
      el.querySelector<HTMLElement>('[role="radio"][aria-checked="true"]') ??
      focusables(el)[0];
    target?.focus({ preventScroll: true });
    el.scrollIntoView({ block: "nearest", behavior: reduce ? "auto" : "smooth" });
  }, [placed, reduce]);

  // Press outside (not on the word itself) closes without stealing focus.
  useEffect(() => {
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node;
      if (ref.current?.contains(t) || anchor.current?.contains(t)) return;
      onClose("none");
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [anchor, onClose]);

  const onKeyDown = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      onClose("anchor");
      return;
    }
    if (e.key === "Tab" && ref.current) {
      const list = focusables(ref.current);
      const first = list[0];
      const last = list[list.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        onClose("anchor");
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        onClose("next");
      }
    }
  };

  return (
    <motion.div
      ref={ref}
      id={id}
      role="dialog"
      aria-label={label}
      initial={{ opacity: 0, y: reduce ? 0 : -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: EASE }}
      onKeyDown={onKeyDown}
      className="glass absolute z-50 scroll-mb-32 scroll-mt-28 rounded-[22px] p-2 text-fg"
      style={pos ? { top: pos.top, left: pos.left, width: pos.width } : { visibility: "hidden" }}
    >
      <p className="t-label px-3 pb-1.5 pt-2 text-fg-3">{label}</p>
      {children}
    </motion.div>
  );
}

/* ───────────────────────────── Editors ───────────────────────────── */

/** Enter in an editor field closes it instead of submitting the form. */
function enterCloses(onDone: () => void) {
  return (e: ReactKeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      onDone();
    }
  };
}

function stepFor(n: number) {
  if (!Number.isFinite(n) || n < 10) return 1;
  return Math.pow(10, Math.floor(Math.log10(n)) - 1);
}

const trim2 = (n: number) => String(Math.round(n * 100) / 100);

/** Well stepper: − [value] +, an optional unit switch, Clear and Done. */
export function NumberEditor({
  label,
  value,
  onChange,
  sanitize,
  prefix,
  suffix,
  error,
  extra,
  onDone,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  /** Cleans typed input (digits, one dot, two decimals). */
  sanitize: (v: string) => string;
  prefix?: string;
  suffix?: string;
  error?: string;
  /** Rendered under the stepper (e.g. the unit switch). */
  extra?: ReactNode;
  onDone: () => void;
}) {
  const n = Number(value);
  const has = value !== "" && Number.isFinite(n);
  const step = stepFor(has ? n : 0);
  const errId = useId();
  return (
    <div className="p-2">
      <div
        className={cn(
          "well flex items-center gap-1 rounded-[16px] p-1 transition-shadow duration-300 ease-expo",
          "focus-within:shadow-[var(--well),0_0_0_1px_var(--c-fg),0_0_0_4px_rgb(196_216_46/0.35)]",
          error && "shadow-[var(--well),0_0_0_1px_var(--c-danger)]",
        )}
      >
        <StepButton
          icon="minus"
          label={`Decrease ${label.toLowerCase()}`}
          disabled={!has || n - step <= 0}
          onClick={() => onChange(trim2(Math.max(0, n - step)))}
        />
        <label className="flex min-w-0 flex-1 items-baseline justify-center gap-1">
          {prefix ? <span className="t-code text-fg-3">{prefix}</span> : null}
          <input
            data-autofocus
            inputMode="decimal"
            autoComplete="off"
            aria-label={label}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? errId : undefined}
            placeholder="0"
            value={value}
            onChange={(e) => onChange(sanitize(e.target.value))}
            onKeyDown={enterCloses(onDone)}
            onFocus={(e) => e.currentTarget.select()}
            className="tabular h-10 w-full min-w-0 bg-transparent text-center text-[18px] font-medium text-fg outline-none placeholder:text-fg-3"
          />
          {suffix ? <span className="t-code shrink-0 text-fg-3">{suffix}</span> : null}
        </label>
        <StepButton
          icon="plus"
          label={`Increase ${label.toLowerCase()}`}
          onClick={() => onChange(trim2((has ? n : 0) + step))}
        />
      </div>
      {error ? (
        <p id={errId} className="t-sub mt-2 flex items-start gap-1.5 px-1 text-danger">
          <Icon name="alert" size={14} className="mt-[1px] shrink-0" />
          {error}
        </p>
      ) : null}
      {extra ? <div className="mt-2">{extra}</div> : null}
      <EditorActions onDone={onDone} onClear={has ? () => onChange("") : undefined} />
    </div>
  );
}

function StepButton({
  icon,
  label,
  onClick,
  disabled,
}: {
  icon: "minus" | "plus";
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="relief-sm grid size-9 shrink-0 place-items-center rounded-full text-fg-2 transition-[color,opacity,transform] duration-300 ease-expo hover:text-fg active:scale-95 disabled:pointer-events-none disabled:opacity-40"
    >
      <Icon name={icon} size={17} />
    </button>
  );
}

function EditorActions({ onDone, onClear }: { onDone: () => void; onClear?: () => void }) {
  return (
    <div className="mt-2 flex items-center gap-2">
      {onClear ? (
        <Button variant="quiet" size="sm" onClick={onClear} className="hover:bg-[rgb(10_10_10/0.05)]">
          Clear
        </Button>
      ) : null}
      <Button variant="primary" size="sm" onClick={onDone} className="flex-1">
        Done
      </Button>
    </div>
  );
}

/** A text field in a well, with Done. */
export function TextEditor({
  label,
  value,
  onChange,
  placeholder,
  maxLength,
  error,
  hint,
  onDone,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  maxLength?: number;
  error?: string;
  hint?: string;
  onDone: () => void;
}) {
  const errId = useId();
  return (
    <div className="p-2">
      <input
        data-autofocus
        type="text"
        autoComplete="off"
        aria-label={label}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errId : undefined}
        placeholder={placeholder}
        maxLength={maxLength}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={enterCloses(onDone)}
        className="field h-12 px-4 text-[15px]"
      />
      {error ? (
        <p id={errId} className="t-sub mt-2 flex items-start gap-1.5 px-1 text-danger">
          <Icon name="alert" size={14} className="mt-[1px] shrink-0" />
          {error}
        </p>
      ) : hint ? (
        <p className="t-sub mt-2 px-1 text-fg-3">{hint}</p>
      ) : null}
      <EditorActions onDone={onDone} onClear={value ? () => onChange("") : undefined} />
    </div>
  );
}

/**
 * One choice from a list — a real radiogroup (↑/↓, Home/End). Picking
 * closes the editor. `search` adds a filter field for long lists;
 * `noneLabel` adds a first option that clears an optional field.
 */
export function ChoiceEditor<T extends string>({
  label,
  options,
  value,
  onChange,
  search,
  noneLabel,
  onDone,
}: {
  label: string;
  options: ReadonlyArray<T>;
  value: T | "";
  onChange: (v: T | "") => void;
  search?: boolean;
  noneLabel?: string;
  onDone: () => void;
}) {
  const [q, setQ] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const opts = needle ? options.filter((o) => o.toLowerCase().includes(needle)) : options.slice();
    const all: Array<{ value: T | ""; label: string }> = opts.map((o) => ({ value: o, label: o }));
    if (noneLabel && !needle) all.unshift({ value: "", label: noneLabel });
    return all;
  }, [options, q, noneLabel]);

  const activeIndex = Math.max(
    0,
    rows.findIndex((r) => r.value === value),
  );

  const pick = (v: T | "") => {
    onChange(v);
    onDone();
  };

  const move = (e: ReactKeyboardEvent<HTMLButtonElement>, i: number) => {
    const radios = Array.from(listRef.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]') ?? []);
    let to = -1;
    if (e.key === "ArrowDown" || e.key === "ArrowRight") to = Math.min(radios.length - 1, i + 1);
    else if (e.key === "ArrowUp" || e.key === "ArrowLeft") to = Math.max(0, i - 1);
    else if (e.key === "Home") to = 0;
    else if (e.key === "End") to = radios.length - 1;
    if (to < 0) return;
    e.preventDefault();
    radios[to]?.focus();
  };

  return (
    <div className="pb-1">
      {search ? (
        <div className="px-2 pb-2">
          <div className="relative">
            <Icon name="search" size={15} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-fg-3" />
            <input
              data-autofocus
              type="text"
              autoComplete="off"
              aria-label={`Search ${label.toLowerCase()}`}
              placeholder="Type to narrow"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  if (rows.length === 1 || (q && rows[0])) pick(rows[0].value);
                } else if (e.key === "ArrowDown") {
                  e.preventDefault();
                  listRef.current?.querySelector<HTMLButtonElement>('[role="radio"]')?.focus();
                }
              }}
              className="field h-10 pl-10 pr-3 text-[14px]"
            />
          </div>
        </div>
      ) : null}
      <div ref={listRef} role="radiogroup" aria-label={label} className="max-h-72 overflow-y-auto overscroll-contain">
        {rows.length === 0 ? (
          <p className="t-sub px-3 py-2.5 text-fg-3">No match.</p>
        ) : (
          rows.map((r, i) => {
            const on = r.value === value;
            return (
              <button
                key={r.value || "__none"}
                type="button"
                role="radio"
                aria-checked={on}
                tabIndex={i === activeIndex ? 0 : -1}
                onClick={() => pick(r.value)}
                onKeyDown={(e) => move(e, i)}
                className={cn(
                  "t-callout flex w-full items-center justify-between gap-3 rounded-[14px] px-3 py-2.5 text-left transition-colors duration-150",
                  "hover:bg-[rgb(10_10_10/0.06)] focus-visible:bg-[rgb(10_10_10/0.06)] focus-visible:outline-offset-0",
                  on ? "font-medium text-fg" : r.value === "" ? "text-fg-3" : "text-fg-2",
                )}
              >
                {r.label}
                {on ? <Icon name="check" size={16} className="shrink-0 text-accent" /> : null}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
