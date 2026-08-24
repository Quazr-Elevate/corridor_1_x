"use client";

import { motion, MotionProps } from "framer-motion";
import { ReactNode } from "react";

/**
 * Wrap a group of children so they reveal with a staggered slide-up.
 * Use for section content that appears after a step is unlocked
 * (e.g. auto-filled fields after GSTIN fetch).
 */
export function MotionStack({
  children,
  className,
  delay = 0,
  stagger = 0.055,
  ...rest
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  stagger?: number;
} & MotionProps) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="visible"
      variants={{
        hidden: {},
        visible: {
          transition: { staggerChildren: stagger, delayChildren: delay },
        },
      }}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

/** Single stack item — pairs with MotionStack for coordinated reveal. */
export function MotionItem({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      variants={{
        hidden: { opacity: 0, y: 10 },
        visible: { opacity: 1, y: 0 },
      }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
