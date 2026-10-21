/**
 * Art tones — the only colours the drawn library may use.
 *
 * Every value is a system colour (paper, cream, sand, ink, olive, lime,
 * amber) or a tonal step mixed from them. Each isometric object takes a
 * `surface` prop and reads its palette from here, so the same drawing sits
 * correctly on the cream trader ground and on the ink control tower.
 * (Commodity still-lifes are "photographs" and keep one palette on both
 * surfaces — see commodity/StillLife.tsx; the corridor map reads the
 * surface's CSS tokens.)
 *
 * Isometric light comes from the top-left: top face lightest, left face
 * mid, right face darkest. On the tower surface the materials follow the
 * system's own inversion — paper becomes charcoal, and *solid* ink becomes
 * cream (as `.solid` does under [data-surface="tower"]).
 */

import type { CSSProperties } from "react";

export type Surface = "trader" | "tower";

export interface ArtProps {
  className?: string;
  /** Accessible name. Omit for decorative use (the SVG is then aria-hidden). */
  title?: string;
  /** Which system surface the art sits on. Defaults to "trader" (cream). */
  surface?: Surface;
  style?: CSSProperties;
}

/** One material, shaded for isometric light from the top-left. */
export interface Material {
  top: string;
  left: string;
  right: string;
  /** Edge line colour for this material. */
  edge: string;
  /** Colour for marks drawn on the faces (ribs, text, seams) — use with opacity. */
  mark: string;
}

export interface IsoTone {
  paper: Material;
  sand: Material;
  straw: Material;
  ink: Material;
  lime: Material;
  /** Contact-shadow colour (used in a fading radial gradient). */
  shadow: string;
  shadowOpacity: number;
  olive: string;
  amber: string;
  lime500: string;
  /** Ground-plane hint lines. */
  ground: string;
}

const INK = "#0A0A0A";

export const ISO_TONES: Record<Surface, IsoTone> = {
  trader: {
    paper: { top: "#FAF8F4", left: "#EEEAE2", right: "#DDD5C6", edge: INK, mark: INK },
    sand: { top: "#EDE5D3", left: "#D9CCB0", right: "#CBBD9E", edge: INK, mark: INK },
    straw: { top: "#E8D9B6", left: "#D7C49A", right: "#C2AD83", edge: INK, mark: INK },
    ink: { top: "#34332F", left: "#1E1D1B", right: INK, edge: INK, mark: "#F4F1EC" },
    lime: { top: "#D6E85A", left: "#C4D82E", right: "#A8BB1C", edge: INK, mark: INK },
    shadow: "rgb(146 130 100)",
    shadowOpacity: 0.5,
    olive: "#55620E",
    amber: "#8A5A00",
    lime500: "#C4D82E",
    ground: "rgb(10 10 10 / 0.08)",
  },
  tower: {
    paper: { top: "#3A3A36", left: "#2B2B28", right: "#1F1F1D", edge: "#8A8C84", mark: "#EDEFEA" },
    sand: { top: "#45413A", left: "#34312B", right: "#262420", edge: "#8E8878", mark: "#EDEFEA" },
    straw: { top: "#4B4435", left: "#3A3428", right: "#2A251D", edge: "#948A72", mark: "#EDEFEA" },
    ink: { top: "#F4F1EC", left: "#DEDCD4", right: "#C3C1B8", edge: INK, mark: INK },
    lime: { top: "#D6E85A", left: "#C4D82E", right: "#A8BB1C", edge: INK, mark: INK },
    shadow: "rgb(0 0 0)",
    shadowOpacity: 0.75,
    olive: "#C4D82E",
    amber: "#F2B84B",
    lime500: "#C4D82E",
    ground: "rgb(237 239 234 / 0.07)",
  },
};
