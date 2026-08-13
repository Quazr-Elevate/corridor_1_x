import { forwardRef, InputHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Badge } from "./Badge";

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  error?: string;
  optional?: boolean;
  autofill?: boolean;
  /** Custom element positioned inside the field on the right (e.g. an icon).
      Auto-fill / Optional badges sit next to the label instead. */
  trailing?: ReactNode;
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, hint, error, optional, autofill, trailing, id, className, readOnly, ...rest },
  ref,
) {
  const fieldId = id ?? `f-${label.replace(/\s+/g, "-").toLowerCase()}`;
  const invalid = Boolean(error);

  return (
    <div>
      <label htmlFor={fieldId} className="field-label">
        <span>{label}</span>
        {autofill ? (
          <Badge tone="autofill">Auto-fill</Badge>
        ) : optional ? (
          <Badge tone="optional">Optional</Badge>
        ) : null}
      </label>
      <div className="relative">
        <input
          ref={ref}
          id={fieldId}
          readOnly={readOnly}
          aria-invalid={invalid || undefined}
          aria-describedby={error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined}
          className={cn("field", trailing && "pr-10", className)}
          {...rest}
        />
        {trailing ? (
          <div className="pointer-events-none absolute inset-y-0 right-2 flex items-center">
            {trailing}
          </div>
        ) : null}
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
});
