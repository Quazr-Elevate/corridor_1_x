/**
 * Public catalog client — anonymous-safe reads.
 *
 * These endpoints don't require a session cookie, but sending one is
 * harmless (backend just ignores it). We reuse the same fetch base URL
 * as api.ts so misconfig is impossible.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

async function get<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const qs = params
    ? "?" +
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== "" && v !== null)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join("&")
    : "";
  const res = await fetch(`${API_BASE}${path}${qs}`, {
    credentials: "include",
    cache: "no-store",
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg =
      (body as { detail?: string })?.detail || `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return body as T;
}

export interface PublicSeller {
  sellerId: string;
  companyName: string;
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
  priceMin: string | null;
  priceMax: string | null;
}

export interface CatalogFilters {
  category?: string;
  variety?: string;
  originState?: string;
  minPrice?: string;
  maxPrice?: string;
  minMoq?: string;
  q?: string;
  offset?: number;
  limit?: number;
}

export const publicApi = {
  listProducts: (filters: CatalogFilters = {}) =>
    get<PublicProductList>("/public/products", { ...filters }),
  getProduct: (id: string) =>
    get<PublicProductDetail>(`/public/products/${id}`),
  facets: () => get<CatalogFacets>("/public/catalog/facets"),
};

/** Absolute URL for a `/uploads/...` path returned by the catalog. */
export function photoUrl(rel: string | null | undefined): string | null {
  if (!rel) return null;
  return rel.startsWith("http") ? rel : `${API_BASE}${rel}`;
}
