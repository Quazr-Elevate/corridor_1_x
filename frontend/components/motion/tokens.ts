/**
 * Motion tokens — Corridor Materials.
 *
 * One curve for everything that arrives (`EASE`, the landing page's
 * cubic-bezier(0.16, 1, 0.3, 1)). Springs for things you move (`SPRING`).
 * No scale or rotation on reveals — only opacity and a short rise.
 *
 * Server-safe: no "use client", so these can be imported anywhere.
 */
export const EASE = [0.16, 1, 0.3, 1] as const;

/** The calm in-out curve used for ambient loops (drift, shimmer). */
export const EASE_CALM = [0.45, 0, 0.55, 1] as const;

/** Things you move: dock highlight, segmented thumb, sheets you drag. */
export const SPRING = { type: "spring", stiffness: 420, damping: 36 } as const;

export const DURATION = {
  /** Small UI responses: menus, listboxes, toasts. */
  quick: 0.25,
  /** Route changes. */
  route: 0.5,
  /** Content arriving on screen. */
  reveal: 0.7,
} as const;

/** Rise distance (px) for content reveals and route changes. */
export const RISE = {
  reveal: 14,
  route: 8,
} as const;

/** Delay between siblings in a <Stagger>. */
export const STAGGER = 0.06;
