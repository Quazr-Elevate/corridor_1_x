"use client";

import { MotionConfig } from "framer-motion";
import type { ReactNode } from "react";

/**
 * Root motion settings. `reducedMotion="user"` follows the OS setting:
 * with Reduce Motion on, framer-motion drops every transform (travel,
 * layout moves) and keeps opacity — "Reduced Motion removes travel".
 * CSS animations are handled by the matching media query in globals.css.
 */
export function MotionProvider({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
