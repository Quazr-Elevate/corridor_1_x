import { r2, rng } from "../ArtSvg";
import type { ArtProps } from "../tone";
import { ContactShadow, SW, isoRx, isoRy, mix } from "./core";
import { IsoFrame } from "./IsoFrame";

/**
 * A heap of long-grain rice: a bell-shaped mound on an isometric circle,
 * lit from the top-left, every grain drawn and laid along the fall line.
 */

type Grain = { x: number; y: number; a: number; l: number; t: number };

const R = 58; // base radius (world)
const H = 66; // peak height (screen units)
const RX = isoRx(R);
const RY = isoRy(R);
const PEAK_X = -RX * 0.06;

/** The silhouette: two cubics from base to peak to base, closed by the front of the base ellipse. */
const C1 = [
  [-RX, 0],
  [-RX * 0.8, -H * 0.46],
  [PEAK_X - RX * 0.4, -H],
  [PEAK_X, -H],
] as const;
const C2 = [
  [PEAK_X, -H],
  [PEAK_X + RX * 0.42, -H],
  [RX * 0.8, -H * 0.44],
  [RX, 0],
] as const;

const HEAP_D =
  `M${r2(C1[0][0])} ${r2(C1[0][1])}` +
  `C${C1.slice(1).map(([x, y]) => `${r2(x)} ${r2(y)}`).join(" ")}` +
  `C${C2.slice(1).map(([x, y]) => `${r2(x)} ${r2(y)}`).join(" ")}` +
  `A${r2(RX)} ${r2(RY)} 0 0 1 ${r2(-RX)} 0Z`;

function bez(c: readonly (readonly [number, number])[], t: number): [number, number] {
  const u = 1 - t;
  return [
    u * u * u * c[0][0] + 3 * u * u * t * c[1][0] + 3 * u * t * t * c[2][0] + t * t * t * c[3][0],
    u * u * u * c[0][1] + 3 * u * u * t * c[1][1] + 3 * u * t * t * c[2][1] + t * t * t * c[3][1],
  ];
}

/** Top of the silhouette at x, from a sampled lookup. */
const TOP = (() => {
  const pts: Array<[number, number]> = [];
  for (let i = 0; i <= 60; i++) pts.push(bez(C1, i / 60));
  for (let i = 1; i <= 60; i++) pts.push(bez(C2, i / 60));
  return (x: number) => {
    for (let i = 1; i < pts.length; i++) {
      const [x0, y0] = pts[i - 1];
      const [x1, y1] = pts[i];
      if (x >= x0 && x <= x1) return y0 + ((y1 - y0) * (x - x0)) / Math.max(1e-6, x1 - x0);
    }
    return 0;
  };
})();

const bottom = (x: number) => RY * Math.sqrt(Math.max(0, 1 - (x / RX) ** 2));

const GRAINS: Grain[] = (() => {
  const rand = rng(1121);
  const out: Grain[] = [];
  let tries = 0;
  while (out.length < 440 && tries < 30000) {
    tries++;
    const x = (rand() * 2 - 1) * RX * 0.96;
    const top = TOP(x);
    const bot = bottom(x);
    const y = top + 2 + rand() * (bot - top - 3.2);
    if (y > bot - 1.2) continue;
    if (out.some((g) => (g.x - x) ** 2 + (g.y - y) ** 2 < 10.5)) continue;
    const fall = (Math.atan2(y + H, x - PEAK_X) * 180) / Math.PI;
    out.push({
      x,
      y,
      a: fall + (rand() - 0.5) * 70,
      l: 5 + rand() * 1.4,
      // how much light the grain gets: left/upper flank bright, right/front shaded
      t: Math.min(1, Math.max(0, (x + RX) / (2 * RX) * 0.75 + (y + H) / (H + RY) * 0.35 + (rand() - 0.5) * 0.2)),
    });
  }
  return out.sort((p, q) => p.y - q.y);
})();

const SPILL: Grain[] = (() => {
  const rand = rng(77);
  const out: Grain[] = [];
  while (out.length < 22) {
    const ang = Math.PI * (0.05 + rand() * 0.9);
    const k = 1.05 + rand() * 0.32;
    const side = rand() > 0.45 ? 1 : -1;
    const x = Math.cos(ang) * RX * k * side;
    const y = Math.sin(ang) * RY * k;
    if (out.some((g) => (g.x - x) ** 2 + (g.y - y) ** 2 < 30)) continue;
    out.push({ x, y, a: rand() * 180, l: 5 + rand() * 1.2, t: 0.35 });
  }
  return out;
})();

export function IsoGrainHeap(props: ArtProps) {
  return (
    <IsoFrame {...props}>
      {({ t, id, surface }) => {
        const m = t.sand;
        const hi = surface === "tower" ? "#F1ECE1" : "#FFFFFF";
        const lo = surface === "tower" ? "#A69C88" : "#D8CCB2";
        const under = surface === "tower" ? "rgb(0 0 0 / 0.5)" : "rgb(120 100 64 / 0.35)";
        const grain = (g: Grain, dy = 0) => {
          const rad = (g.a * Math.PI) / 180;
          const dx = (Math.cos(rad) * g.l) / 2;
          const ddy = (Math.sin(rad) * g.l) / 2;
          return `M${r2(g.x - dx)} ${r2(g.y - ddy + dy)}L${r2(g.x + dx)} ${r2(g.y + ddy + dy)}`;
        };
        // bucket grains by light so each bucket is one path
        const buckets = [0, 1, 2, 3].map((b) => GRAINS.filter((g) => Math.min(3, Math.floor(g.t * 4)) === b));
        return (
          <g transform="translate(120 140)">
            <defs>
              <linearGradient id={id("body")} x1="0" y1="0" x2="1" y2="0.4">
                <stop offset="0" stopColor={mix(m.top, m.left, 0.15)} />
                <stop offset="0.55" stopColor={m.left} />
                <stop offset="1" stopColor={m.right} />
              </linearGradient>
              <clipPath id={id("clip")}>
                <path d={HEAP_D} />
              </clipPath>
            </defs>
            <ContactShadow c={[0, 0]} rx={RX * 1.25} ry={RY * 1.1} gradId={id("sh")} dx={10} />
            <path d={HEAP_D} fill={`url(#${id("body")})`} />
            <g clipPath={`url(#${id("clip")})`} strokeLinecap="round" fill="none">
              <path d={GRAINS.map((g) => grain(g, 0.8)).join("")} stroke={under} strokeWidth={2.4} />
              {buckets.map((b, i) => (
                <path key={i} d={b.map((g) => grain(g)).join("")} stroke={mix(hi, lo, i / 3)} strokeWidth={2} />
              ))}
            </g>
            <path d={HEAP_D} fill="none" stroke={m.edge} strokeWidth={SW} strokeLinejoin="round" />
            {/* loose grains around the base */}
            <g strokeLinecap="round" fill="none">
              <path d={SPILL.map((g) => grain(g, 1)).join("")} stroke={under} strokeWidth={2.4} />
              <path d={SPILL.map((g) => grain(g)).join("")} stroke={m.edge} strokeWidth={2.7} />
              <path d={SPILL.map((g) => grain(g)).join("")} stroke={mix(hi, lo, 0.3)} strokeWidth={1.9} />
            </g>
          </g>
        );
      }}
    </IsoFrame>
  );
}
