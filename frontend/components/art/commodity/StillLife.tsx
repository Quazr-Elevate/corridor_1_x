import type { ReactNode } from "react";
import { rng } from "../ArtSvg";
import { H, W, quant, type Item } from "./layout";

/**
 * The still-life set every commodity drawing sits on: warm sand hessian in
 * soft window light from the top-left, seen at a low angle — the same
 * ground as the macro photographs. Weave in perspective (coarse in front,
 * fading into the soft background), a light film grain, a warm vignette.
 */

export type Gid = (key: string) => string;

/** Sand duotone: everything on the ground is mixed from these two inks. */
export const SAND = {
  light: "#F6F1E7",
  mid: "#DED3BE",
  deep: "#BCA67D",
  shade: "#6B5434",
  thread: "#7A6440",
} as const;

/* ── weave (computed once) ───────────────────────────────────────── */

const WEAVE = (() => {
  const rand = rng(4242);
  const n1 = (v: number) => (Math.round(v * 10) / 10).toString();
  /** A thread as a gently wavy polyline (jitter across its direction). */
  const wavy = (x0: number, y0: number, x1: number, y1: number, amp: number, step: number) => {
    const vertical = Math.abs(y1 - y0) > Math.abs(x1 - x0);
    const n = Math.max(2, Math.round(Math.hypot(x1 - x0, y1 - y0) / step));
    let d = `M${n1(x0)} ${n1(y0)}`;
    for (let i = 1; i <= n; i++) {
      const t = i / n;
      const j = (rand() - 0.5) * amp;
      d += `L${n1(x0 + (x1 - x0) * t + (vertical ? j : 0))} ${n1(y0 + (y1 - y0) * t + (vertical ? 0 : j))}`;
    }
    return d;
  };
  // horizontal threads: spacing grows toward the viewer; two weights
  const h: [string, string] = ["", ""];
  for (let k = 0, y = 70; y < H + 6; k++) {
    const g = Math.pow((y - 70) / (H - 70), 1.15);
    h[k % 2] += wavy(-4, y, W + 4, y + (rand() - 0.5) * 1.4, 0.4 + g * 1.1, 58);
    y += 1.4 + g * 4.8;
  }
  // vertical threads converge on a vanishing point far above the frame
  const vx = W / 2;
  const vy = -420;
  const v: [string, string] = ["", ""];
  let i = 0;
  for (let x = -170; x <= W + 170; x += 6 + (rand() - 0.5) * 1.2, i++) {
    const t0 = (70 - vy) / (H + 6 - vy);
    v[i % 2] += wavy(vx + (x - vx) * t0, 70, x, H + 6, 1.2, 60);
  }
  // slubs: thicker irregular bits of yarn
  let slub = "";
  for (let k = 0; k < 30; k++) {
    const y = 130 + rand() * (H - 130);
    slub += `M${n1(rand() * W)} ${n1(y)}l${n1(8 + rand() * 18)} ${n1((rand() - 0.5) * 0.8)}`;
  }
  return { h, v, slub };
})();

/** Defs + ground layers. Put items in `children`; vignette and grain go on top. */
export function StillLife({ gid, children, tint }: { gid: Gid; children: ReactNode; tint?: string }) {
  return (
    <>
      <defs>
        <linearGradient id={gid("base")} x1="0.2" y1="0" x2="0.5" y2="1">
          <stop offset="0" stopColor={SAND.light} />
          <stop offset="0.34" stopColor="#EBE3D3" />
          <stop offset="0.72" stopColor={SAND.mid} />
          <stop offset="1" stopColor="#CBBC9F" />
        </linearGradient>
        <radialGradient id={gid("window")} cx="0.12" cy="0" r="1">
          <stop offset="0" stopColor="#FFF8EA" stopOpacity={0.9} />
          <stop offset="0.38" stopColor="#FFF4DE" stopOpacity={0.38} />
          <stop offset="1" stopColor="#FFF4DE" stopOpacity={0} />
        </radialGradient>
        <radialGradient id={gid("vig")} cx="0.46" cy="0.42" r="0.78">
          <stop offset="0.55" stopColor={SAND.shade} stopOpacity={0} />
          <stop offset="1" stopColor={SAND.shade} stopOpacity={0.42} />
        </radialGradient>
        <linearGradient id={gid("weaveFade")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0.22" stopColor="#fff" stopOpacity={0} />
          <stop offset="0.55" stopColor="#fff" stopOpacity={0.7} />
          <stop offset="1" stopColor="#fff" stopOpacity={1} />
        </linearGradient>
        <mask id={gid("weaveMask")} maskUnits="userSpaceOnUse" x={0} y={0} width={W} height={H}>
          <rect width={W} height={H} fill={`url(#${gid("weaveFade")})`} />
        </mask>
        <filter id={gid("noise")} x="0" y="0" width="100%" height="100%" colorInterpolationFilters="sRGB">
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves={2} seed={7} stitchTiles="stitch" />
          <feColorMatrix values="0 0 0 0 0.42  0 0 0 0 0.33  0 0 0 0 0.2  0 0 0 -1.15 0.82" />
        </filter>
        <pattern id={gid("grain")} width={128} height={128} patternUnits="userSpaceOnUse">
          <rect width={128} height={128} filter={`url(#${gid("noise")})`} />
        </pattern>
        {/* depth of field */}
        <filter id={gid("far")} x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation={2.6} />
        </filter>
        <filter id={gid("mid")} x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation={1.1} />
        </filter>
        <filter id={gid("thread")} x="0" y="0" width="100%" height="100%">
          <feGaussianBlur stdDeviation={0.45} />
        </filter>
        <filter id={gid("near")} x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation={0.8} />
        </filter>
        <filter id={gid("soft")} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation={6} />
        </filter>
        {/* shared soft cast shadow (unit circle, scaled per item) */}
        <radialGradient id={gid("castG")}>
          <stop offset="0" stopColor="#3B2A14" stopOpacity={0.5} />
          <stop offset="0.6" stopColor="#3B2A14" stopOpacity={0.2} />
          <stop offset="1" stopColor="#3B2A14" stopOpacity={0} />
        </radialGradient>
        <circle id={gid("cast")} r={1} fill={`url(#${gid("castG")})`} />
        {/* shared specular glints (kinds.tsx) */}
        {[35, 50, 70].map((o) => (
          <radialGradient key={o} id={gid(`glint${o}`)}>
            <stop offset="0" stopColor="#FFF8EC" stopOpacity={o / 100} />
            <stop offset="1" stopColor="#FFF8EC" stopOpacity={0} />
          </radialGradient>
        ))}
      </defs>

      <rect width={W} height={H} fill={`url(#${gid("base")})`} />
      {tint ? <rect width={W} height={H} fill={tint} /> : null}
      {/* soft folds in the cloth */}
      <g filter={`url(#${gid("soft")})`} opacity={0.5}>
        <path d="M-20 214C80 196 170 236 260 214S380 196 430 206L430 226C360 220 300 246 230 238S70 214 -20 236Z" fill={SAND.shade} opacity={0.18} />
        <path d="M-20 150C70 140 150 162 240 150S360 132 430 140L430 150C350 146 280 168 220 166S60 152 -20 162Z" fill="#FFFFFF" opacity={0.45} />
      </g>
      <g mask={`url(#${gid("weaveMask")})`} filter={`url(#${gid("thread")})`} fill="none" strokeLinecap="round">
        <path d={WEAVE.v[0]} stroke={SAND.thread} strokeOpacity={0.15} strokeWidth={1.1} strokeLinejoin="round" />
        <path d={WEAVE.v[1]} stroke={SAND.thread} strokeOpacity={0.1} strokeWidth={1.6} strokeLinejoin="round" />
        <defs>
          <path id={gid("weft")} d={WEAVE.h[0]} />
        </defs>
        <use href={`#${gid("weft")}`} stroke={SAND.thread} strokeOpacity={0.19} strokeWidth={1.25} strokeLinejoin="round" />
        <path d={WEAVE.h[1]} stroke={SAND.thread} strokeOpacity={0.13} strokeWidth={1.7} strokeLinejoin="round" />
        {/* the lit top edge of each weft thread */}
        <use href={`#${gid("weft")}`} transform="translate(0 -1.3)" stroke="#FFFFFF" strokeOpacity={0.34} strokeWidth={0.8} />
        <path d={WEAVE.slub} stroke={SAND.thread} strokeOpacity={0.16} strokeWidth={2} />
      </g>
      <rect width={W} height={H} fill={`url(#${gid("window")})`} />

      {children}

      <rect width={W} height={H} fill={`url(#${gid("vig")})`} />
      <rect width={W} height={H} fill={`url(#${gid("grain")})`} opacity={0.24} style={{ mixBlendMode: "multiply" }} />
    </>
  );
}

/* ── instancing ──────────────────────────────────────────────────── */

/**
 * A kind of item (bean, grain, leaf). `draw` renders one variant in local
 * coordinates (long axis on x, centred at 0,0) *lit for rotation `a`*, so
 * the light stays top-left whichever way the item lies.
 */
export interface Kind {
  key: string;
  /** Angle step for shared symbols (default 15°). */
  step?: number;
  draw: (v: number, a: number, gid: Gid) => ReactNode;
  /** Cast-shadow ellipse radii (local units) for a variant. */
  cast: (v: number) => readonly [number, number];
}

export interface Placed {
  kind: Kind;
  it: Item;
}

/** Tag items with their kind. */
export const as = (kind: Kind, items: readonly Item[]): Placed[] => items.map((it) => ({ kind, it }));

/** The <defs> for every (kind, variant, angle) actually used. */
export function KindDefs({ placed, gid }: { placed: readonly Placed[]; gid: Gid }) {
  const used = new Map<string, { kind: Kind; v: number; a: number }>();
  for (const { kind, it } of placed) {
    const a = quant(it.a, kind.step);
    used.set(`${kind.key}-${it.v}-${a}`, { kind, v: it.v, a });
  }
  return (
    <defs>
      {[...used.entries()].map(([key, { kind, v, a }]) => (
        <g key={key} id={gid(key)}>
          {kind.draw(v, a, (k) => (k.startsWith("@") ? gid(k.slice(1)) : gid(`${key}-${k}`)))}
        </g>
      ))}
    </defs>
  );
}

/** Items in painter's order (by depth), each with its cast shadow. */
export function Items({
  placed,
  gid,
  shadow = 1,
  heapShadows = false,
}: {
  placed: readonly Placed[];
  gid: Gid;
  /** Cast-shadow strength (0 hides them). */
  shadow?: number;
  /** Also cast shadows for items lying on a heap (big items only). */
  heapShadows?: boolean;
}) {
  const sorted = [...placed].sort((p, q) => p.it.depth - q.it.depth);
  const n1 = (v: number) => (Math.round(v * 10) / 10).toString();
  const n2 = (v: number) => (Math.round(v * 100) / 100).toString();
  return (
    <>
      {sorted.flatMap(({ kind, it }, i) => {
        const a = quant(it.a, kind.step);
        const [rx, ry] = kind.cast(it.v);
        const rot = a ? ` rotate(${a})` : "";
        const out = [];
        // heaps carry their own dark mass, so only loose items cast a shadow
        if (shadow > 0 && rx > 0 && (!it.onHeap || heapShadows)) {
          const off = it.onHeap ? 0.9 : 2.2;
          out.push(
            <use
              key={`s${i}`}
              href={`#${gid("cast")}`}
              transform={`translate(${n1(it.x + off * it.s)} ${n1(it.y + off * 1.5 * it.s)})${rot} scale(${n2(rx * it.s * 1.12)} ${n2(ry * it.s * 1.25)})`}
              opacity={shadow * (it.onHeap ? 0.85 : 0.75)}
            />,
          );
        }
        out.push(
          <use
            key={`i${i}`}
            href={`#${gid(`${kind.key}-${it.v}-${a}`)}`}
            transform={`translate(${n1(it.x)} ${n1(it.y)})${rot} scale(${n2(it.s)})`}
          />,
        );
        return out;
      })}
    </>
  );
}

/**
 * Depth of field: items above `far` are well out of focus, those above
 * `mid` slightly soft, the band in between sharp, and anything below
 * `near` (closest to the lens) a touch soft again.
 */
export function Focus({
  placed,
  gid,
  far,
  mid,
  near = H + 10,
  shadow = 1,
  heapShadows = false,
}: {
  placed: readonly Placed[];
  gid: Gid;
  far: number;
  mid: number;
  near?: number;
  shadow?: number;
  heapShadows?: boolean;
}) {
  const band = (lo: number, hi: number) => placed.filter((p) => p.it.y >= lo && p.it.y < hi);
  return (
    <>
      {/* out-of-focus background also sits in the haze of the window light */}
      <g filter={`url(#${gid("far")})`} opacity={0.82}>
        <Items placed={band(-Infinity, far)} gid={gid} shadow={shadow} heapShadows={heapShadows} />
      </g>
      <g filter={`url(#${gid("mid")})`}>
        <Items placed={band(far, mid)} gid={gid} shadow={shadow} heapShadows={heapShadows} />
      </g>
      <Items placed={band(mid, near)} gid={gid} shadow={shadow} heapShadows={heapShadows} />
      <g filter={`url(#${gid("near")})`}>
        <Items placed={band(near, Infinity)} gid={gid} shadow={shadow} heapShadows={heapShadows} />
      </g>
    </>
  );
}
