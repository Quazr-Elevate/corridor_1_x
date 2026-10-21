import { useId, type CSSProperties, type ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * The frame every drawn piece renders in. Scales from its viewBox (no
 * fixed pixel size — set a width with `className`), and is either a
 * labelled image (`title`) or decorative (`aria-hidden`).
 */
export function ArtSvg({
  viewBox,
  title,
  titleId,
  className,
  style,
  preserveAspectRatio,
  children,
}: {
  viewBox: string;
  title?: string;
  titleId: string;
  className?: string;
  style?: CSSProperties;
  preserveAspectRatio?: string;
  children: ReactNode;
}) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={viewBox}
      preserveAspectRatio={preserveAspectRatio}
      className={cn("block h-auto w-full select-none", className)}
      style={style}
      role={title ? "img" : undefined}
      aria-labelledby={title ? titleId : undefined}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      {title ? <title id={titleId}>{title}</title> : null}
      {children}
    </svg>
  );
}

/** A stable, selector-safe id prefix for gradients/filters in one instance. */
export function useArtId(prefix = "art"): string {
  const raw = useId();
  return `${prefix}-${raw.replace(/[^a-zA-Z0-9_-]/g, "")}`;
}

/** Deterministic PRNG (mulberry32) so server and client draw identical scatters. */
export function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Round to 2 decimals for compact, stable SVG attribute strings. */
export const r2 = (n: number) => Math.round(n * 100) / 100;
