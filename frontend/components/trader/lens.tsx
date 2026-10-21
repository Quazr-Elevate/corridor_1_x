"use client";

import { motion, useReducedMotion } from "framer-motion";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import type { Me } from "@/lib/api";
import { cn } from "@/lib/cn";
import { SPRING } from "@/components/motion/tokens";
import { XMark } from "@/components/ui/Logo";

/**
 * The trader's lens — Selling or Buying (reference: portal /corridor top
 * cluster). It decides what the Corridor home leads with: your listings
 * and seller moves, or the live market. Defaults from the business
 * profile's trade position; the choice is remembered per browser.
 */

export type Lens = "selling" | "buying";

const KEY = "cor1x.lens";

interface LensValue {
  lens: Lens;
  setLens: (lens: Lens) => void;
}

const LensContext = createContext<LensValue>({ lens: "selling", setLens: () => {} });

function lensFor(me: Me | null): Lens {
  const tp = me?.business.tradePosition;
  if (tp === "buyer") return "buying";
  if (tp === "seller" || tp === "both") return "selling";
  return me?.userType === "buyer" ? "buying" : "selling";
}

export function LensProvider({ me, children }: { me: Me | null; children: ReactNode }) {
  const [stored, setStored] = useState<Lens | null>(null);

  useEffect(() => {
    try {
      const v = window.localStorage.getItem(KEY);
      if (v === "selling" || v === "buying") setStored(v);
    } catch {
      // Storage blocked (private window) — the profile default stands.
    }
  }, []);

  const setLens = useCallback((lens: Lens) => {
    setStored(lens);
    try {
      window.localStorage.setItem(KEY, lens);
    } catch {
      // Not remembered; still applies for this visit.
    }
  }, []);

  const lens = stored ?? lensFor(me);
  return <LensContext.Provider value={{ lens, setLens }}>{children}</LensContext.Provider>;
}

export function useLens(): LensValue {
  return useContext(LensContext);
}

export const LENS_LABEL: Record<Lens, string> = { selling: "Selling", buying: "Buying" };

const OPTIONS: ReadonlyArray<Lens> = ["selling", "buying"];

/**
 * Relief track, solid thumb that springs between the two sides, and the
 * small cream disc with the X sitting on the seam. A real radiogroup:
 * arrows switch, only the checked side is in the tab order.
 */
export function LensSwitch({ className }: { className?: string }) {
  const { lens, setLens } = useLens();
  const reduce = useReducedMotion();
  const refs = useRef<Array<HTMLButtonElement | null>>([]);

  return (
    <div
      role="radiogroup"
      aria-label="Lens"
      className={cn("relief-sm relative inline-flex shrink-0 items-center rounded-full p-1", className)}
    >
      {OPTIONS.map((value, i) => {
        const on = lens === value;
        return (
          <button
            key={value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={on}
            tabIndex={on ? 0 : -1}
            onClick={() => setLens(value)}
            onKeyDown={(e) => {
              if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
              e.preventDefault();
              const next = OPTIONS[(i + 1) % OPTIONS.length];
              setLens(next);
              refs.current[OPTIONS.indexOf(next)]?.focus();
            }}
            className={cn(
              "relative z-10 flex h-9 items-center rounded-full text-[13px] font-medium tracking-[-0.01em] transition-colors duration-300",
              i === 0 ? "pl-3 pr-5" : "pl-5 pr-3",
              on ? "text-cream" : "text-fg-3 hover:text-fg",
            )}
          >
            {on ? (
              <motion.span
                layoutId="trader-lens-thumb"
                className="solid absolute inset-0 -z-10 rounded-full"
                transition={reduce ? { duration: 0 } : SPRING}
              />
            ) : null}
            {LENS_LABEL[value]}
          </button>
        );
      })}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-1/2 z-20 -ml-[9px] -mt-[9px] grid size-[18px] place-items-center rounded-full bg-ground text-fg shadow-[0_0_0_3px_var(--c-surface)]"
      >
        <XMark size={9} />
      </span>
    </div>
  );
}
