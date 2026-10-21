"use client";

import { useEffect, useState, type RefObject } from "react";

/**
 * True once an element has properly entered the viewport.
 *
 * "Properly" means either `amount` of the element is visible, or — for
 * elements taller than the screen, which can never reach that ratio — a
 * quarter of the viewport is covered by it. Elements that are already
 * above the viewport when observed (restored scroll, deep links) count as
 * seen, so scrolling back up never finds an empty hole.
 *
 * Without IntersectionObserver the element is simply shown.
 */
export function useEnterView(
  ref: RefObject<Element | null>,
  { amount = 0.2, once = true }: { amount?: number; once?: boolean } = {},
) {
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const target = Math.min(1, Math.max(0, amount));
    // Fine steps up to the target so tall elements get a callback soon
    // after a quarter of the screen is covered.
    const steps: number[] = [];
    for (let t = 0; t < target; t += 0.025) steps.push(Number(t.toFixed(3)));
    const thresholds = Array.from(new Set([...steps, target])).sort((a, b) => a - b);
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          const rootTop = e.rootBounds?.top ?? 0;
          const rootH = e.rootBounds?.height ?? window.innerHeight;
          const passed = !e.isIntersecting && e.boundingClientRect.bottom <= rootTop;
          const enough =
            e.isIntersecting &&
            (e.intersectionRatio >= target - 0.001 || e.intersectionRect.height >= rootH * 0.25);
          if (enough || passed) {
            setInView(true);
            if (once) io.disconnect();
          } else if (!once && !e.isIntersecting) {
            setInView(false);
          }
        }
      },
      { threshold: thresholds },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [ref, amount, once]);

  return inView;
}
