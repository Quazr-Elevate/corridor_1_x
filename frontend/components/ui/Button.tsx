"use client";

import Link from "next/link";
import { forwardRef, type AnchorHTMLAttributes, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Icon, type IconName } from "./Icon";
import {
  buttonClass,
  buttonIconSize,
  iconButtonClass,
  iconButtonGlyphSize,
  type ButtonSize,
  type ButtonVariant,
  type IconButtonSize,
  type IconButtonVariant,
} from "./buttonStyles";

/**
 * Buttons — Corridor Materials. Style maps live in `buttonStyles.ts`
 * (server-safe); this module adds the interactive components.
 *   primary   Solid ink. The default "do this" action.
 *   secondary Relief. Actionable, but not the main path.
 *   commit    Lime fill — only for moves that make something certain
 *             (verify, submit, approve). Use sparingly.
 *   quiet     Text-only, for tertiary actions.
 *   danger    Text in danger, soft fill on hover.
 *   night     Primary on night glass (auth screens).
 *   night-quiet Outline on night glass.
 */
export { buttonClass, iconButtonClass };
export type { ButtonSize, ButtonVariant, IconButtonSize, IconButtonVariant };

function Spinner({ size }: { size: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className="animate-spin"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity=".25" strokeWidth="2" />
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: IconName;
  iconRight?: IconName;
  block?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    size = "md",
    loading,
    icon,
    iconRight,
    block,
    className,
    children,
    disabled,
    type = "button",
    ...rest
  },
  ref,
) {
  const iconSize = buttonIconSize(size);
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={buttonClass(variant, size, cn(block && "w-full", className))}
      {...rest}
    >
      {loading ? <Spinner size={iconSize} /> : icon ? <Icon name={icon} size={iconSize} /> : null}
      {children}
      {iconRight && !loading ? <Icon name={iconRight} size={iconSize} /> : null}
    </button>
  );
});

export interface LinkButtonProps
  extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href" | "children" | "className"> {
  href: string;
  prefetch?: boolean;
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: IconName;
  iconRight?: IconName;
  block?: boolean;
  className?: string;
  children: ReactNode;
}

export function LinkButton({
  href,
  variant = "primary",
  size = "md",
  icon,
  iconRight,
  block,
  className,
  children,
  ...rest
}: LinkButtonProps) {
  const iconSize = buttonIconSize(size);
  return (
    <Link href={href} className={buttonClass(variant, size, cn(block && "w-full", className))} {...rest}>
      {icon ? <Icon name={icon} size={iconSize} /> : null}
      {children}
      {iconRight ? <Icon name={iconRight} size={iconSize} /> : null}
    </Link>
  );
}

/**
 * Round icon-only control (top cluster, close buttons, field toggles).
 * Variants: quiet (default) · secondary (relief) · primary (solid) ·
 * night (on night glass) · glass (floating over photography).
 */
export function IconButton({
  icon,
  label,
  className,
  variant = "quiet",
  size = "md",
  ...rest
}: Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  icon: IconName;
  label: string;
  variant?: IconButtonVariant;
  size?: IconButtonSize;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={iconButtonClass(variant, size, className)}
      {...rest}
    >
      <Icon name={icon} size={iconButtonGlyphSize(size)} />
    </button>
  );
}

export { Spinner };
