/**
 * Photography — the typed media library.
 *
 * Source of truth: `public/media/gen/manifest.json` (written by the image
 * pipeline: one full-size JPG fallback, WebP renditions per width, and a
 * tiny blurred JPEG as a data URL for the loading placeholder). This file
 * maps those entries to camelCase keys and adds the alt text.
 *
 * Server-safe (no "use client"): import anywhere.
 *
 *   import { MEDIA, commodityPhoto } from "@/lib/media";
 *   <Photo media={MEDIA.portNight} portrait={MEDIA.portNightPortrait} fill priority />
 *   const photo = commodityPhoto(product.category); // MediaEntry | undefined
 *
 * Drawn art (components/art/*) is only the fallback for commodities that
 * have no photograph yet — `commodityPhoto()` returns undefined for those.
 */
import manifest from "@/public/media/gen/manifest.json";

/** One photograph, ready for a <picture>. */
export interface MediaEntry {
  /** camelCase key in {@link MEDIA}. */
  key: MediaKey;
  /** Full-size JPEG — the fallback for browsers without WebP. */
  src: string;
  /** WebP renditions by intrinsic width (px) → URL. */
  webp: Readonly<Record<number, string>>;
  /** The WebP widths, ascending. */
  widths: readonly number[];
  /** `srcset` string for the WebP renditions ("…-640.webp 640w, …"). */
  webpSrcSet: string;
  /** Intrinsic size of the full-size image. */
  width: number;
  height: number;
  /** width / height. */
  aspect: number;
  /** Describes the picture; empty it (`decorative`) when it is only atmosphere. */
  alt: string;
  /** Tiny blurred JPEG data URL — painted until the photo has loaded. */
  blurDataURL: string;
}

interface RawEntry {
  width: number;
  height: number;
  widths: number[];
  src: string;
  webp: Record<string, string>;
  blurDataURL: string;
}

/** camelCase key → manifest file stem. */
const FILES = {
  portNight: "port-night",
  portNightPortrait: "port-night-portrait",
  portDay: "port-day",
  warehouse: "warehouse",
  dubaiDusk: "dubai-dusk",
  inspector: "inspector",
  rice: "rice",
  sugar: "sugar",
  wheat: "wheat",
  pulses: "pulses",
  spices: "spices",
} as const;

export type MediaKey = keyof typeof FILES;

const ALT: Record<MediaKey, string> = {
  portNight:
    "A container port at night: gantry cranes and a berthed ship lit in amber, reflected across dark water.",
  portNightPortrait:
    "A container port at night: gantry cranes lit in amber, their lights reflected across dark water.",
  portDay: "A container port in hazy morning light, gantry cranes over a berthed ship and calm water.",
  warehouse: "Rice sacks stacked high on pallets in a sunlit warehouse.",
  dubaiDusk: "The Dubai skyline and the Jebel Ali port cranes at dusk, seen across the water.",
  inspector: "An inspector lifts a scoop of basmati rice from an open sack, a checklist beside it.",
  rice: "Long-grain basmati rice on hessian, close up.",
  sugar: "Refined white sugar crystals, close up.",
  wheat: "Wheat ears and grains on hessian, close up.",
  pulses: "Split yellow lentils, red lentils and green mung beans on hessian.",
  spices: "Turmeric root, black pepper, dried red chillies and green cardamom, close up.",
};

const RAW: Record<string, RawEntry> = manifest;

function build(key: MediaKey): MediaEntry {
  const raw = RAW[FILES[key]];
  if (!raw) throw new Error(`media manifest has no entry "${FILES[key]}" (lib/media.ts)`);
  const webp: Record<number, string> = {};
  for (const [w, url] of Object.entries(raw.webp)) webp[Number(w)] = url;
  const widths = Object.keys(webp)
    .map(Number)
    .sort((a, b) => a - b);
  return {
    key,
    src: raw.src,
    webp,
    widths,
    webpSrcSet: widths.map((w) => `${webp[w]} ${w}w`).join(", "),
    width: raw.width,
    height: raw.height,
    aspect: raw.width / raw.height,
    alt: ALT[key],
    blurDataURL: raw.blurDataURL,
  };
}

export const MEDIA_KEYS = Object.keys(FILES) as MediaKey[];

/** Every photograph, by key. */
export const MEDIA: Readonly<Record<MediaKey, MediaEntry>> = Object.freeze(
  Object.fromEntries(MEDIA_KEYS.map((k) => [k, build(k)])) as Record<MediaKey, MediaEntry>,
);

/**
 * The smallest WebP at least `minWidth` wide (or the largest there is).
 * Handy for layers that are blurred anyway — the ambient photo uses 640.
 */
export function webpAtLeast(media: MediaEntry, minWidth = 0): string {
  const w = media.widths.find((x) => x >= minWidth) ?? media.widths[media.widths.length - 1];
  return w === undefined ? media.src : media.webp[w];
}

/** The largest WebP rendition (the full-size image as WebP). */
export function largestWebp(media: MediaEntry): string {
  return webpAtLeast(media, Number.POSITIVE_INFINITY);
}

// ── Commodities ────────────────────────────────────────────────────

/** Listing categories (mirrors the backend's `Category` literal). */
export const COMMODITY_CATEGORIES = [
  "Rice",
  "Sugar",
  "Wheat",
  "Pulses",
  "Spices",
  "Oilseeds",
  "Cotton",
  "Millets",
  "Tea",
  "Coffee",
  "Other",
] as const;

export type CommodityCategory = (typeof COMMODITY_CATEGORIES)[number];

/** Macro photograph per category; undefined → use the drawn fallback. */
export const COMMODITY_PHOTOS: Readonly<Record<CommodityCategory, MediaEntry | undefined>> = Object.freeze({
  Rice: MEDIA.rice,
  Sugar: MEDIA.sugar,
  Wheat: MEDIA.wheat,
  Pulses: MEDIA.pulses,
  Spices: MEDIA.spices,
  Oilseeds: undefined,
  Cotton: undefined,
  Millets: undefined,
  Tea: undefined,
  Coffee: undefined,
  Other: undefined,
});

const BY_LOWER: Record<string, MediaEntry | undefined> = Object.fromEntries(
  COMMODITY_CATEGORIES.map((c) => [c.toLowerCase(), COMMODITY_PHOTOS[c]]),
);

/**
 * The photograph for a listing category (case-insensitive), or undefined
 * when there is none and the drawn art should stand in.
 */
export function commodityPhoto(category: string | null | undefined): MediaEntry | undefined {
  if (!category) return undefined;
  return BY_LOWER[category.trim().toLowerCase()];
}
