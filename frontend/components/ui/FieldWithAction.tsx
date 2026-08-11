"use client";

import { forwardRef, InputHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface FieldWithActionProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  error?: string;
  action: ReactNode;
}

export const FieldWithAction = forwardRef<HTMLInputElement, FieldWithActionProps>(
  function FieldWithAction({ label, hint, error, action, id, className, ...rest }, ref) {
    const fieldId = id ?? `f-${label.replace(/\s+/g, "-").toLowerCase()}`;
    const invalid = Boolean(error);

    return (
      <div>
        <label htmlFor={fieldId} className="field-label">
          {label}
        </label>
        <div className="field-row" data-invalid={invalid || undefined}>
          <input
            ref={ref}
            id={fieldId}
            aria-invalid={invalid || undefined}
            aria-describedby={error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined}
            className={cn("field", className)}
            {...rest}
          />
          <div className="flex items-center pr-1">{action}</div>
        </div>
        {error ? (
          <span id={`${fieldId}-error`} role="alert" className="field-error">
            {error}
          </span>
        ) : hint ? (
          <span id={`${fieldId}-hint`} className="mt-1.5 block text-xs text-mute">
            {hint}
          </span>
        ) : null}
      </div>
    );
  },
);
