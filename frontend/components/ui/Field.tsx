"use client";

import {
  forwardRef,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type InputHTMLAttributes,
  type KeyboardEvent,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { cn } from "@/lib/cn";
import { Icon } from "./Icon";

/**
 * Fields sit in a well (sunk relief). Labels are mono, uppercase
 * (`t-label`). Errors read in danger directly under the well.
 *
 * `night` renders the field for night-glass surfaces (auth screens).
 */

export interface FieldShellProps {
  label?: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  optional?: boolean;
  required?: boolean;
  night?: boolean;
  htmlFor?: string;
  className?: string;
  action?: ReactNode;
  children: ReactNode;
}

export function FieldShell({
  label,
  hint,
  error,
  optional,
  required,
  night,
  htmlFor,
  className,
  action,
  children,
}: FieldShellProps) {
  return (
    <div className={cn("min-w-0", className)}>
      {label ? (
        <div className="mb-2 flex items-baseline justify-between gap-3">
          <label
            htmlFor={htmlFor}
            className={cn("t-label", night ? "text-cream/55" : "text-fg-3")}
          >
            {label}
            {required ? <span className="ml-1 text-danger">*</span> : null}
            {optional ? (
              <span className={cn("ml-1.5 normal-case tracking-normal", night ? "text-cream/40" : "text-fg-3")}>
                optional
              </span>
            ) : null}
          </label>
          {action}
        </div>
      ) : null}
      {children}
      {error ? (
        <p role="alert" className={cn("t-sub mt-2 flex items-start gap-1.5", night ? "text-[#ff7a6b]" : "text-danger")}>
          <Icon name="alert" size={14} className="mt-[1px] shrink-0" />
          {error}
        </p>
      ) : hint ? (
        <p className={cn("t-sub mt-2", night ? "text-cream/50" : "text-fg-3")}>{hint}</p>
      ) : null}
    </div>
  );
}

type Common = Omit<FieldShellProps, "children" | "htmlFor"> & {
  inputClassName?: string;
  size?: "md" | "lg";
};

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "size">, Common {
  leading?: ReactNode;
  trailing?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  {
    label,
    hint,
    error,
    optional,
    required,
    night,
    className,
    inputClassName,
    action,
    leading,
    trailing,
    size = "md",
    id,
    ...rest
  },
  ref,
) {
  const auto = useId();
  const fid = id ?? auto;
  const h = size === "lg" ? "h-[52px]" : "h-12";
  return (
    <FieldShell
      label={label}
      hint={hint}
      error={error}
      optional={optional}
      required={required}
      night={night}
      htmlFor={fid}
      className={className}
      action={action}
    >
      <div className="relative">
        {leading ? (
          <span className={cn("pointer-events-none absolute left-4 top-1/2 -translate-y-1/2", night ? "text-cream/50" : "text-fg-3")}>
            {leading}
          </span>
        ) : null}
        <input
          ref={ref}
          id={fid}
          required={required}
          aria-invalid={error ? true : undefined}
          className={cn(
            night ? "field-night" : "field",
            h,
            "px-4 text-[15px]",
            leading ? "pl-11" : undefined,
            trailing ? "pr-12" : undefined,
            inputClassName,
          )}
          {...rest}
        />
        {trailing ? (
          <span className="absolute right-2 top-1/2 -translate-y-1/2">{trailing}</span>
        ) : null}
      </div>
    </FieldShell>
  );
});

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement>, Omit<Common, "size"> {
  counter?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, hint, error, optional, required, night, className, inputClassName, action, counter, id, maxLength, value, ...rest },
  ref,
) {
  const auto = useId();
  const fid = id ?? auto;
  const len = typeof value === "string" ? value.length : 0;
  return (
    <FieldShell
      label={label}
      hint={hint}
      error={error}
      optional={optional}
      required={required}
      night={night}
      htmlFor={fid}
      className={className}
      action={
        action ??
        (counter && maxLength ? (
          <span className="t-code text-fg-3 tabular">
            {len}/{maxLength}
          </span>
        ) : undefined)
      }
    >
      <textarea
        ref={ref}
        id={fid}
        required={required}
        maxLength={maxLength}
        value={value}
        aria-invalid={error ? true : undefined}
        className={cn(night ? "field-night" : "field", "min-h-[112px] resize-y px-4 py-3 text-[15px] leading-relaxed", inputClassName)}
        {...rest}
      />
    </FieldShell>
  );
});

export interface SelectProps
  extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "size" | "onChange" | "value" | "defaultValue">,
    Common {
  placeholder?: string;
  options: ReadonlyArray<{ value: string; label: string } | string>;
  value?: string;
  /** Called like a native select's change handler: read `e.target.value`. */
  onChange?: (e: ChangeEvent<HTMLSelectElement>) => void;
}

type Opt = { value: string; label: string; disabled?: boolean };

/**
 * A select drawn by the page, not the operating system. The native list
 * ignores the page's colours on some systems (macOS, dark mode), which left
 * black text on a black menu; this one uses the surface's own colours
 * everywhere, in the trader app and the console alike.
 *
 * Same props as a native select. A hidden native <select> keeps `name`,
 * `required` and form autofill working.
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  {
    label, hint, error, optional, required, night, className, inputClassName, action, options, placeholder, id,
    value, size = "md", onChange, disabled, name, autoComplete, ...rest
  },
  ref,
) {
  const auto = useId();
  const fid = id ?? auto;
  const listId = `${fid}-list`;
  const h = size === "lg" ? "h-[52px]" : "h-12";
  const items: Opt[] = useMemo(
    () => [
      ...(placeholder !== undefined ? [{ value: "", label: placeholder, disabled: !!required }] : []),
      ...options.map((o) => (typeof o === "string" ? { value: o, label: o } : o)),
    ],
    [options, placeholder, required],
  );
  const current = value ?? "";
  const chosen = items.find((o) => o.value === current);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [placeUp, setPlaceUp] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const typed = useRef({ text: "", at: 0 });

  const pick = (o: Opt) => {
    if (o.disabled) return;
    setOpen(false);
    buttonRef.current?.focus();
    if (o.value === current) return;
    const target = { value: o.value, name: name ?? "", id: fid } as HTMLSelectElement;
    onChange?.({ target, currentTarget: target } as unknown as ChangeEvent<HTMLSelectElement>);
  };

  const openList = () => {
    if (disabled) return;
    const box = rootRef.current?.getBoundingClientRect();
    setPlaceUp(!!box && window.innerHeight - box.bottom < 300 && box.top > window.innerHeight - box.bottom);
    const at = items.findIndex((o) => o.value === current);
    setActive(at >= 0 ? at : items.findIndex((o) => !o.disabled));
    setOpen(true);
  };

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);

  useEffect(() => {
    if (open) listRef.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  const move = (from: number, step: number) => {
    for (let i = from + step; i >= 0 && i < items.length; i += step) if (!items[i].disabled) return i;
    return from;
  };

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;
    if (!open) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) {
        e.preventDefault();
        openList();
      }
      return;
    }
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => move(a, 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => move(a, -1)); }
    else if (e.key === "Home") { e.preventDefault(); setActive(move(-1, 1)); }
    else if (e.key === "End") { e.preventDefault(); setActive(move(items.length, -1)); }
    else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); const o = items[active]; if (o) pick(o); }
    else if (e.key === "Escape") { e.preventDefault(); setOpen(false); }
    else if (e.key === "Tab") setOpen(false);
    else if (e.key.length === 1) {
      // Type to jump: "ut" finds "Uttar Pradesh".
      const now = Date.now();
      const text = (now - typed.current.at < 700 ? typed.current.text : "") + e.key.toLowerCase();
      typed.current = { text, at: now };
      const hit = items.findIndex((o) => !o.disabled && o.label.toLowerCase().startsWith(text));
      if (hit >= 0) setActive(hit);
    }
  };

  return (
    <FieldShell
      label={label}
      hint={hint}
      error={error}
      optional={optional}
      required={required}
      night={night}
      htmlFor={fid}
      className={className}
      action={action}
    >
      <div ref={rootRef} className="relative">
        <button
          ref={buttonRef}
          id={fid}
          type="button"
          role="combobox"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={listId}
          aria-activedescendant={open ? `${fid}-opt-${active}` : undefined}
          aria-invalid={error ? true : undefined}
          aria-required={required || undefined}
          disabled={disabled}
          onClick={() => (open ? setOpen(false) : openList())}
          onKeyDown={onKeyDown}
          className={cn(
            night ? "field-night" : "field",
            h,
            "flex items-center px-4 pr-11 text-left text-[15px] disabled:cursor-not-allowed",
            !current && (night ? "text-cream/45" : "text-fg-3"),
            inputClassName,
          )}
        >
          <span className="min-w-0 flex-1 truncate">{chosen?.label ?? current}</span>
        </button>
        <Icon
          name="chevron-down"
          size={16}
          className={cn(
            "pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 transition-transform duration-200",
            open && "rotate-180",
            night ? "text-cream/50" : "text-fg-3",
          )}
        />
        {/* Keeps name and autofill for forms; the button above is what people use. Not
            `required`: the browser would try to focus this hidden copy and block the submit. */}
        <select
          ref={ref}
          tabIndex={-1}
          aria-hidden="true"
          name={name}
          autoComplete={autoComplete}
          disabled={disabled}
          value={current}
          onChange={(e) => {
            const o = items.find((x) => x.value === e.target.value);
            if (o) pick(o);
          }}
          className="sr-only"
          {...rest}
        >
          {items.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        {open ? (
          <ul
            ref={listRef}
            id={listId}
            role="listbox"
            aria-labelledby={fid}
            onMouseDown={(e) => e.preventDefault()}
            className={cn(
              "absolute inset-x-0 z-40 max-h-[min(18rem,50vh)] overflow-y-auto overscroll-contain rounded-[18px] border p-1.5",
              placeUp ? "bottom-[calc(100%+8px)]" : "top-[calc(100%+8px)]",
              night ? "select-list-night" : "select-list",
            )}
          >
            {items.map((o, i) => {
              const isActive = i === active;
              const isChosen = o.value === current && !(o.value === "" && placeholder !== undefined);
              return (
                <li
                  key={o.value || "__placeholder"}
                  id={`${fid}-opt-${i}`}
                  data-index={i}
                  role="option"
                  aria-selected={isChosen}
                  aria-disabled={o.disabled || undefined}
                  onMouseMove={() => !o.disabled && i !== active && setActive(i)}
                  onClick={() => pick(o)}
                  className={cn(
                    "flex min-h-10 cursor-pointer items-center gap-3 rounded-[12px] px-3 py-2 text-[14px] transition-colors duration-150",
                    o.disabled && "cursor-default opacity-55",
                    isActive && !o.disabled && "select-option-active",
                    isChosen && "font-medium",
                  )}
                >
                  <span className="min-w-0 flex-1 truncate">{o.label}</span>
                  {isChosen ? <Icon name="check" size={15} strokeWidth={2} className="select-option-check shrink-0" /> : null}
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>
    </FieldShell>
  );
});

/** Static read-only value laid out like a field (for locked/verified data). */
export function ReadField({ label, value, mono }: { label: ReactNode; value: ReactNode; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <p className="t-label text-fg-3">{label}</p>
      <p className={cn("mt-1.5 truncate text-[15px] text-fg", mono && "t-code text-[14px]")}>
        {value || <span className="text-fg-3">—</span>}
      </p>
    </div>
  );
}
