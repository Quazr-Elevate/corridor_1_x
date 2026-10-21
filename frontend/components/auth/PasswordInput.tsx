"use client";

import { forwardRef, useState } from "react";
import { IconButton } from "@/components/ui/Button";
import { Input, type InputProps } from "@/components/ui/Field";

/**
 * Password field with a show/hide toggle in the trailing slot.
 * Works on night glass (`night`) and on cream.
 */
export const PasswordInput = forwardRef<HTMLInputElement, Omit<InputProps, "type" | "trailing">>(
  function PasswordInput(props, ref) {
    const [shown, setShown] = useState(false);
    return (
      <Input
        ref={ref}
        {...props}
        type={shown ? "text" : "password"}
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        trailing={
          <IconButton
            icon={shown ? "eye-off" : "eye"}
            label={shown ? "Hide password" : "Show password"}
            aria-pressed={shown}
            onClick={() => setShown((s) => !s)}
            className={props.night ? "text-cream/60 hover:bg-white/[0.06] hover:text-cream" : undefined}
          />
        }
      />
    );
  },
);
