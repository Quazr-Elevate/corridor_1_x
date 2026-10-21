import { local } from "./layout";
import type { Gid, Kind } from "./StillLife";

/**
 * Item kinds for the still-lifes. Each is drawn in local coordinates with
 * its long axis on x; every lighting term (gradient centre, specular) is
 * placed in *screen* space through `local(a, …)`, so a bean lying at any
 * angle is still lit from the top-left.
 */

type Stop = readonly [offset: number, color: string, opacity?: number];

function stops(list: readonly Stop[]) {
  return list.map(([o, c, op], i) => <stop key={i} offset={o} stopColor={c} stopOpacity={op ?? 1} />);
}

/** Radial gradient centred on the lit side (screen offset `at`). */
function Lit({ id, a, at, r, list }: { id: string; a: number; at: readonly [number, number]; r: number; list: readonly Stop[] }) {
  const [cx, cy] = local(a, at[0], at[1]);
  return (
    <radialGradient id={id} gradientUnits="userSpaceOnUse" cx={cx} cy={cy} r={r} fx={cx} fy={cy}>
      {stops(list)}
    </radialGradient>
  );
}

/** Linear gradient running from the lit side to the shadow side. */
function LitLinear({ id, a, d, list }: { id: string; a: number; d: number; list: readonly Stop[] }) {
  const [x1, y1] = local(a, -d * 0.62, -d * 0.78);
  const [x2, y2] = local(a, d * 0.62, d * 0.78);
  return (
    <linearGradient id={id} gradientUnits="userSpaceOnUse" x1={x1} y1={y1} x2={x2} y2={y2}>
      {stops(list)}
    </linearGradient>
  );
}

/** A soft specular glint that stays level in screen space (gradients shared via StillLife). */
function Glint({ gid, a, at, rx, ry, o = 0.5 }: { gid: Gid; a: number; at: readonly [number, number]; rx: number; ry: number; o?: number }) {
  const [cx, cy] = local(a, at[0], at[1]);
  const level = o >= 0.62 ? 70 : o >= 0.45 ? 50 : 35;
  const x = cx.toFixed(2);
  const y = cy.toFixed(2);
  return (
    <ellipse cx={x} cy={y} rx={rx} ry={ry} fill={`url(#${gid(`@glint${level}`)})`} transform={`rotate(${-a - 18} ${x} ${y})`} />
  );
}

const url = (id: string) => `url(#${id})`;

/* ── Coffee ──────────────────────────────────────────────────────── */

const BEAN = "M-12 0.2C-12 -5.9 -6.6 -8.9 0.2 -8.8C7 -8.7 12 -5.4 12 0C12 5.6 6.9 8.8 0 8.8C-6.9 8.8 -12 6.1 -12 0.2Z";

/** Roasted arabica: v0 flat face with the centre cut, v1 the rounded back. */
export const coffeeBean: Kind = {
  key: "bean",
  step: 24,
  cast: () => [12.5, 8.5],
  draw: (v, a, gid) => (
    <>
      <Lit
        id={gid("b")}
        a={a}
        at={[-3.6, -4.4]}
        r={18}
        list={[
          [0, v === 1 ? "#A8754B" : "#9C6942"],
          [0.32, "#7A4828"],
          [0.72, "#4C2913"],
          [1, "#2A1609"],
        ]}
      />
      <path d={BEAN} fill={url(gid("b"))} />
      {v === 0 ? (
        <>
          <path
            d="M-9.6 1.3C-6 -1.7 -2.2 2.7 1.2 0.6C4.4 -1.3 7.2 -1 9.8 0.4"
            fill="none"
            stroke="#1A0C04"
            strokeWidth={1.8}
            strokeLinecap="round"
          />
          <path
            d="M-9.2 0.1C-5.8 -2.8 -2.1 1.5 1.1 -0.5C4.2 -2.3 7 -2 9.4 -0.8"
            fill="none"
            stroke="#D7A57A"
            strokeOpacity={0.28}
            strokeWidth={0.7}
            strokeLinecap="round"
          />
        </>
      ) : (
        <path d="M-8.6 -0.4C-3 -2.4 3 -2.4 8.6 -0.4" fill="none" stroke="#C49068" strokeOpacity={0.2} strokeWidth={2.6} strokeLinecap="round" />
      )}
      <Glint gid={gid} a={a} at={[-3.4, -4.6]} rx={4.6} ry={1.9} o={0.55} />
      <path d={BEAN} fill="none" stroke="#170A03" strokeOpacity={0.35} strokeWidth={0.6} />
    </>
  ),
};

/* ── Tea ─────────────────────────────────────────────────────────── */

const CURLS = [
  "M-11 0.6C-8 -2.4 -3 -2.6 1 -1.4C4.5 -0.4 8 -2.2 11 -1C9.2 1.8 5 2.6 1.2 1.8C-2.6 1 -6.6 2.8 -11 0.6Z",
  "M-9 2C-9.5 -1.5 -6 -3.4 -2 -2.6C2 -1.8 4 -3.6 7.5 -3C10 -2.4 10.4 0.4 8.2 1.4C5.5 2.6 2.6 0.8 -0.4 1.8C-3.4 2.8 -6 3.8 -9 2Z",
  "M-7.4 0C-5.2 -2.6 -1 -2.9 1.7 -1.7C4.2 -0.6 6.2 -1.7 7.6 -0.2C6.2 1.9 3.1 2.5 0.4 1.7C-2.5 0.9 -5 2.5 -7.4 0Z",
  "M-6 0.2C-4 -1.8 -0.6 -2 2 -1.2C4 -0.6 5.4 -0.8 6.4 0C5.2 1.4 2.6 1.8 0.2 1.4C-2.2 1 -4.2 1.8 -6 0.2Z",
];
const CURL_GROOVE = [
  "M-9 0.3C-5 -1 -1 1 3 -0.2C6 -1 8 -0.8 10 -0.4",
  "M-7.6 1.2C-5 -0.4 -1.4 -0.2 2 -0.6C4.6 -1 6.6 -1.4 8.6 -0.6",
  "M-6 0C-3.6 -1.2 -0.6 0.6 2.4 -0.2C4.4 -0.7 5.6 -0.4 6.6 -0.1",
  "M-4.8 0.1C-2.4 -0.8 0.4 0.4 3 -0.2",
];

/** Orthodox black tea: twisted dark leaf (v0–2) and a golden tip (v3). */
export const teaCurl: Kind = {
  key: "tea",
  step: 30,
  cast: (v) => (v === 3 ? [6.5, 2.2] : [10, 2.8]),
  draw: (v, a, gid) => {
    const tip = v === 3;
    return (
      <>
        <LitLinear
          id={gid("b")}
          a={a}
          d={4}
          list={
            tip
              ? [
                  [0, "#D9B676"],
                  [0.5, "#A9833F"],
                  [1, "#6E5022"],
                ]
              : [
                  [0, "#6B5538"],
                  [0.45, "#3A2B1A"],
                  [1, "#17100A"],
                ]
          }
        />
        <path d={CURLS[v]} fill={url(gid("b"))} />
        <path d={CURL_GROOVE[v]} fill="none" stroke={tip ? "#5E4418" : "#0B0703"} strokeOpacity={0.55} strokeWidth={0.6} strokeLinecap="round" />
        <Glint gid={gid} a={a} at={[-1.6, -1.2]} rx={3.4} ry={0.8} o={tip ? 0.5 : 0.32} />
      </>
    );
  },
};

/* ── Millets ─────────────────────────────────────────────────────── */

const PEARL = "M-3.4 0.1C-3.4 -2.3 -1.6 -3.1 0.3 -3C2.3 -2.9 3.6 -1.6 3.6 0.1C3.6 1.9 2.2 3 0.2 3C-1.8 3 -3.4 2.1 -3.4 0.1Z";
const PEARL_TONES: ReadonlyArray<readonly Stop[]> = [
  [
    [0, "#F2E6C4"],
    [0.42, "#D3BC8A"],
    [0.82, "#A28A5A"],
    [1, "#776242"],
  ],
  [
    [0, "#E9E3CF"],
    [0.42, "#C6BA97"],
    [0.82, "#968A68"],
    [1, "#6E6448"],
  ],
  [
    [0, "#F4DFAE"],
    [0.42, "#D8B272"],
    [0.82, "#A7804A"],
    [1, "#7A5A30"],
  ],
];

/** Pearl millet (bajra): plump grey-gold grains with a dark hilum. */
export const pearlMillet: Kind = {
  key: "pearl",
  step: 45,
  cast: () => [3.4, 2.8],
  draw: (v, a, gid) => (
    <>
      <Lit id={gid("b")} a={a} at={[-1.3, -1.5]} r={5} list={PEARL_TONES[v]} />
      <path d={PEARL} fill={url(gid("b"))} />
      <circle cx={3} cy={0.1} r={0.6} fill="#4A3820" fillOpacity={0.55} />
      <Glint gid={gid} a={a} at={[-1.2, -1.4]} rx={1.5} ry={0.8} o={0.6} />
    </>
  ),
};

/** Finger millet (ragi): tiny round red-brown seeds. */
export const ragi: Kind = {
  key: "ragi",
  step: 90,
  cast: () => [2.2, 2],
  draw: (_v, a, gid) => (
    <>
      <Lit
        id={gid("b")}
        a={a}
        at={[-0.8, -1]}
        r={3}
        list={[
          [0, "#C27A4C"],
          [0.5, "#8A4424"],
          [1, "#4A200E"],
        ]}
      />
      <circle r={2.3} fill={url(gid("b"))} />
      <Glint gid={gid} a={a} at={[-0.8, -0.9]} rx={0.9} ry={0.5} o={0.55} />
    </>
  ),
};

/* ── Oilseeds ────────────────────────────────────────────────────── */

const KERNEL = "M-7 0C-7 -4 -4 -5 0 -4.9C4 -4.8 7.2 -3.2 7.2 0C7.2 3.4 4 4.9 0 4.9C-4 4.9 -7 3.8 -7 0Z";

/** Groundnut kernels: v0 whole (red skin), v1 split half (cream face). */
export const peanutKernel: Kind = {
  key: "kernel",
  step: 30,
  cast: () => [7, 4.8],
  draw: (v, a, gid) =>
    v === 0 ? (
      <>
        <Lit
          id={gid("b")}
          a={a}
          at={[-2.2, -2.6]}
          r={9.5}
          list={[
            [0, "#D2946A"],
            [0.4, "#A8623C"],
            [0.8, "#6E3519"],
            [1, "#4A200C"],
          ]}
        />
        <path d={KERNEL} fill={url(gid("b"))} />
        <path d="M-5.4 -1.6C-2 -2.6 2 -2.4 5.6 -1.2M-5.6 1.4C-2 2.4 2 2.4 5.8 1.2" fill="none" stroke="#3E1A08" strokeOpacity={0.22} strokeWidth={0.5} />
        <Glint gid={gid} a={a} at={[-2.2, -2.4]} rx={2.8} ry={1.1} o={0.5} />
      </>
    ) : (
      <>
        <Lit
          id={gid("f")}
          a={a}
          at={[-2, -2.4]}
          r={9}
          list={[
            [0, "#F6ECCF"],
            [0.5, "#DFCB98"],
            [1, "#B49464"],
          ]}
        />
        <path d={KERNEL} fill="#8A4424" />
        <path d="M-6.4 -0.2C-6.4 -3.4 -3.6 -4.2 0 -4.1C3.6 -4 6.4 -2.8 6.4 -0.2C6.4 2.6 3.6 3.9 0 3.9C-3.6 3.9 -6.4 2.8 -6.4 -0.2Z" fill={url(gid("f"))} />
        <path d="M4.2 -0.6C5 -0.9 5.6 -0.3 5.4 0.4C5.1 1.1 4.2 1 4 0.4" fill="#C9AE76" stroke="#8A6A38" strokeOpacity={0.5} strokeWidth={0.4} />
        <path d="M-4.6 0C-1.6 -0.6 1.6 -0.6 3.8 -0.2" fill="none" stroke="#A88A56" strokeOpacity={0.35} strokeWidth={0.45} />
      </>
    ),
};

const SHELL =
  "M-17 0C-17 -6 -13 -8 -9 -7.6C-5 -7.2 -3 -5 0 -5C3 -5 5 -7.6 10 -7.8C14.5 -8 17.5 -5 17.5 0C17.5 5 14.5 8 10 7.8C5 7.6 3 5 0 5C-3 5 -5 7.2 -9 7.6C-13 8 -17 6 -17 0Z";
const SHELL_NET = (() => {
  const ridges =
    "M-15.5 -2.6C-12 -5 -6 -4.4 -2 -2.6C2 -1.2 7 -5 15.8 -2.6" +
    "M-16.4 0.4C-11 -1.2 -5 -0.8 0 -0.2C5 0.4 11 -1.4 17 0.2" +
    "M-15.4 3.2C-11 4.8 -5.4 4.4 -1.6 2.8C2.4 1.6 7.6 5 15.6 2.8";
  let cross = "";
  for (let x = -14; x <= 15; x += 2.6) {
    const lobe = Math.abs(x) > 2 ? 6.6 : 4.6;
    cross += `M${x.toFixed(1)} ${(-lobe + 1.4).toFixed(1)}l0.9 2.4M${(x + 1.2).toFixed(1)} -1.2l-0.8 2.6M${x.toFixed(1)} ${(lobe - 3.6).toFixed(1)}l0.9 2.2`;
  }
  return { ridges, cross };
})();

/** Groundnut in its shell: two lobes, waisted, netted. */
export const peanutShell: Kind = {
  key: "shell",
  cast: () => [17, 7.5],
  draw: (_v, a, gid) => (
    <>
      <Lit
        id={gid("b")}
        a={a}
        at={[-5, -6]}
        r={24}
        list={[
          [0, "#EAD6A8"],
          [0.4, "#C9A970"],
          [0.78, "#9E7C48"],
          [1, "#76572E"],
        ]}
      />
      <path d={SHELL} fill={url(gid("b"))} />
      <path d={SHELL_NET.ridges} fill="none" stroke="#5E4220" strokeOpacity={0.3} strokeWidth={0.7} strokeLinecap="round" />
      <path d={SHELL_NET.cross} fill="none" stroke="#5E4220" strokeOpacity={0.2} strokeWidth={0.55} strokeLinecap="round" />
      <path d="M0 -5C-0.8 -1.6 -0.8 1.6 0 5" fill="none" stroke="#5E4220" strokeOpacity={0.4} strokeWidth={0.8} />
      <Glint gid={gid} a={a} at={[-5.5, -4.2]} rx={6} ry={1.8} o={0.4} />
      <path d={SHELL} fill="none" stroke="#4E3618" strokeOpacity={0.3} strokeWidth={0.55} />
    </>
  ),
};

/** Mustard seed: tiny, dark, glossy. */
export const mustard: Kind = {
  key: "mustard",
  step: 90,
  cast: () => [2, 1.8],
  draw: (v, a, gid) => (
    <>
      <Lit
        id={gid("b")}
        a={a}
        at={[-0.7, -0.8]}
        r={2.6}
        list={
          v === 0
            ? [
                [0, "#8A5634"],
                [0.5, "#4A2612"],
                [1, "#1E0E05"],
              ]
            : [
                [0, "#C99A52"],
                [0.5, "#946524"],
                [1, "#5A3A12"],
              ]
        }
      />
      <circle r={1.95} fill={url(gid("b"))} />
      <Glint gid={gid} a={a} at={[-0.6, -0.8]} rx={0.8} ry={0.45} o={0.7} />
    </>
  ),
};

/** Sesame: flat pale teardrop. */
export const sesame: Kind = {
  key: "sesame",
  step: 30,
  cast: () => [2.4, 1.4],
  draw: (_v, a, gid) => (
    <>
      <Lit
        id={gid("b")}
        a={a}
        at={[-0.8, -0.6]}
        r={3}
        list={[
          [0, "#FBF4E2"],
          [0.6, "#E6D7B2"],
          [1, "#BFA978"],
        ]}
      />
      <path d="M-2.4 0C-2.4 -1.3 -1 -1.5 0.4 -1.3C1.6 -1.1 2.5 -0.5 2.5 0C2.5 0.5 1.6 1.1 0.4 1.3C-1 1.5 -2.4 1.3 -2.4 0Z" fill={url(gid("b"))} />
      <path d="M-1.8 0H1.8" stroke="#9C8458" strokeOpacity={0.35} strokeWidth={0.3} />
    </>
  ),
};

/* ── Mixed (Other) ───────────────────────────────────────────────── */

const RICE = "M-5.6 0.2C-5.6 -1.3 -3.6 -1.85 0 -1.85C3.6 -1.85 5.6 -1.2 5.6 0C5.6 1.25 3.6 1.85 0 1.85C-3.6 1.85 -5.6 1.4 -5.6 0.2Z";

/** Long-grain rice. */
export const riceGrain: Kind = {
  key: "rice",
  cast: () => [5.8, 1.9],
  draw: (_v, a, gid) => (
    <>
      <Lit
        id={gid("b")}
        a={a}
        at={[-1.6, -1.2]}
        r={6.4}
        list={[
          [0, "#FFFDF7"],
          [0.5, "#EFE6D1"],
          [1, "#C8B994"],
        ]}
      />
      <path d={RICE} fill={url(gid("b"))} />
      <Glint gid={gid} a={a} at={[-1.4, -0.9]} rx={2.6} ry={0.6} o={0.75} />
    </>
  ),
};

/** Split pigeon pea (toor dal). */
export const splitPulse: Kind = {
  key: "dal",
  step: 45,
  cast: () => [4.4, 4],
  draw: (_v, a, gid) => (
    <>
      <Lit
        id={gid("b")}
        a={a}
        at={[-1.6, -1.8]}
        r={6}
        list={[
          [0, "#F6D88E"],
          [0.5, "#DDAD52"],
          [1, "#A6772C"],
        ]}
      />
      <ellipse rx={4.4} ry={3.9} fill={url(gid("b"))} />
      <path d="M-2.6 0.6C-1 -0.2 0.8 0.4 2.4 -0.4" fill="none" stroke="#9A6A22" strokeOpacity={0.35} strokeWidth={0.4} />
      <Glint gid={gid} a={a} at={[-1.4, -1.6]} rx={1.8} ry={0.9} o={0.55} />
    </>
  ),
};
