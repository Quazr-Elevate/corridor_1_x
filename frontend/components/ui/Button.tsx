"use client";

import { ButtonHTMLAttributes, forwardRef, PointerEvent } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "ghost" | "inline";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", className, children, onPointerDown, disabled, loading, type = "button", ...rest },
  ref,
) {
  const handlePointerDown = (e: PointerEvent<HTMLButtonElement>) => {
    if (disabled || loading) return;
    const btn = e.currentTarget;
    const rect = btn.getBoundingClientRect();
    const ripple = document.createElement("span");
    ripple.className = "btn-ripple";
    ripple.style.left = `${e.clientX - rect.left}px`;
    ripple.style.top = `${e.clientY - rect.top}px`;
    btn.appendChild(ripple);
    const cleanup = () => ripple.remove();
    ripple.addEventListener("animationend", cleanup, { once: true });
    onPointerDown?.(e);
  };

  const variantClass =
    variant === "primary" ? "btn-primary" : variant === "ghost" ? "btn-ghost" : "btn-inline";

  return (
    <button
      ref={ref}
      type={type}
      className={cn(variantClass, className)}
      onPointerDown={handlePointerDown}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Loader2 aria-hidden className="h-4 w-4 animate-spin" /> : null}
      <span className="inline-flex items-center gap-2">{children}</span>
    </button>
  );
});
