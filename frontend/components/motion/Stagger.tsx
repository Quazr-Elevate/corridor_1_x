"use client";

import { motion, type Variants } from "framer-motion";
import { createContext, forwardRef, useContext, useRef, type CSSProperties, type ReactNode, type Ref } from "react";
import { DURATION, EASE, RISE, STAGGER } from "./tokens";
import { Reveal, useMergedRef, type MotionDomProps, type MotionTag, type RevealProps } from "./Reveal";
import { useEnterView } from "./useEnterView";

/**
 * Stagger — a container that reveals its <StaggerItem> children one after
 * another (60ms apart) when it enters the viewport. Each item uses the
 * same motion as <Reveal>: fade + 14px rise on the expo curve.
 *
 *   <Stagger as="ul" className="grid gap-4 sm:grid-cols-3">
 *     {items.map((x) => <StaggerItem as="li" key={x.id}>…</StaggerItem>)}
 *   </Stagger>
 *
 * Items may sit deeper than direct children (variants travel through
 * context). A <StaggerItem> outside a <Stagger> behaves like a <Reveal>.
 */

const InStagger = createContext(false);

export interface StaggerProps extends MotionDomProps {
  as?: MotionTag;
  /** Seconds between items. Default 0.06. */
  stagger?: number;
  /** Seconds before the first item. */
  delay?: number;
  /** Share of the container that must be visible (0–1). Default 0.15. */
  amount?: number;
  once?: boolean;
  style?: CSSProperties;
  children?: ReactNode;
}

export const Stagger = forwardRef<HTMLElement, StaggerProps>(function Stagger(
  { as = "div", stagger = STAGGER, delay = 0, amount = 0.15, once = true, children, ...rest },
  forwarded,
) {
  const local = useRef<HTMLElement | null>(null);
  const ref = useMergedRef<HTMLElement>(local, forwarded);
  const shown = useEnterView(local, { amount, once });
  const Comp = motion[as] as typeof motion.div;
  const variants: Variants = {
    hidden: { transition: { staggerChildren: 0.02, staggerDirection: -1 } },
    shown: { transition: { staggerChildren: stagger, delayChildren: delay } },
  };
  return (
    <InStagger.Provider value>
      <Comp
        ref={ref as Ref<HTMLDivElement>}
        initial="hidden"
        animate={shown ? "shown" : "hidden"}
        variants={variants}
        {...(rest as Record<string, unknown>)}
      >
        {children}
      </Comp>
    </InStagger.Provider>
  );
});

export interface StaggerItemProps extends MotionDomProps {
  as?: MotionTag;
  /** Rise distance in px. Default 14. */
  y?: number;
  /** Seconds. Default 0.7. */
  duration?: number;
  style?: CSSProperties;
  children?: ReactNode;
}

export const StaggerItem = forwardRef<HTMLElement, StaggerItemProps>(function StaggerItem(
  { as = "div", y = RISE.reveal, duration = DURATION.reveal, children, ...rest },
  ref,
) {
  const inStagger = useContext(InStagger);
  if (!inStagger) {
    return (
      <Reveal ref={ref} as={as} y={y} duration={duration} {...(rest as RevealProps)}>
        {children}
      </Reveal>
    );
  }
  const Comp = motion[as] as typeof motion.div;
  const variants: Variants = {
    hidden: { opacity: 0, y, transition: { duration: 0.3, ease: EASE } },
    shown: { opacity: 1, y: 0, transition: { duration, ease: EASE } },
  };
  return (
    <Comp ref={ref as Ref<HTMLDivElement>} variants={variants} {...(rest as Record<string, unknown>)}>
      {children}
    </Comp>
  );
});
