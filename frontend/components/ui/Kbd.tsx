import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * Kbd — a mono key cap for shortcuts and gestures ("⌘ K", "J / K").
 * Hairline edge with a 1px bottom lip so it reads as a key, not a chip.
 *
 *   <Kbd>⌘</Kbd><Kbd>K</Kbd>
 */
export function Kbd({
  children,
  size = "md",
  className,
}: {
  children: ReactNode;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  return (
    <kbd
      className={cn(
        "t-code inline-grid shrink-0 place-items-center rounded-[6px] px-1 leading-none text-fg-3",
        "shadow-[inset_0_0_0_1px_var(--c-line-2),inset_0_-1px_0_var(--c-line-2)]",
        size === "sm" && "h-[18px] min-w-[18px] text-[10px]",
        size === "md" && "h-5 min-w-5 text-[11px]",
        size === "lg" && "h-6 min-w-6 rounded-[7px] px-1.5 text-[12px]",
        className,
      )}
    >
      {children}
    </kbd>
  );
}
