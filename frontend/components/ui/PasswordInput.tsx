"use client";

import { forwardRef, useId, useState } from "react";
import { IconButton } from "./Button";
import { Input, type InputProps } from "./Field";

/**
 * Password field — a well input with a show/hide toggle in the trailing
 * slot. The toggle is a real button (`aria-pressed`, `aria-controls`) and
 * keeps the caret in the field when clicked. `night` for night glass.
 *
 *   <PasswordInput label="Password" autoComplete="new-password" night />
 */
export type PasswordInputProps = Omit<InputProps, "type" | "trailing">;

export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(function PasswordInput(
  { id, night, autoComplete = "current-password", ...props },
  ref,
) {
  const auto = useId();
  const fid = id ?? auto;
  const [shown, setShown] = useState(false);
  return (
    <Input
      ref={ref}
      {...props}
      id={fid}
      night={night}
      type={shown ? "text" : "password"}
      autoComplete={autoComplete}
      autoCapitalize="none"
      autoCorrect="off"
      spellCheck={false}
      trailing={
        <IconButton
          icon={shown ? "eye-off" : "eye"}
          label={shown ? "Hide password" : "Show password"}
          aria-pressed={shown}
          aria-controls={fid}
          variant={night ? "night" : "quiet"}
          disabled={props.disabled}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => setShown((s) => !s)}
        />
      }
    />
  );
});
