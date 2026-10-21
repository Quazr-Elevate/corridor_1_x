import type { ReactNode } from "react";
import { r2 } from "../ArtSvg";
import type { Material } from "../tone";

/**
 * Isometric core — true isometric projection (30° axes).
 *
 * World axes: +x runs to the screen's lower-right, +y to the lower-left,
 * +z straight up. Visible faces of a box are its top (z max), its LEFT
 * face (y max) and its RIGHT face (x max). Light comes from the top-left,
 * so top = lightest, left = mid, right = darkest.
 *
 * Shapes on a face are drawn in that face's own 2D coordinates (u, v) and
 * mapped through `onTop / onLeft / onRight`, which keeps stroke widths
 * untouched (no skewed strokes) and curves exact (affine maps preserve
 * Béziers).
 */

export const C = Math.cos(Math.PI / 6); // 0.866…
export const SW = 1.15; // edge line width (viewBox units)
export const SW_FINE = 0.75; // marks on faces

export type P3 = readonly [number, number, number];
export type Map2 = (u: number, v: number) => P3;

export function iso(p: P3): [number, number] {
  return [(p[0] - p[1]) * C, (p[0] + p[1]) * 0.5 - p[2]];
}

export function pt(p: P3): string {
  const [x, y] = iso(p);
  return `${r2(x)},${r2(y)}`;
}

export function poly(points: P3[]): string {
  return points.map(pt).join(" ");
}

/** u → +x, v → +y on the horizontal plane through `o`. */
export const onTop =
  (o: P3): Map2 =>
  (u, v) => [o[0] + u, o[1] + v, o[2]];

/** Left face (y = const): u → +x, v → down (−z). Origin = face's top-left. */
export const onLeft =
  (o: P3): Map2 =>
  (u, v) => [o[0] + u, o[1], o[2] - v];

/** Right face (x = const): u → −y (towards the right), v → down. Origin = face's top-left (the y-max corner). */
export const onRight =
  (o: P3): Map2 =>
  (u, v) => [o[0], o[1] - u, o[2] - v];

/**
 * Map an absolute 2D path (M L H V C Q Z, uppercase only) through a plane
 * mapping into an isometric screen path.
 */
export function mapD(d: string, f: Map2): string {
  const tokens = d.match(/[MLHVCQZ]|-?\d*\.?\d+(?:e-?\d+)?/gi) ?? [];
  let i = 0;
  let cmd = "M";
  let cu = 0;
  let cv = 0;
  const out: string[] = [];
  const num = () => parseFloat(tokens[i++]);
  const P = (u: number, v: number) => {
    const [x, y] = iso(f(u, v));
    return `${r2(x)} ${r2(y)}`;
  };
  while (i < tokens.length) {
    const t = tokens[i];
    if (/^[MLHVCQZ]$/i.test(t)) {
      cmd = t.toUpperCase();
      i++;
      if (cmd === "Z") {
        out.push("Z");
        continue;
      }
    }
    switch (cmd) {
      case "M":
      case "L": {
        cu = num();
        cv = num();
        out.push(`${cmd}${P(cu, cv)}`);
        if (cmd === "M") cmd = "L";
        break;
      }
      case "H":
        cu = num();
        out.push(`L${P(cu, cv)}`);
        break;
      case "V":
        cv = num();
        out.push(`L${P(cu, cv)}`);
        break;
      case "C": {
        const a = num(), b = num(), c = num(), e = num();
        cu = num();
        cv = num();
        out.push(`C${P(a, b)} ${P(c, e)} ${P(cu, cv)}`);
        break;
      }
      case "Q": {
        const a = num(), b = num();
        cu = num();
        cv = num();
        out.push(`Q${P(a, b)} ${P(cu, cv)}`);
        break;
      }
      default:
        i++;
    }
  }
  return out.join("");
}

const K = 0.5522847498;
/** A circle as four cubic arcs, in local 2D coordinates. */
export function circleD(cx: number, cy: number, r: number): string {
  const k = r * K;
  return (
    `M${cx + r} ${cy}` +
    `C${cx + r} ${cy + k} ${cx + k} ${cy + r} ${cx} ${cy + r}` +
    `C${cx - k} ${cy + r} ${cx - r} ${cy + k} ${cx - r} ${cy}` +
    `C${cx - r} ${cy - k} ${cx - k} ${cy - r} ${cx} ${cy - r}` +
    `C${cx + k} ${cy - r} ${cx + r} ${cy - k} ${cx + r} ${cy}Z`
  );
}

/** Rounded rectangle in local 2D coordinates. */
export function rrectD(x: number, y: number, w: number, h: number, r: number): string {
  const k = r * (1 - K);
  return (
    `M${x + r} ${y}H${x + w - r}C${x + w - k} ${y} ${x + w} ${y + k} ${x + w} ${y + r}` +
    `V${y + h - r}C${x + w} ${y + h - k} ${x + w - k} ${y + h} ${x + w - r} ${y + h}` +
    `H${x + r}C${x + k} ${y + h} ${x} ${y + h - k} ${x} ${y + h - r}` +
    `V${y + r}C${x} ${y + k} ${x + k} ${y} ${x + r} ${y}Z`
  );
}

/* ── Box ─────────────────────────────────────────────────────────── */

export function boxFaces(o: P3, s: P3) {
  const [x, y, z] = o;
  const [w, d, h] = s;
  return {
    top: poly([
      [x, y, z + h],
      [x + w, y, z + h],
      [x + w, y + d, z + h],
      [x, y + d, z + h],
    ]),
    left: poly([
      [x, y + d, z],
      [x + w, y + d, z],
      [x + w, y + d, z + h],
      [x, y + d, z + h],
    ]),
    right: poly([
      [x + w, y, z],
      [x + w, y + d, z],
      [x + w, y + d, z + h],
      [x + w, y, z + h],
    ]),
  };
}

/** A shaded box with ink edges. `o` = min corner, `s` = [w (x), d (y), h (z)]. */
export function Box({
  o,
  s,
  m,
  sw = SW,
  hideTop,
  children,
}: {
  o: P3;
  s: P3;
  m: Material;
  sw?: number;
  hideTop?: boolean;
  children?: ReactNode;
}) {
  const f = boxFaces(o, s);
  return (
    <g stroke={m.edge} strokeWidth={sw} strokeLinejoin="round" strokeLinecap="round">
      <polygon points={f.left} fill={m.left} />
      <polygon points={f.right} fill={m.right} />
      {hideTop ? null : <polygon points={f.top} fill={m.top} />}
      {children}
    </g>
  );
}

/** A line between two world points. */
export function Seg({
  a,
  b,
  stroke,
  sw = SW_FINE,
  opacity,
}: {
  a: P3;
  b: P3;
  stroke: string;
  sw?: number;
  opacity?: number;
}) {
  const [x1, y1] = iso(a);
  const [x2, y2] = iso(b);
  return (
    <line
      x1={r2(x1)}
      y1={r2(y1)}
      x2={r2(x2)}
      y2={r2(y2)}
      stroke={stroke}
      strokeWidth={sw}
      strokeOpacity={opacity}
      strokeLinecap="round"
    />
  );
}

/* ── Vertical cylinder ───────────────────────────────────────────── */

/** Screen radii of a horizontal iso circle of radius r. */
export const isoRx = (r: number) => r * Math.SQRT2 * C;
export const isoRy = (r: number) => r * Math.SQRT1_2;

/**
 * Upright cylinder centred on (cx, cy) in world x/y, from z0 to z1. Body is
 * shaded with a horizontal gradient (`gradId`, define with `<CylGrad>`).
 */
export function Cylinder({
  c,
  r,
  z0,
  z1,
  m,
  gradId,
  sw = SW,
  topFill,
}: {
  c: readonly [number, number];
  r: number;
  z0: number;
  z1: number;
  m: Material;
  gradId: string;
  sw?: number;
  topFill?: string;
}) {
  const [bx, by] = iso([c[0], c[1], z0]);
  const [, ty] = iso([c[0], c[1], z1]);
  const rx = isoRx(r);
  const ry = isoRy(r);
  const body =
    `M${r2(bx - rx)} ${r2(ty)}V${r2(by)}` +
    `A${r2(rx)} ${r2(ry)} 0 0 0 ${r2(bx + rx)} ${r2(by)}` +
    `V${r2(ty)}A${r2(rx)} ${r2(ry)} 0 0 1 ${r2(bx - rx)} ${r2(ty)}Z`;
  return (
    <g stroke={m.edge} strokeWidth={sw} strokeLinejoin="round">
      <path d={body} fill={`url(#${gradId})`} />
      <ellipse cx={r2(bx)} cy={r2(ty)} rx={r2(rx)} ry={r2(ry)} fill={topFill ?? m.top} />
    </g>
  );
}

/** Horizontal light-to-dark gradient for cylinders and rounded forms. */
export function CylGrad({ id, m }: { id: string; m: Material }) {
  return (
    <linearGradient id={id} x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stopColor={m.left} />
      <stop offset="0.45" stopColor={m.left} />
      <stop offset="1" stopColor={m.right} />
    </linearGradient>
  );
}

/* ── Contact shadow ──────────────────────────────────────────────── */

/** Radial fade used by every contact shadow. */
export function ShadowGrad({ id, color, opacity }: { id: string; color: string; opacity: number }) {
  return (
    <radialGradient id={id}>
      <stop offset="0" stopColor={color} stopOpacity={opacity} />
      <stop offset="0.55" stopColor={color} stopOpacity={opacity * 0.45} />
      <stop offset="1" stopColor={color} stopOpacity={0} />
    </radialGradient>
  );
}

/**
 * Soft contact shadow on the ground plane under a footprint centred at
 * world (cx, cy). Light from the top-left pushes it slightly to the right.
 */
export function ContactShadow({
  c,
  rx,
  ry,
  gradId,
  dx = 6,
}: {
  c: readonly [number, number];
  rx: number;
  ry: number;
  gradId: string;
  dx?: number;
}) {
  const [x, y] = iso([c[0], c[1], 0]);
  return <ellipse cx={r2(x + dx)} cy={r2(y + 2)} rx={r2(rx)} ry={r2(ry)} fill={`url(#${gradId})`} />;
}

/**
 * Blurred footprint shadow for long objects (ship, truck, crane): the
 * object's ground outline, pushed a little to the right, softened by the
 * frame's `soft` filter.
 */
export function FootprintShadow({
  points,
  filterId,
  color,
  opacity,
  dx = 6,
  dy = 3,
}: {
  points: P3[];
  filterId: string;
  color: string;
  opacity: number;
  dx?: number;
  dy?: number;
}) {
  return (
    <polygon
      points={poly(points)}
      transform={`translate(${dx} ${dy})`}
      fill={color}
      fillOpacity={opacity}
      filter={`url(#${filterId})`}
    />
  );
}

/** SVG transform that lays flat 2D content (e.g. text) onto a face. */
export function planeMatrix(plane: "top" | "left" | "right", o: P3): string {
  const [x, y] = iso(o);
  const tx = r2(x);
  const ty = r2(y);
  const c = C.toFixed(5);
  if (plane === "top") return `matrix(${c} 0.5 -${c} 0.5 ${tx} ${ty})`;
  if (plane === "left") return `matrix(${c} 0.5 0 1 ${tx} ${ty})`;
  return `matrix(${c} -0.5 0 1 ${tx} ${ty})`;
}

/* ── World-space paths ───────────────────────────────────────────── */

export type WSeg = ["M" | "L", P3] | ["Q", P3, P3] | ["C", P3, P3, P3] | ["Z"];

/** Build a screen path from world-space segments (Béziers map exactly). */
export function wpath(segs: WSeg[]): string {
  return segs
    .map((s) => {
      switch (s[0]) {
        case "M":
        case "L":
          return `${s[0]}${pt(s[1]).replace(",", " ")}`;
        case "Q":
          return `Q${pt(s[1]).replace(",", " ")} ${pt(s[2]).replace(",", " ")}`;
        case "C":
          return `C${pt(s[1]).replace(",", " ")} ${pt(s[2]).replace(",", " ")} ${pt(s[3]).replace(",", " ")}`;
        default:
          return "Z";
      }
    })
    .join("");
}

/** Point on a quadratic Bézier between world points. */
export function qAt(a: P3, c: P3, b: P3, t: number): P3 {
  const u = 1 - t;
  return [
    u * u * a[0] + 2 * u * t * c[0] + t * t * b[0],
    u * u * a[1] + 2 * u * t * c[1] + t * t * b[1],
    u * u * a[2] + 2 * u * t * c[2] + t * t * b[2],
  ];
}

/** Linear mix of two #RRGGBB colours (t = 0 → a, t = 1 → b). */
export function mix(a: string, b: string, t: number): string {
  const pa = parseInt(a.slice(1), 16);
  const pb = parseInt(b.slice(1), 16);
  const m = (s: number) => {
    const x = (pa >> s) & 255;
    const y = (pb >> s) & 255;
    return Math.round(x + (y - x) * t);
  };
  const n = (m(16) << 16) | (m(8) << 8) | m(0);
  return `#${n.toString(16).padStart(6, "0")}`;
}
