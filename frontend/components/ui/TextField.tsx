import { forwardRef, InputHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Badge } from "./Badge";

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  error?: string;
  optional?: boolean;
  autofill?: boolean;
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
        {label}
      </label>
      <div className="relative">
        <input
          ref={ref}
          id={fieldId}
          readOnly={readOnly}
          aria-invalid={invalid || undefined}
          aria-describedby={error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined}
          className={cn("field", (autofill || readOnly) && "pr-24", className)}
          {...rest}
        />
        {(autofill || optional) && !trailing ? (
          <div className="pointer-events-none absolute inset-y-0 right-2 flex items-center">
            {autofill ? (
              <Badge tone="autofill">Auto-fill</Badge>
            ) : (
              <Badge tone="optional">Optional</Badge>
            )}
          </div>
        ) : null}
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
