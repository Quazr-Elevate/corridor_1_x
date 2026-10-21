/**
 * Projection, framing and paths for the corridor map. Pure functions —
 * computed once at module load, shared by server and client.
 *
 * Mercator, 16 viewBox units per degree of longitude, origin at the
 * top-left of the data frame (lon 44, lat 36).
 */
import { CAPTIONS, FRAME, LAND, PORTS, laneWaypoints, type Lane, type LonLat, type PortId } from "./geo";

export const UNITS_PER_DEG = 16;
const KR = (UNITS_PER_DEG * 180) / Math.PI;
const mercY = (lat: number) => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
const Y_TOP = mercY(FRAME.lat1);

export const FRAME_W = (FRAME.lon1 - FRAME.lon0) * UNITS_PER_DEG;
export const FRAME_H = (Y_TOP - mercY(FRAME.lat0)) * KR;

export function project(p: LonLat): [number, number] {
  return [(p[0] - FRAME.lon0) * UNITS_PER_DEG, (Y_TOP - mercY(p[1])) * KR];
}

const f1 = (n: number) => (Math.round(n * 10) / 10).toString();

/** Every land ring as one path, in viewBox units. */
export const LAND_PATH: string = LAND.map((ring) => {
  const pts = ring.map(project);
  return "M" + pts.map(([x, y]) => `${f1(x)} ${f1(y)}`).join("L") + "Z";
}).join("");

/** Uniform Catmull–Rom through projected waypoints, as cubic Béziers. */
function spline(points: Array<[number, number]>): string {
  const P = [points[0], ...points, points[points.length - 1]];
  let d = `M${f1(points[0][0])} ${f1(points[0][1])}`;
  for (let i = 1; i < P.length - 2; i++) {
    const [p0, p1, p2, p3] = [P[i - 1], P[i], P[i + 1], P[i + 2]];
    const c1x = p1[0] + (p2[0] - p0[0]) / 6;
    const c1y = p1[1] + (p2[1] - p0[1]) / 6;
    const c2x = p2[0] - (p3[0] - p1[0]) / 6;
    const c2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += `C${f1(c1x)} ${f1(c1y)} ${f1(c2x)} ${f1(c2y)} ${f1(p2[0])} ${f1(p2[1])}`;
  }
  return d;
}

export function lanePath(lane: Lane): string {
  return spline(laneWaypoints(lane).map(project));
}

export const PORT_XY: Record<PortId, [number, number]> = Object.fromEntries(
  Object.values(PORTS).map((p) => [p.id, project(p.at)]),
) as Record<PortId, [number, number]>;

export const CAPTION_XY = CAPTIONS.map((c) => ({ ...c, xys: c.at.map(project) }));

export interface ViewBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** The part of the frame that must always show: UAE ports + Hormuz to Kakinada + Sri Lanka. */
const FOCUS = (() => {
  const [x0, y0] = project([48.8, 28.8]);
  const [x1, y1] = project([86.4, 4.6]);
  return { x0, y0, x1, y1 };
})();

/** Frame the corridor for a given width / height ratio (clamped to 0.95–1.9). */
export function viewBoxFor(aspect: number): ViewBox {
  const a = Math.min(1.9, Math.max(0.95, aspect));
  const fw = FOCUS.x1 - FOCUS.x0;
  const fh = FOCUS.y1 - FOCUS.y0;
  let w = fw;
  let h = fw / a;
  if (h < fh) {
    h = fh;
    w = fh * a;
  }
  w = Math.min(w, FRAME_W);
  h = Math.min(h, FRAME_H);
  // Spare room goes mostly north (Iran, Pakistan) and west (Arabia):
  // land reads better than open ocean.
  const x = Math.min(FRAME_W - w, Math.max(0, FOCUS.x0 - (w - fw) * 0.6));
  const y = Math.min(FRAME_H - h, Math.max(0, FOCUS.y0 - (h - fh) * 0.72));
  return { x: round1(x), y: round1(y), w: round1(w), h: round1(h) };
}

function round1(n: number) {
  return Math.round(n * 10) / 10;
}
