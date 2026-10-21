/**
 * Still-life layout — where every grain, bean and leaf lies.
 *
 * All positions are in the shared 400 × 300 still-life viewBox. Scenes are
 * composed for `preserveAspectRatio="xMidYMid slice"`: the subject stays
 * inside x 50–350 / y 25–275, so 4:3, 1:1 and 16:10 crops all hold it.
 *
 * Light comes from the top-left and the camera looks down at ~35°, like
 * the macro photographs: far (top) is soft, the middle is sharp.
 */
import { rng } from "../ArtSvg";

export const W = 400;
export const H = 300;

export interface Item {
  x: number;
  y: number;
  /** Rotation in degrees. */
  a: number;
  /** Scale (perspective × jitter). */
  s: number;
  /** Variant index for the item kind. */
  v: number;
  /** Painter's depth: smaller draws first. */
  depth: number;
  /** Lies on a heap (smaller cast shadow, darker contact). */
  onHeap: boolean;
}

/** Perspective: things lower in frame are nearer, so a little larger. */
export const persp = (y: number) => 0.8 + (y / H) * 0.34;

function pickVariant(r: number, weights: readonly number[]) {
  const total = weights.reduce((s, w) => s + w, 0);
  let t = r * total;
  for (let i = 0; i < weights.length; i++) {
    t -= weights[i];
    if (t <= 0) return i;
  }
  return weights.length - 1;
}

export interface MoundSpec {
  cx: number;
  /** Ground line of the heap's base centre. */
  cy: number;
  rx: number;
  ry: number;
  /** Height of the peak above the base centre. */
  h: number;
  n: number;
  seed: number;
  /** Minimum spacing between item centres (screen units, before perspective). */
  gap: number;
  /** Relative weights of the item variants. */
  variants?: readonly number[];
  /** 0 = random orientation, 1 = every item follows the fall line. */
  align?: number;
  /** Base scale. */
  scale?: number;
  jitter?: number;
}

/** Top of the heap silhouette at screen x (or null outside the footprint). */
export function moundTop(m: Pick<MoundSpec, "cx" | "cy" | "rx" | "h">, x: number): number | null {
  const u = (x - m.cx) / m.rx;
  if (Math.abs(u) >= 1) return null;
  // slightly asymmetric dome: the peak sits a touch left, the right flank is longer
  const k = u < -0.08 ? Math.abs(u + 0.08) / 0.92 : (u + 0.08) / 1.08;
  return m.cy - m.h * Math.pow(1 - Math.pow(k, 1.8), 1.25);
}

/** Bottom (front base) of the heap at screen x. */
export function moundBottom(m: Pick<MoundSpec, "cx" | "cy" | "rx" | "ry">, x: number): number | null {
  const u = (x - m.cx) / m.rx;
  if (Math.abs(u) >= 1) return null;
  return m.cy + m.ry * Math.sqrt(1 - u * u);
}

/** Heap outline as a path (for shading layers). */
export function moundPath(m: MoundSpec, steps = 36): string {
  const pts: string[] = [];
  for (let i = 0; i <= steps; i++) {
    const x = m.cx - m.rx + (2 * m.rx * i) / steps;
    const y = moundTop(m, Math.min(m.cx + m.rx - 0.01, Math.max(m.cx - m.rx + 0.01, x))) ?? m.cy;
    pts.push(`${x.toFixed(1)} ${y.toFixed(1)}`);
  }
  for (let i = steps; i >= 0; i--) {
    const x = m.cx - m.rx + (2 * m.rx * i) / steps;
    const y = moundBottom(m, Math.min(m.cx + m.rx - 0.01, Math.max(m.cx - m.rx + 0.01, x))) ?? m.cy;
    pts.push(`${x.toFixed(1)} ${y.toFixed(1)}`);
  }
  return `M${pts.join("L")}Z`;
}

/** Items filling a heap, back to front. */
export function mound(m: MoundSpec): Item[] {
  const rand = rng(m.seed);
  const out: Item[] = [];
  const align = m.align ?? 0.5;
  const peakX = m.cx - m.rx * 0.08;
  const peakY = m.cy - m.h;
  let tries = 0;
  while (out.length < m.n && tries < m.n * 60) {
    tries++;
    const x = m.cx + (rand() * 2 - 1) * m.rx * 0.97;
    const top = moundTop(m, x);
    const bot = moundBottom(m, x);
    if (top == null || bot == null) continue;
    const y = top + 1.5 + rand() * (bot - top - 2.5);
    const g = m.gap * persp(y);
    if (out.some((o) => (o.x - x) ** 2 + (o.y - y) ** 2 < g * g)) continue;
    const fall = (Math.atan2(y - peakY, x - peakX) * 180) / Math.PI;
    const a = rand() < align ? fall + (rand() - 0.5) * 50 : rand() * 360;
    const t = (y - top) / Math.max(1, bot - top);
    out.push({
      x,
      y,
      a,
      s: (m.scale ?? 1) * persp(y) * (1 + (rand() - 0.5) * (m.jitter ?? 0.16)),
      v: pickVariant(rand(), m.variants ?? [1]),
      depth: m.cy - m.ry * 0.6 + t * m.ry * 1.6,
      onHeap: true,
    });
  }
  return out;
}

export interface StrewSpec {
  n: number;
  seed: number;
  gap: number;
  /** Probability (0–1) that a point is kept: shapes the scatter. */
  density: (x: number, y: number) => number;
  /** Search box. */
  box?: { x0: number; y0: number; x1: number; y1: number };
  variants?: readonly number[];
  scale?: number;
  jitter?: number;
  /** Other items to keep clear of. */
  avoid?: readonly Item[];
}

/** Loose items lying on the cloth. */
export function strew(sp: StrewSpec): Item[] {
  const rand = rng(sp.seed);
  const box = sp.box ?? { x0: -10, y0: 0, x1: W + 10, y1: H + 10 };
  const out: Item[] = [];
  const near = [...(sp.avoid ?? [])];
  let tries = 0;
  while (out.length < sp.n && tries < sp.n * 80) {
    tries++;
    const x = box.x0 + rand() * (box.x1 - box.x0);
    const y = box.y0 + rand() * (box.y1 - box.y0);
    if (rand() > sp.density(x, y)) continue;
    const g = sp.gap * persp(y);
    if (near.some((o) => (o.x - x) ** 2 + (o.y - y) ** 2 < g * g)) continue;
    const it: Item = {
      x,
      y,
      a: rand() * 360,
      s: (sp.scale ?? 1) * persp(y) * (1 + (rand() - 0.5) * (sp.jitter ?? 0.18)),
      v: pickVariant(rand(), sp.variants ?? [1]),
      depth: y,
      onHeap: false,
    };
    out.push(it);
    near.push(it);
  }
  return out;
}

/** Soft elliptical falloff, 1 at the centre → 0 at the rim. */
export function blob(cx: number, cy: number, rx: number, ry: number, power = 1.6) {
  return (x: number, y: number) => {
    const d = Math.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2);
    return d >= 1 ? 0 : Math.pow(1 - d, power);
  };
}

/** Stretch of the light direction (screen space, from the top-left). */
export const LIGHT = { x: -0.62, y: -0.78 };

/** A screen-space offset expressed in an item's local frame (rotated by `a`°). */
export function local(a: number, dx: number, dy: number): [number, number] {
  const r = (-a * Math.PI) / 180;
  const c = Math.cos(r);
  const s = Math.sin(r);
  return [dx * c - dy * s, dx * s + dy * c];
}

/**
 * Quantised angle so instances can share lit symbols. 15° steps by default;
 * round things (seeds, millet) can use coarser steps — nobody sees their
 * rotation, and fewer steps mean fewer symbols.
 */
export const ANGLE_STEP = 15;
export const quant = (a: number, step = ANGLE_STEP) => (((Math.round(a / step) * step) % 360) + 360) % 360;
