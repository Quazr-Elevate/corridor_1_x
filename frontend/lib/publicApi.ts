/**
 * Public catalog client — anonymous-safe reads.
 *
 * These endpoints don't require a session cookie, but sending one is
 * harmless (the backend ignores it).
 *
 * Base URL:
 *   • browser — same base as lib/api.ts (`NEXT_PUBLIC_API_BASE_URL`, else the
 *     same-origin `/api` proxy from next.config.mjs).
 *   • server  — a relative base can't be fetched from Node, so when the public
 *     base is relative we talk to the backend directly via `API_PROXY_TARGET`
 *     (the same target the /api rewrite points at), defaulting to the local
 *     uvicorn port.
 */

const PUBLIC_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

function isAbsolute(url: string): boolean {
  return /^https?:\/\//i.test(url);
}

/** Base URL for fetches — server-safe. */
export function resolveApiBase(): string {
  if (typeof window === "undefined" && !isAbsolute(PUBLIC_BASE)) {
    return (process.env.API_PROXY_TARGET || "http://localhost:8000").replace(/\/+$/, "");
  }
  return PUBLIC_BASE;
}

export class PublicApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function get<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const qs = params
    ? Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== "" && v !== null)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join("&")
    : "";
  const onServer = typeof window === "undefined";
  let res: Response;
  try {
    res = await fetch(`${resolveApiBase()}${path}${qs ? `?${qs}` : ""}`, {
      // Cookies only matter (and only work) in the browser.
      ...(onServer ? {} : { credentials: "include" as const }),
      cache: "no-store",
    });
  } catch {
    throw new PublicApiError("We couldn't reach the market. Try again in a moment.", 0);
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (body as { detail?: unknown })?.detail;
    throw new PublicApiError(
      typeof detail === "string" ? detail : `Request failed (${res.status})`,
      res.status,
    );
  }
  return body as T;
}

export interface PublicSeller {
  /** The seller's business id. */
  sellerId: string;
  businessName: string;
  city: string | null;
  state: string | null;
  verified: boolean;
}

export interface PublicProductCard {
  id: string;
  name: string;
  category: string;
  variety: string | null;
  originState: string | null;
  packaging: string | null;
  quantity: string | null;
  unit: string;
  moq: string | null;
  pricePerUnit: string | null;
  currency: string;
  /** Indicative USD value (latest rate) — for comparing across currencies. */
  priceUsd: string | null;
  /** Day of the rate behind priceUsd (YYYY-MM-DD). */
  priceUsdAsOf: string | null;
  photo: string | null;
  seller: PublicSeller;
}

export interface PublicProductDetail extends PublicProductCard {
  description: string | null;
  photos: string[];
}

export interface PublicProductList {
  total: number;
  items: PublicProductCard[];
}

export interface CatalogFacets {
  categories: Array<{ value: string; count: number }>;
  originStates: Array<{ value: string; count: number }>;
  /** Range of priceUsd over live lots — in `priceCurrency` (always USD). */
  priceMin: string | null;
  priceMax: string | null;
  priceCurrency?: string;
  fxAsOf?: string | null;
}

/** GET /public/fx/rates — 1 USD = rates[code] × code. */
export interface FxRates {
  base: "USD";
  asOf: string | null;
  rates: Record<string, number>;
  source: string | null;
}

export interface CatalogFilters {
  category?: string;
  variety?: string;
  originState?: string;
  minPrice?: string;
  maxPrice?: string;
  /** Currency minPrice/maxPrice are typed in (backend default USD). */
  priceCurrency?: string;
  minMoq?: string;
  q?: string;
  offset?: number;
  limit?: number;
}

export const publicApi = {
  listProducts: (filters: CatalogFilters = {}) =>
    get<PublicProductList>("/public/products", { ...filters }),
  getProduct: (id: string) =>
    get<PublicProductDetail>(`/public/products/${encodeURIComponent(id)}`),
  facets: () => get<CatalogFacets>("/public/catalog/facets"),
  fxRates: () => get<FxRates>("/public/fx/rates"),
};

/**
 * URL for a `/uploads/...` path returned by the catalog, for rendering in
 * the browser (<img src>). Uses the public base, so it resolves through the
 * same-origin proxy or the configured absolute API URL.
 */
export function photoUrl(rel: string | null | undefined): string | null {
  if (!rel) return null;
  if (/^(https?:|data:|blob:)/.test(rel)) return rel;
  return `${PUBLIC_BASE}${rel.startsWith("/") ? rel : `/${rel}`}`;
}
