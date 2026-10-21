import type { CatalogFilters } from "./publicApi";

/**
 * URL <-> filter object bridge. Keeps `/products?category=Rice&q=basmati`
 * bookmarkable and back-button-safe.
 *
 * Empty strings become undefined so `?category=` doesn't override to a
 * literal empty category on the backend.
 */

/** Lots per page in the public market (backend allows 1–60). */
export const MARKET_PAGE_SIZE = 24;

const KEYS = [
  "category",
  "variety",
  "originState",
  "minPrice",
  "maxPrice",
  "priceCurrency",
  "minMoq",
  "q",
] as const;

export type FilterKey = (typeof KEYS)[number];

export function filtersFromSearchParams(sp: URLSearchParams): CatalogFilters {
  const out: CatalogFilters = {};
  for (const k of KEYS) {
    const raw = sp.get(k)?.trim();
    const v = k === "priceCurrency" ? raw?.toUpperCase() : raw;
    if (v) (out as Record<string, string>)[k] = v;
  }
  const off = Number(sp.get("offset"));
  if (Number.isFinite(off) && off > 0) out.offset = Math.floor(off);
  return out;
}

/** Same as filtersFromSearchParams, for a Next.js `searchParams` record. */
export function filtersFromRecord(
  sp: Record<string, string | string[] | undefined>,
): CatalogFilters {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(sp)) {
    if (v === undefined) continue;
    if (Array.isArray(v)) v.forEach((x) => p.append(k, x));
    else p.set(k, v);
  }
  return filtersFromSearchParams(p);
}

export function searchParamsFromFilters(f: CatalogFilters): string {
  const p = new URLSearchParams();
  for (const k of KEYS) {
    const v = (f as Record<string, string | undefined>)[k];
    if (v) p.set(k, v);
  }
  if (f.offset) p.set("offset", String(f.offset));
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** How many filters are active — used to render a Clear button.
 *  `priceCurrency` only qualifies the price bounds, so it doesn't count. */
export function activeFilterCount(f: CatalogFilters): number {
  return KEYS.reduce(
    (n, k) => n + (k !== "priceCurrency" && (f as Record<string, string | undefined>)[k] ? 1 : 0),
    0,
  );
}
