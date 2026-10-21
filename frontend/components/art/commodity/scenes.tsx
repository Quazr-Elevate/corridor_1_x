import type { ReactNode } from "react";
import { rng } from "../ArtSvg";
import {
  blob,
  mound,
  moundBottom,
  moundPath,
  moundTop,
  strew,
  type Item,
  type MoundSpec,
} from "./layout";
import { as, Focus, Items, KindDefs, SAND, type Gid, type Placed } from "./StillLife";
import {
  coffeeBean,
  mustard,
  peanutKernel,
  peanutShell,
  pearlMillet,
  ragi,
  riceGrain,
  sesame,
  splitPulse,
  teaCurl,
} from "./kinds";

export type ArtCategory = "Oilseeds" | "Cotton" | "Millets" | "Tea" | "Coffee" | "Other";

/* ── shared pieces ───────────────────────────────────────────────── */

const f = (n: number) => n.toFixed(1);

/** Keep strewn items off a heap's footprint (+ a margin). */
function off(m: MoundSpec, margin: number, d: (x: number, y: number) => number) {
  return (x: number, y: number) => {
    const top = moundTop({ ...m, rx: m.rx + margin }, x);
    const bot = moundBottom({ ...m, rx: m.rx + margin, ry: m.ry + margin }, x);
    if (top != null && bot != null && y > top - margin && y < bot + margin * 0.6) return 0;
    return d(x, y);
  };
}

/** Soft contact shadow under a heap, plus the dark mass that shows between items. */
function HeapUnder({ m, gid, mass, k = 1 }: { m: MoundSpec; gid: Gid; mass: string; k?: number }) {
  return (
    <>
      <ellipse
        cx={f(m.cx + 14)}
        cy={f(m.cy + m.ry * 0.35)}
        rx={f(m.rx * 1.1)}
        ry={f(m.ry * 1.3)}
        fill={SAND.shade}
        opacity={0.5 * k}
        filter={`url(#${gid("soft")})`}
      />
      <path d={moundPath({ ...m, rx: m.rx * 0.97, ry: m.ry * 0.9, h: m.h * 0.97 })} fill={mass} />
    </>
  );
}

/** Top-left light across a heap: the far flank brighter, the near-right flank in shade. */
function HeapLight({ m, gid, shade = 0.34, lift = 0.16 }: { m: MoundSpec; gid: Gid; shade?: number; lift?: number }) {
  const id = gid(`hl-${Math.round(m.cx)}-${Math.round(m.cy)}`);
  return (
    <>
      <defs>
        <linearGradient id={id} gradientUnits="userSpaceOnUse" x1={m.cx - m.rx * 0.6} y1={m.cy - m.h} x2={m.cx + m.rx * 0.7} y2={m.cy + m.ry}>
          <stop offset="0" stopColor="#FFF6E4" stopOpacity={lift} />
          <stop offset="0.45" stopColor="#FFF6E4" stopOpacity={0} />
          <stop offset="0.7" stopColor="#24140A" stopOpacity={shade * 0.4} />
          <stop offset="1" stopColor="#24140A" stopOpacity={shade} />
        </linearGradient>
      </defs>
      <path d={moundPath(m)} fill={`url(#${id})`} />
    </>
  );
}

/* ── Coffee ──────────────────────────────────────────────────────── */

function coffee(seed: number) {
  const heap: MoundSpec = { cx: 268, cy: 214, rx: 214, ry: 62, h: 168, n: 150, seed: 11 + seed, gap: 21.5, variants: [3, 2], align: 0.3, scale: 1.72 };
  const items = mound(heap);
  const loose = strew({
    n: 8,
    seed: 23 + seed,
    gap: 44,
    box: { x0: -10, y0: 222, x1: 250, y1: 312 },
    density: off(heap, 14, (x, y) => blob(100, 266, 170, 70)(x, y)),
    variants: [1, 1],
    scale: 1.72,
    avoid: items,
  });
  const far = strew({ n: 5, seed: 37 + seed, gap: 46, box: { x0: -20, y0: 6, x1: 120, y1: 74 }, density: blob(30, 34, 120, 50, 0.6), scale: 1.6 });
  return { heap, near: [...as(coffeeBean, items), ...as(coffeeBean, loose), ...as(coffeeBean, far)] };
}

/* ── Tea ─────────────────────────────────────────────────────────── */

function tea(seed: number) {
  const heap: MoundSpec = { cx: 274, cy: 206, rx: 206, ry: 58, h: 156, n: 240, seed: 41 + seed, gap: 13, variants: [3, 3, 2, 1], align: 0.25, scale: 1.7 };
  const items = mound(heap);
  const loose = strew({
    n: 12,
    seed: 53 + seed,
    gap: 24,
    box: { x0: 190, y0: 238, x1: 410, y1: 306 },
    density: off(heap, 8, (x, y) => blob(320, 274, 140, 56)(x, y)),
    variants: [3, 3, 2, 2],
    scale: 1.7,
    avoid: items,
  });
  const far = strew({ n: 8, seed: 61 + seed, gap: 26, box: { x0: -20, y0: 6, x1: 110, y1: 70 }, density: blob(30, 30, 110, 44, 0.6), variants: [3, 3, 2, 1], scale: 1.6 });
  return { heap, near: [...as(teaCurl, items), ...as(teaCurl, loose), ...as(teaCurl, far)] };
}

/** Serrated camellia leaf along +x from its base. */
function leafD(len: number, wid: number, seed: number) {
  const rand = rng(seed);
  const N = 30;
  const top: string[] = [];
  const bot: string[] = [];
  for (let i = 0; i <= N; i++) {
    const t = i / N;
    const w = wid * Math.pow(Math.sin(Math.PI * Math.pow(t, 0.82)), 0.85) * (1 - 0.12 * t);
    const tooth = t > 0.12 && t < 0.94 ? (i % 2 === 0 ? 0.9 : -0.2) * (0.6 + rand() * 0.5) : 0;
    top.push(`${f(t * len + (i % 2 ? 0.6 : 0))} ${f(-(w + tooth))}`);
    bot.unshift(`${f(t * len + (i % 2 ? 0.6 : 0))} ${f(w + tooth * 0.9)}`);
  }
  return `M0 0L${top.join("L")}L${bot.join("L")}Z`;
}

function leafVeins(len: number, wid: number) {
  let d = `M0 0Q${f(len / 2)} ${f(-wid * 0.08)} ${f(len)} 0`;
  for (let t = 0.16; t < 0.86; t += 0.105) {
    const x = t * len;
    const w = wid * Math.sin(Math.PI * Math.pow(t, 0.82)) * 0.78;
    d += `M${f(x)} ${f(-wid * 0.04)}Q${f(x + len * 0.05)} ${f(-w * 0.55)} ${f(x + len * 0.13)} ${f(-w)}`;
    d += `M${f(x)} ${f(wid * 0.02)}Q${f(x + len * 0.05)} ${f(w * 0.55)} ${f(x + len * 0.13)} ${f(w)}`;
  }
  return d;
}

/** "Two leaves and a bud" lying on the cloth. */
function TeaSprig({ gid }: { gid: Gid }) {
  const leaves = [
    { at: 34, ang: -34, len: 74, wid: 15, seed: 3, dark: false },
    { at: 70, ang: 30, len: 62, wid: 13, seed: 5, dark: true },
  ];
  const sprig = (
    <>
      <path d="M-6 3C30 1 70 -1 104 -1" fill="none" stroke="#6C6A30" strokeWidth={3} strokeLinecap="round" />
      <path d="M-6 2C30 0 70 -2 104 -2" fill="none" stroke="#A6A86A" strokeOpacity={0.5} strokeWidth={0.9} strokeLinecap="round" />
      {leaves.map((l, i) => (
        <g key={i} transform={`translate(${l.at} 0) rotate(${l.ang})`}>
          <path d={leafD(l.len, l.wid, l.seed)} fill={`url(#${gid(l.dark ? "leafB" : "leafA")})`} />
          <path d={leafVeins(l.len, l.wid)} fill="none" stroke="#C9D08C" strokeOpacity={0.42} strokeWidth={0.7} strokeLinecap="round" />
          <path d={leafD(l.len, l.wid, l.seed)} fill="none" stroke="#2C330A" strokeOpacity={0.35} strokeWidth={0.5} />
        </g>
      ))}
      {/* the bud: slim, silvery */}
      <g transform="translate(100 -1) rotate(-8)">
        <path d="M0 0C6 -4.2 18 -4.4 34 -0.6C18 3.6 6 3.8 0 0Z" fill={`url(#${gid("bud")})`} />
        <path d="M2 -0.2C10 -2 20 -2 32 -0.6" fill="none" stroke="#FFFFFF" strokeOpacity={0.4} strokeWidth={0.8} />
      </g>
    </>
  );
  return (
    <g transform="translate(14 296) rotate(-27) scale(1.55)">
      <defs>
        <linearGradient id={gid("leafA")} x1="0" y1="0" x2="0.3" y2="1">
          <stop offset="0" stopColor="#97A54E" />
          <stop offset="0.5" stopColor="#66741F" />
          <stop offset="1" stopColor="#3E4810" />
        </linearGradient>
        <linearGradient id={gid("leafB")} x1="0" y1="0" x2="0.3" y2="1">
          <stop offset="0" stopColor="#7F8D38" />
          <stop offset="0.55" stopColor="#55620E" />
          <stop offset="1" stopColor="#343D0A" />
        </linearGradient>
        <linearGradient id={gid("bud")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#D6DCAE" />
          <stop offset="1" stopColor="#7E8A44" />
        </linearGradient>
      </defs>
      <g transform="translate(4 7)" opacity={0.38} filter={`url(#${gid("soft")})`}>
        <g fill="#3B2A14" stroke="#3B2A14">
          {sprig}
        </g>
      </g>
      {sprig}
    </g>
  );
}

/* ── Cotton ──────────────────────────────────────────────────────── */

interface Boll {
  cx: number;
  cy: number;
  r: number;
  rot: number;
  seed: number;
  bract?: boolean;
}

function blobD(cx: number, cy: number, r: number, rand: () => number, squash = 0.86) {
  const p = [rand() * 6, rand() * 6, rand() * 6];
  const pts: Array<[number, number]> = [];
  const N = 13;
  for (let i = 0; i < N; i++) {
    const t = (i / N) * Math.PI * 2;
    const rr = r * (1 + 0.07 * Math.sin(3 * t + p[0]) + 0.05 * Math.sin(5 * t + p[1]) + 0.03 * Math.sin(8 * t + p[2]));
    pts.push([cx + Math.cos(t) * rr, cy + Math.sin(t) * rr * squash]);
  }
  // closed Catmull–Rom
  let d = `M${f(pts[0][0])} ${f(pts[0][1])}`;
  for (let i = 0; i < N; i++) {
    const p0 = pts[(i - 1 + N) % N];
    const p1 = pts[i];
    const p2 = pts[(i + 1) % N];
    const p3 = pts[(i + 2) % N];
    d += `C${f(p1[0] + (p2[0] - p0[0]) / 6)} ${f(p1[1] + (p2[1] - p0[1]) / 6)} ${f(p2[0] - (p3[0] - p1[0]) / 6)} ${f(p2[1] - (p3[1] - p1[1]) / 6)} ${f(p2[0])} ${f(p2[1])}`;
  }
  return `${d}Z`;
}

function CottonBoll({ b, gid }: { b: Boll; gid: Gid }) {
  const rand = rng(b.seed);
  // four locks, each a cluster of three soft puffs
  const puffs = Array.from({ length: 4 }, (_, k) => {
    const t = ((b.rot + k * 90 + (rand() - 0.5) * 16) * Math.PI) / 180;
    const d = b.r * (0.42 + rand() * 0.06);
    const rl = b.r * (0.5 + rand() * 0.06);
    const [ux, uy] = [Math.cos(t), Math.sin(t) * 0.78];
    const [nx, ny] = [-uy, ux];
    const cx = b.cx + ux * d;
    const cy = b.cy + uy * d;
    return [
      { cx: cx - ux * rl * 0.12, cy: cy - uy * rl * 0.12, r: rl * 0.92 },
      { cx: cx + nx * rl * 0.42 + ux * rl * 0.22, cy: cy + ny * rl * 0.42 + uy * rl * 0.22, r: rl * 0.64 },
      { cx: cx - nx * rl * 0.4 + ux * rl * 0.26, cy: cy - ny * rl * 0.4 + uy * rl * 0.26, r: rl * 0.6 },
    ];
  })
    .flat()
    .map((p) => {
      let silk = "";
      for (let i = 0; i < 4; i++) {
        const rr = p.r * (0.35 + rand() * 0.45);
        const a0 = rand() * Math.PI * 2;
        const a1 = a0 + 0.6 + rand() * 1.1;
        silk += `M${f(p.cx + Math.cos(a0) * rr)} ${f(p.cy + Math.sin(a0) * rr * 0.86)}A${f(rr)} ${f(rr * 0.86)} 0 0 1 ${f(p.cx + Math.cos(a1) * rr)} ${f(p.cy + Math.sin(a1) * rr * 0.86)}`;
      }
      return { ...p, d: blobD(p.cx, p.cy, p.r, rand), silk };
    })
    .sort((p, q) => p.cy + p.r * 0.3 - (q.cy + q.r * 0.3));
  // the dry burr: one pointed carpel wall between each pair of locks
  const sepals = Array.from({ length: 4 }, (_, k) => {
    const t = ((b.rot + 45 + k * 90 + (rand() - 0.5) * 14) * Math.PI) / 180;
    const len = b.r * (1.18 + rand() * 0.14);
    const w = b.r * 0.3;
    const [ux, uy] = [Math.cos(t), Math.sin(t) * 0.8];
    const [nx, ny] = [-uy, ux];
    const curl = (rand() - 0.5) * b.r * 0.3;
    const P = (along: number, side: number): string =>
      `${f(b.cx + ux * len * along + nx * side)} ${f(b.cy + uy * len * along + ny * side)}`;
    return {
      d:
        `M${P(0, w)}C${P(0.32, w * 1.05)} ${P(0.62, w * 0.3 + curl * 0.35)} ${P(1, curl)}` +
        `C${P(0.66, -w * 0.2 + curl * 0.45)} ${P(0.34, -w * 0.95)} ${P(0, -w)}Z`,
      // the half that curls up into the light
      lit:
        `M${P(0, w)}C${P(0.32, w * 1.05)} ${P(0.62, w * 0.3 + curl * 0.35)} ${P(1, curl)}` +
        `Q${P(0.6, curl * 0.3)} ${P(0.2, 0)}Z`,
      rib: `M${P(0.3, 0)}Q${P(0.66, curl * 0.25)} ${P(0.95, curl * 0.85)}`,
    };
  });
  const id = (k: string) => gid(`boll${b.seed}-${k}`);
  return (
    <g>
      <defs>
        <radialGradient id={id("sepal")} gradientUnits="userSpaceOnUse" cx={b.cx - b.r * 0.5} cy={b.cy - b.r * 0.6} r={b.r * 1.9}>
          <stop offset="0" stopColor="#A6845A" />
          <stop offset="0.5" stopColor="#6E4E2E" />
          <stop offset="1" stopColor="#3A2614" />
        </radialGradient>
        {puffs.map((p, i) => (
          <radialGradient key={i} id={id(`p${i}`)} gradientUnits="userSpaceOnUse" cx={p.cx - p.r * 0.36} cy={p.cy - p.r * 0.44} r={p.r * 1.42}>
            <stop offset="0" stopColor="#FFFFFF" />
            <stop offset="0.38" stopColor="#FBF8F0" />
            <stop offset="0.7" stopColor="#ECE3D0" />
            <stop offset="0.9" stopColor="#D2C3A4" />
            <stop offset="1" stopColor="#B7A480" />
          </radialGradient>
        ))}
      </defs>
      {/* cast shadow */}
      <ellipse cx={f(b.cx + b.r * 0.22)} cy={f(b.cy + b.r * 0.62)} rx={f(b.r * 1.08)} ry={f(b.r * 0.42)} fill={SAND.shade} opacity={0.5} filter={`url(#${gid("soft")})`} />
      {b.bract !== false
        ? sepals.map((sp, i) => (
            <g key={i}>
              <path d={sp.d} fill={`url(#${id("sepal")})`} stroke="#2A1A0C" strokeOpacity={0.4} strokeWidth={0.7} />
              <path d={sp.lit} fill="#C9A878" opacity={0.28} />
              <path d={sp.rib} fill="none" stroke="#2A1A0C" strokeOpacity={0.35} strokeWidth={0.8} strokeLinecap="round" />
            </g>
          ))
        : null}
      <defs>
        {puffs.map((p, i) => (
          <path key={i} id={id(`d${i}`)} d={p.d} />
        ))}
      </defs>
      <g filter={`url(#${gid("fluff")})`}>
        {puffs.map((_, i) => (
          <g key={i}>
            <use href={`#${id(`d${i}`)}`} fill="#7A6644" opacity={0.3} transform="translate(1.4 2.2)" />
            <use href={`#${id(`d${i}`)}`} fill={`url(#${id(`p${i}`)})`} />
          </g>
        ))}
        <path
          d={puffs.map((p) => p.silk).join("")}
          fill="none"
          stroke="#A8987A"
          strokeOpacity={0.14}
          strokeWidth={1}
          strokeLinecap="round"
        />
      </g>
    </g>
  );
}

/* ── Millets ─────────────────────────────────────────────────────── */

function millets(seed: number) {
  const heap: MoundSpec = { cx: 272, cy: 204, rx: 204, ry: 56, h: 150, n: 280, seed: 71 + seed, gap: 14, variants: [5, 3, 2], align: 0.1, scale: 2.2 };
  const items = mound(heap);
  const loose = strew({
    n: 22,
    seed: 83 + seed,
    gap: 17,
    box: { x0: 200, y0: 232, x1: 410, y1: 306 },
    density: off(heap, 6, (x, y) => blob(330, 268, 120, 50)(x, y)),
    variants: [5, 3, 2],
    scale: 2.2,
    avoid: items,
  });
  const back: MoundSpec = { cx: 24, cy: 76, rx: 120, ry: 26, h: 62, n: 80, seed: 91 + seed, gap: 10.5, scale: 2.6 };
  const far = mound(back);
  return { heap, back, near: [...as(pearlMillet, items), ...as(pearlMillet, loose), ...as(ragi, far)] };
}

/** A pearl-millet head lying across the front, its grains in rows. */
function MilletSpike({ gid }: { gid: Gid }) {
  const L = 168;
  const R = 13;
  const rand = rng(5);
  const tones = ["#7E6844", "#A48C5C", "#C9B07E", "#E2CDA0", "#D2BB8C", "#A9915F", "#7A6440"];
  const grains: ReactNode[] = [];
  let row = 0;
  for (let x = 8; x < L - 6; x += 4.6, row++) {
    const taper = Math.min(1, x / 26, (L - x) / 30);
    const r = R * (0.55 + 0.45 * Math.sqrt(Math.max(0, taper)));
    for (let k = -3; k <= 3; k++) {
      const th = ((k + (row % 2 ? 0.5 : 0)) / 3.6) * (Math.PI / 2);
      if (Math.abs(th) > Math.PI / 2 - 0.12) continue;
      const y = Math.sin(th) * r;
      const lit = Math.cos(th + 0.55); // light from the upper side
      const tone = tones[Math.max(0, Math.min(tones.length - 1, Math.round(3 + lit * 2.4 - Math.abs(Math.sin(th)) * 1.6)))];
      grains.push(
        <ellipse key={`${row}-${k}`} cx={f(x + (rand() - 0.5) * 0.8)} cy={f(y)} rx={2.5} ry={f(2.4 * Math.max(0.45, Math.cos(th)))} fill={tone} />,
      );
    }
  }
  const body = `M0 0C0 -${R * 0.6} 18 -${R} 40 -${R}L${L - 32} -${R * 0.95}C${L - 10} -${R * 0.8} ${L} -${R * 0.3} ${L + 2} 0C${L} ${R * 0.3} ${L - 10} ${R * 0.8} ${L - 32} ${R * 0.95}L40 ${R}C18 ${R} 0 ${R * 0.6} 0 0Z`;
  return (
    <g transform="translate(-6 300) rotate(-17) scale(1.45)">
      <defs>
        <linearGradient id={gid("spike")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#B49A68" />
          <stop offset="0.5" stopColor="#8A7246" />
          <stop offset="1" stopColor="#56442A" />
        </linearGradient>
        <linearGradient id={gid("stalk")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#E3D2A6" />
          <stop offset="0.5" stopColor="#BCA16C" />
          <stop offset="1" stopColor="#8A7044" />
        </linearGradient>
      </defs>
      <g transform="translate(5 9)" opacity={0.45} filter={`url(#${gid("soft")})`}>
        <path d={body} fill="#3B2A14" />
      </g>
      {/* stalk out of frame to the left */}
      <path d="M2 -3.2L-90 6L-90 13L2 3.4Z" fill={`url(#${gid("stalk")})`} />
      <path d="M0 -2.6L-90 6.4" stroke="#FFFFFF" strokeOpacity={0.45} strokeWidth={0.8} />
      <path d={body} fill={`url(#${gid("spike")})`} />
      <g stroke="#5A4626" strokeOpacity={0.35} strokeWidth={0.35}>
        {grains}
      </g>
      {/* bristles along the silhouette */}
      <path
        d={Array.from({ length: 40 }, (_, i) => {
          const x = 10 + i * 4;
          const s = i % 2 ? -1 : 1;
          return `M${x} ${s * (R - 1)}l${f(1.4 + rand())} ${f(s * (2.4 + rand() * 1.6))}`;
        }).join("")}
        stroke="#6E5A36"
        strokeOpacity={0.55}
        strokeWidth={0.5}
        strokeLinecap="round"
      />
    </g>
  );
}

/* ── Oilseeds ────────────────────────────────────────────────────── */

function oilseeds(seed: number) {
  const heap: MoundSpec = { cx: 276, cy: 204, rx: 200, ry: 58, h: 152, n: 150, seed: 101 + seed, gap: 18.6, variants: [4, 1], align: 0.3, scale: 2 };
  const items = mound(heap);
  const shells = strew({
    n: 2,
    seed: 113 + seed,
    gap: 70,
    box: { x0: 0, y0: 236, x1: 150, y1: 292 },
    density: off(heap, 16, (x, y) => blob(60, 264, 130, 50, 0.6)(x, y)),
    scale: 1.9,
    avoid: items,
  });
  const kernels = strew({
    n: 5,
    seed: 127 + seed,
    gap: 34,
    box: { x0: 220, y0: 236, x1: 410, y1: 306 },
    density: off(heap, 10, (x, y) => blob(330, 270, 120, 50)(x, y)),
    variants: [3, 1],
    scale: 2,
    avoid: [...items, ...shells],
  });
  const seeds = strew({
    n: 46,
    seed: 131 + seed,
    gap: 11,
    box: { x0: -10, y0: 130, x1: 200, y1: 300 },
    density: off(heap, 6, (x, y) => blob(40, 210, 150, 90, 0.9)(x, y)),
    variants: [5, 1],
    scale: 2.3,
    avoid: [...items, ...shells],
  });
  const sesameSeeds = strew({
    n: 16,
    seed: 139 + seed,
    gap: 13,
    box: { x0: 250, y0: 252, x1: 410, y1: 306 },
    density: blob(340, 284, 100, 34),
    scale: 2.2,
    avoid: [...items, ...shells, ...kernels],
  });
  const far = strew({ n: 6, seed: 149 + seed, gap: 40, box: { x0: -20, y0: 6, x1: 110, y1: 70 }, density: blob(30, 30, 110, 44, 0.6), variants: [4, 1], scale: 1.9 });
  return {
    heap,
    near: [
      ...as(peanutKernel, items),
      ...as(peanutShell, shells),
      ...as(peanutKernel, kernels),
      ...as(mustard, seeds),
      ...as(sesame, sesameSeeds),
      ...as(peanutKernel, far),
    ],
  };
}

/* ── Other: a wooden sampling scoop of mixed grain ───────────────── */

const SCOOP = { cx: 262, cy: 146, rot: -6, orx: 140, ory: 74, wall: 19, irx: 124, iry: 61 };

function scoopContents(seed: number): Item[] {
  const rand = rng(161 + seed);
  const out: Item[] = [];
  const kinds = [5, 3, 1.4];
  const total = kinds.reduce((s, k) => s + k, 0);
  const t = (SCOOP.rot * Math.PI) / 180;
  let tries = 0;
  while (out.length < 190 && tries < 12000) {
    tries++;
    const u = rand() * 2 - 1;
    const v = rand() * 2 - 1;
    if (u * u + v * v > 0.92) continue;
    const lx = u * SCOOP.irx;
    const ly = v * SCOOP.iry + 3;
    const dome = 30 * (1 - (u * u + v * v));
    const x = SCOOP.cx + lx * Math.cos(t) - ly * Math.sin(t);
    const y = SCOOP.cy + lx * Math.sin(t) + ly * Math.cos(t) - dome;
    if (out.some((o) => (o.x - x) ** 2 + (o.y - y) ** 2 < 96)) continue;
    let r = rand() * total;
    let kind = 0;
    while (kind < kinds.length - 1 && r > kinds[kind]) r -= kinds[kind++];
    out.push({ x, y, a: rand() * 360, s: 1.75 + (rand() - 0.5) * 0.2, v: kind, depth: y + dome, onHeap: true });
  }
  return out;
}

function other(seed: number) {
  const contents = scoopContents(seed);
  const pick = (k: number) => contents.filter((c) => c.v === k).map((c) => ({ ...c, v: 0 }));
  const mixRand = rng(171 + seed);
  const spill = strew({
    n: 22,
    seed: 173 + seed,
    gap: 15,
    box: { x0: 190, y0: 248, x1: 410, y1: 306 },
    density: blob(320, 282, 130, 40),
    scale: 1.9,
  }).map((it) => ({ ...it, v: mixRand() < 0.5 ? 0 : mixRand() < 0.65 ? 1 : 2 }));
  const spillOf = (k: number) => spill.filter((c) => c.v === k).map((c) => ({ ...c, v: 0 }));
  return {
    inside: [...as(riceGrain, pick(0)), ...as(splitPulse, pick(1)), ...as(mustard, pick(2))],
    near: [...as(riceGrain, spillOf(0)), ...as(splitPulse, spillOf(1)), ...as(mustard, spillOf(2))],
  };
}

function ellipseD(cx: number, cy: number, rx: number, ry: number) {
  return `M${f(cx - rx)} ${f(cy)}A${f(rx)} ${f(ry)} 0 1 0 ${f(cx + rx)} ${f(cy)}A${f(rx)} ${f(ry)} 0 1 0 ${f(cx - rx)} ${f(cy)}Z`;
}

function Scoop({ gid, children }: { gid: Gid; children: ReactNode }) {
  const { cx, cy, rot, orx, ory, wall, irx, iry } = SCOOP;
  // wall band: outer rim ellipse swept down by `wall`
  const wallD = `M${f(cx - orx)} ${f(cy)}A${orx} ${ory} 0 0 0 ${f(cx + orx)} ${f(cy)}L${f(cx + orx * 0.97)} ${f(cy + wall)}A${f(orx * 0.97)} ${ory} 0 0 1 ${f(cx - orx * 0.97)} ${f(cy + wall)}Z`;
  const inner = ellipseD(cx, cy + 3, irx, iry);
  // grain may heap above the rim, never over the front lip
  const contentsClip = `M${f(cx - irx)} ${f(cy + 3)}A${irx} ${iry} 0 0 0 ${f(cx + irx)} ${f(cy + 3)}L${f(cx + irx)} ${f(cy - 60)}L${f(cx - irx)} ${f(cy - 60)}Z`;
  return (
    <g>
      <defs>
        <linearGradient id={gid("wood")} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#E2C596" />
          <stop offset="0.5" stopColor="#BF9862" />
          <stop offset="1" stopColor="#8E6A3A" />
        </linearGradient>
        <linearGradient id={gid("woodWall")} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#B08A56" />
          <stop offset="0.6" stopColor="#8A6436" />
          <stop offset="1" stopColor="#5E4220" />
        </linearGradient>
        <radialGradient id={gid("bowl")} cx="0.66" cy="0.74" r="0.9">
          <stop offset="0" stopColor="#C29A64" />
          <stop offset="0.6" stopColor="#8E6A3E" />
          <stop offset="1" stopColor="#5A3F1E" />
        </radialGradient>
        <linearGradient id={gid("handle")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#E0C391" />
          <stop offset="0.45" stopColor="#B88E58" />
          <stop offset="1" stopColor="#7A5A30" />
        </linearGradient>
        <clipPath id={gid("contents")}>
          <path d={contentsClip} transform={`rotate(${rot} ${cx} ${cy})`} />
        </clipPath>
      </defs>
      {/* shadows */}
      <ellipse cx={cx + 22} cy={cy + 52} rx={orx * 1.05} ry={ory * 0.72} fill={SAND.shade} opacity={0.55} filter={`url(#${gid("soft")})`} />
      <path d="M140 196L-20 276" stroke={SAND.shade} strokeOpacity={0.4} strokeWidth={30} strokeLinecap="round" filter={`url(#${gid("soft")})`} />
      {/* handle, running out of frame to the lower left */}
      <g>
        <path d="M150 156L-30 246L-22 270L162 186Z" fill={`url(#${gid("handle")})`} />
        <path d="M150 166L-26 254M140 176L-24 262" stroke="#6E4E26" strokeOpacity={0.22} strokeWidth={0.9} />
        <path d="M150 157L-30 247" stroke="#FFF4DE" strokeOpacity={0.55} strokeWidth={1.4} strokeLinecap="round" />
      </g>
      <g transform={`rotate(${rot} ${cx} ${cy})`}>
        <path d={wallD} fill={`url(#${gid("woodWall")})`} />
        <path d={ellipseD(cx, cy, orx, ory)} fill={`url(#${gid("wood")})`} />
        <path d={inner} fill={`url(#${gid("bowl")})`} />
        {/* rim highlight on the far lip */}
        <path d={`M${f(cx - orx + 4)} ${f(cy - 2)}A${orx - 4} ${ory - 3} 0 0 1 ${f(cx + orx - 4)} ${f(cy - 2)}`} fill="none" stroke="#FFF2DA" strokeOpacity={0.55} strokeWidth={1.2} />
      </g>
      <g clipPath={`url(#${gid("contents")})`}>{children}</g>
    </g>
  );
}

/* ── scene table ─────────────────────────────────────────────────── */

const cache = new Map<string, ReturnType<typeof build>>();

function build(cat: ArtCategory, seed: number) {
  switch (cat) {
    case "Coffee":
      return { kind: "heap" as const, ...coffee(seed), mass: "#24130A" };
    case "Tea":
      return { kind: "heap" as const, ...tea(seed), mass: "#1A120A" };
    case "Millets":
      return { kind: "heap" as const, ...millets(seed), mass: "#7E6844" };
    case "Oilseeds":
      return { kind: "heap" as const, ...oilseeds(seed), mass: "#4A2410" };
    case "Cotton":
      return { kind: "cotton" as const };
    case "Other":
      return { kind: "scoop" as const, ...other(seed) };
  }
}

function scene(cat: ArtCategory, seed: number) {
  const key = `${cat}:${seed}`;
  let s = cache.get(key);
  if (!s) {
    s = build(cat, seed);
    cache.set(key, s);
  }
  return s;
}

/** Everything drawn for one category, between the ground and the grain. */
export function Scene({ category, seed, gid }: { category: ArtCategory; seed: number; gid: Gid }) {
  const s = scene(category, seed);

  if (s.kind === "cotton") {
    const r = rng(181 + seed);
    const j = () => (r() - 0.5) * 10;
    return (
      <>
        <defs>
          {/* fibrous silhouette, smooth inside: displace only the alpha, then fill it */}
          <filter id={gid("fluff")} x="-25%" y="-25%" width="150%" height="150%">
            <feTurbulence type="fractalNoise" baseFrequency="0.14" numOctaves={3} seed={4 + seed} result="n" />
            <feDisplacementMap in="SourceAlpha" in2="n" scale={11} xChannelSelector="R" yChannelSelector="G" result="a" />
            <feGaussianBlur in="a" stdDeviation={0.7} result="ab" />
            <feMorphology in="SourceGraphic" operator="dilate" radius={2.5} result="big" />
            <feGaussianBlur in="big" stdDeviation={0.6} result="bigs" />
            <feComposite in="bigs" in2="ab" operator="in" />
          </filter>
        </defs>
        <g filter={`url(#${gid("far")})`}>
          <CottonBoll b={{ cx: 48 + j(), cy: 62, r: 64, rot: 30, seed: 7 + seed }} gid={gid} />
          <CottonBoll b={{ cx: 382 + j(), cy: 40, r: 50, rot: 10, seed: 9 + seed }} gid={gid} />
        </g>
        <CottonBoll b={{ cx: 248 + j(), cy: 166, r: 112, rot: 14, seed: 3 + seed }} gid={gid} />
        <g filter={`url(#${gid("near")})`}>
          <CottonBoll b={{ cx: 46 + j(), cy: 274, r: 52, rot: -20, seed: 5 + seed, bract: false }} gid={gid} />
          <CottonBoll b={{ cx: 368 + j(), cy: 284, r: 34, rot: 40, seed: 11 + seed, bract: false }} gid={gid} />
        </g>
      </>
    );
  }

  if (s.kind === "scoop") {
    const all: Placed[] = [...s.inside, ...s.near];
    return (
      <>
        <KindDefs placed={all} gid={gid} />
        <Scoop gid={gid}>
          <Items placed={s.inside} gid={gid} shadow={0.8} heapShadows />
        </Scoop>
        <Focus placed={s.near} gid={gid} far={60} mid={90} near={292} />
      </>
    );
  }

  return (
    <>
      <KindDefs placed={s.near} gid={gid} />
      {"back" in s && s.back ? (
        <g filter={`url(#${gid("far")})`}>
          <HeapUnder m={s.back} gid={gid} mass="#5A2C16" k={0.6} />
        </g>
      ) : null}
      <g filter={`url(#${gid("mid")})`}>
        <HeapUnder m={s.heap} gid={gid} mass={s.mass} />
      </g>
      <Focus
        placed={s.near}
        gid={gid}
        far={84}
        mid={122}
        near={294}
        heapShadows={category === "Coffee" || category === "Oilseeds"}
      />
      <g filter={`url(#${gid("mid")})`}>
        <HeapLight m={s.heap} gid={gid} shade={category === "Millets" ? 0.26 : 0.32} />
      </g>
      {category === "Tea" ? <TeaSprig gid={gid} /> : null}
      {category === "Millets" ? <MilletSpike gid={gid} /> : null}
    </>
  );
}
