"use client";

import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
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

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "size">, Common {
  placeholder?: string;
  options: ReadonlyArray<{ value: string; label: string } | string>;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, error, optional, required, night, className, inputClassName, action, options, placeholder, id, value, size = "md", ...rest },
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
        <select
          ref={ref}
          id={fid}
          required={required}
          value={value}
          aria-invalid={error ? true : undefined}
          className={cn(
            night ? "field-night" : "field",
            h,
            "appearance-none px-4 pr-11 text-[15px]",
            !value && "text-fg-3",
            inputClassName,
          )}
          {...rest}
        >
          {placeholder !== undefined ? (
            <option value="" disabled={required}>
              {placeholder}
            </option>
          ) : null}
          {options.map((o) => {
            const opt = typeof o === "string" ? { value: o, label: o } : o;
            return (
              <option key={opt.value} value={opt.value} className="text-ink">
                {opt.label}
              </option>
            );
          })}
        </select>
        <Icon
          name="chevron-down"
          size={16}
          className={cn("pointer-events-none absolute right-4 top-1/2 -translate-y-1/2", night ? "text-cream/50" : "text-fg-3")}
        />
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
