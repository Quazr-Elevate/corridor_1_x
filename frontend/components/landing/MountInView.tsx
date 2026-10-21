"use client";

import { useRef, type CSSProperties, type ReactNode } from "react";
import { useEnterView } from "@/components/motion/useEnterView";

/**
 * Mounts its children the first time the frame enters the viewport, so
 * drawn-in art (the corridor map's lanes) plays when it is seen, not
 * while it is still below the fold. The frame holds `aspect` until then,
 * so nothing shifts.
 */
export function MountInView({
  children,
  aspect,
  amount = 0.3,
  className,
  style,
}: {
  children: ReactNode;
  /** width / height held before mounting. */
  aspect?: number;
  amount?: number;
  className?: string;
  style?: CSSProperties;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const shown = useEnterView(ref, { amount, once: true });
  return (
    <div
      ref={ref}
      className={className}
      style={{ ...(shown || !aspect ? null : { aspectRatio: String(aspect) }), ...style }}
    >
      {shown ? children : null}
    </div>
  );
}
