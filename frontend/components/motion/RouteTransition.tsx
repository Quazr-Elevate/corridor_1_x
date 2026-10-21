"use client";

import { motion } from "framer-motion";
import { useSyncExternalStore, type ReactNode } from "react";
import { DURATION, EASE, RISE } from "./tokens";

/**
 * RouteTransition — page content settles in on every navigation: opacity
 * and an 8px rise on the expo curve, 0.5s. Used by the route `template.tsx`
 * files, which Next.js re-mounts per navigation; the shells (dock, rail,
 * top cluster) live in `layout.tsx`, so they never move.
 *
 * - Server render and hydration are not animated: content painted by the
 *   server is visible immediately (no blank first paint, no flash).
 * - Every later mount — a client navigation, or content that appears after
 *   a shell finishes loading — fades in.
 * - Opacity and transform only, so there is no layout shift; at rest the
 *   transform is `none`, so fixed descendants position normally.
 * - Reduced Motion (MotionProvider) drops the rise; the fade stays.
 */

const noopSubscribe = () => () => {};

/** False while hydrating server HTML, true for any fresh client mount. */
function useIsClientMount() {
  return useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
}

export function RouteTransition({ children, className }: { children: ReactNode; className?: string }) {
  const fresh = useIsClientMount();
  return (
    <motion.div
      className={className}
      initial={fresh ? { opacity: 0, y: RISE.route } : false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DURATION.route, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}
