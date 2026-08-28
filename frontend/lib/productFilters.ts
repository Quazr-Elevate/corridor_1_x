import type { CatalogFilters } from "./publicApi";

/**
 * URL <-> filter object bridge. Keeps `/products?category=Rice&q=basmati`
 * bookmarkable and back-button-safe.
 *
 * Empty strings become undefined so `?category=` doesn't override to a
 * literal empty category on the backend.
 */

const KEYS = [
  "category",
  "variety",
  "originState",
  "minPrice",
  "maxPrice",
  "minMoq",
  "q",
] as const;

export function filtersFromSearchParams(sp: URLSearchParams): CatalogFilters {
  const out: CatalogFilters = {};
  for (const k of KEYS) {
    const v = sp.get(k);
    if (v) (out as Record<string, string>)[k] = v;
  }
  const off = sp.get("offset");
  if (off) out.offset = Number(off) || 0;
  return out;
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

/** How many filter chips are active — used to render a Clear button. */
export function activeFilterCount(f: CatalogFilters): number {
  return KEYS.reduce(
    (n, k) => n + ((f as Record<string, string | undefined>)[k] ? 1 : 0),
    0,
  );
}
