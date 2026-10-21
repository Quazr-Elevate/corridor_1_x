/**
 * Greedy label placement in screen pixels: each label tries its preferred
 * compass directions at growing distances and takes the first spot that
 * stays inside the map and clears every placed label, every port marker
 * and every caption. Runs on the server at a nominal size and again on the
 * client at the real size, so labels never overlap at any width.
 */

export type Dir = "n" | "ne" | "e" | "se" | "s" | "sw" | "w" | "nw";

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface LabelInput {
  id: string;
  /** Anchor (the port) in px. */
  x: number;
  y: number;
  w: number;
  h: number;
  prefer: readonly Dir[];
}

export interface Placed {
  id: string;
  rect: Rect;
  /** Leader from the anchor to the label edge, when the label sits away from it. */
  leader: [number, number, number, number] | null;
}

const UNIT: Record<Dir, [number, number]> = {
  n: [0, -1],
  ne: [1, -1],
  e: [1, 0],
  se: [1, 1],
  s: [0, 1],
  sw: [-1, 1],
  w: [-1, 0],
  nw: [-1, -1],
};
const ALL: Dir[] = ["e", "w", "n", "s", "ne", "nw", "se", "sw"];
const DISTANCES = [8, 16, 26, 38, 52, 70];

function rectAt(ax: number, ay: number, w: number, h: number, dir: Dir, d: number): Rect {
  const [ux, uy] = UNIT[dir];
  const diag = ux !== 0 && uy !== 0 ? 0.72 : 1;
  const px = ax + ux * d * diag;
  const py = ay + uy * d * diag;
  const x = ux > 0 ? px : ux < 0 ? px - w : px - w / 2;
  const y = uy > 0 ? py : uy < 0 ? py - h : py - h / 2;
  return { x, y, w, h };
}

const hit = (a: Rect, b: Rect, pad: number) =>
  a.x < b.x + b.w + pad && b.x < a.x + a.w + pad && a.y < b.y + b.h + pad && b.y < a.y + a.h + pad;

function overlapArea(a: Rect, b: Rect) {
  const w = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
  const h = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
  return w > 0 && h > 0 ? w * h : 0;
}

function leaderTo(ax: number, ay: number, r: Rect, d: number): Placed["leader"] {
  if (d < 14) return null;
  const ex = Math.min(Math.max(ax, r.x), r.x + r.w);
  const ey = Math.min(Math.max(ay, r.y), r.y + r.h);
  const len = Math.hypot(ex - ax, ey - ay);
  if (len < 8) return null;
  // start just outside the marker
  const k = 6 / len;
  return [ax + (ex - ax) * k, ay + (ey - ay) * k, ex, ey];
}

export function layoutLabels(
  labels: readonly LabelInput[],
  obstacles: readonly Rect[],
  bounds: { w: number; h: number },
  margin = 4,
): Placed[] {
  const placed: Placed[] = [];
  const taken: Rect[] = [];
  for (const L of labels) {
    const dirs = [...L.prefer, ...ALL.filter((d) => !L.prefer.includes(d))];
    // every candidate, cheapest first: near beats far, preferred beats not
    const candidates = DISTANCES.flatMap((d) =>
      dirs.map((dir, rank) => ({ rect: rectAt(L.x, L.y, L.w, L.h, dir, d), d, cost: d + rank * 12 })),
    ).sort((a, b) => a.cost - b.cost);
    const fits = (r: Rect) =>
      r.x >= margin && r.y >= margin && r.x + r.w <= bounds.w - margin && r.y + r.h <= bounds.h - margin;
    let best = candidates.find(
      (c) => fits(c.rect) && !taken.some((t) => hit(c.rect, t, 3)) && !obstacles.some((o) => hit(c.rect, o, 2)),
    );
    if (!best) {
      // nothing is clear: take the least-bad spot that stays inside the map
      let bestCost = Infinity;
      for (const c of candidates) {
        const cost =
          (fits(c.rect) ? 0 : 1e6) +
          taken.reduce((s, t) => s + overlapArea(c.rect, t), 0) * 4 +
          obstacles.reduce((s, o) => s + overlapArea(c.rect, o), 0) +
          c.cost;
        if (cost < bestCost) {
          bestCost = cost;
          best = c;
        }
      }
    }
    const { rect, d } = best!;
    taken.push(rect);
    placed.push({ id: L.id, rect, leader: leaderTo(L.x, L.y, rect, d) });
  }
  return placed;
}
