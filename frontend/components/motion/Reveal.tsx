"use client";

import { motion, type Variants } from "framer-motion";
import {
  forwardRef,
  useCallback,
  useRef,
  type CSSProperties,
  type ForwardedRef,
  type HTMLAttributes,
  type ReactNode,
  type Ref,
} from "react";
import { DURATION, EASE, RISE } from "./tokens";
import { useEnterView } from "./useEnterView";

/**
 * Reveal — content arrives once, as it enters the viewport: opacity 0 → 1
 * and a 14px rise on the one expo curve. No scale, no rotation.
 *
 * Reduced Motion (via the root <MotionProvider>, reducedMotion="user")
 * removes the travel; only the fade remains.
 *
 *   <Reveal>…</Reveal>
 *   <Reveal as="section" delay={0.1} className="mt-10">…</Reveal>
 */

export type MotionTag =
  | "div"
  | "section"
  | "article"
  | "aside"
  | "header"
  | "footer"
  | "main"
  | "nav"
  | "ul"
  | "ol"
  | "li"
  | "dl"
  | "span"
  | "p"
  | "figure";

/** DOM props that don't collide with framer-motion's own handlers. */
export type MotionDomProps = Omit<
  HTMLAttributes<HTMLElement>,
  | "onAnimationStart"
  | "onAnimationEnd"
  | "onAnimationIteration"
  | "onDrag"
  | "onDragStart"
  | "onDragEnd"
  | "style"
  | "children"
>;

export interface RevealProps extends MotionDomProps {
  /** Element to render. Default `div`. */
  as?: MotionTag;
  /** Seconds before the reveal starts once in view. */
  delay?: number;
  /** Rise distance in px. Default 14. */
  y?: number;
  /** Seconds. Default 0.7. */
  duration?: number;
  /** Share of the element that must be visible (0–1). Default 0.2. */
  amount?: number;
  /** Reveal only the first time. Default true. */
  once?: boolean;
  style?: CSSProperties;
  children?: ReactNode;
}

export function revealVariants(y: number = RISE.reveal, duration: number = DURATION.reveal, delay = 0): Variants {
  return {
    hidden: { opacity: 0, y, transition: { duration: 0.3, ease: EASE } },
    shown: { opacity: 1, y: 0, transition: { duration, delay, ease: EASE } },
  };
}

function assignRef<T>(r: Ref<T> | ForwardedRef<T> | undefined, node: T | null) {
  if (!r) return;
  if (typeof r === "function") r(node);
  else (r as { current: T | null }).current = node;
}

/** Point a local ref and a forwarded ref at the same node. */
export function useMergedRef<T>(a: Ref<T> | ForwardedRef<T> | undefined, b: Ref<T> | ForwardedRef<T> | undefined) {
  return useCallback(
    (node: T | null) => {
      assignRef(a, node);
      assignRef(b, node);
    },
    [a, b],
  );
}

export const Reveal = forwardRef<HTMLElement, RevealProps>(function Reveal(
  {
    as = "div",
    delay = 0,
    y = RISE.reveal,
    duration = DURATION.reveal,
    amount = 0.2,
    once = true,
    children,
    ...rest
  },
  forwarded,
) {
  const local = useRef<HTMLElement | null>(null);
  const ref = useMergedRef<HTMLElement>(local, forwarded);
  const shown = useEnterView(local, { amount, once });
  const Comp = motion[as] as typeof motion.div;
  return (
    <Comp
      ref={ref as Ref<HTMLDivElement>}
      initial="hidden"
      animate={shown ? "shown" : "hidden"}
      variants={revealVariants(y, duration, delay)}
      {...(rest as Record<string, unknown>)}
    >
      {children}
    </Comp>
  );
});
