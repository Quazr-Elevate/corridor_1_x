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
 *     uvicorn port. Either way the version prefix is added (lib/apiBase.ts).
 */

import { versioned } from "./apiBase";

const RAW_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
const PUBLIC_BASE = versioned(RAW_BASE);

function isAbsolute(url: string): boolean {
  return /^https?:\/\//i.test(url);
}

/** Base URL for fetches — server-safe. */
export function resolveApiBase(): string {
  if (typeof window === "undefined" && !isAbsolute(RAW_BASE)) {
    return versioned(process.env.API_PROXY_TARGET || "http://localhost:8000");
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

/**
 * `cookie` is the visitor's Cookie header, passed by server components
 * (`(await cookies()).toString()`): the price range is only returned to a
 * signed-in, verified business, and a server-side fetch has no cookies of
 * its own. In the browser the cookie rides along by itself.
 */
export interface ViewerInit {
  cookie?: string;
}

async function get<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
  viewer?: ViewerInit,
): Promise<T> {
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
      ...(onServer
        ? viewer?.cookie
          ? { headers: { cookie: viewer.cookie } }
          : {}
        : { credentials: "include" as const }),
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
  /** The masked company code (`IN-482913`) other parties see instead of a name. */
  companyCode: string | null;
  /** State or region only. The market never shows the seller's city. */
  state: string | null;
  verified: boolean;
}

export interface PublicSpec {
  parameterId: string;
  code: string;
  name: string;
  unit: string | null;
  value: string;
  operator: "MIN" | "MAX" | "EQ";
  testMethod: string | null;
}

export interface PublicCertificate {
  id: string;
  /** The document type. The filename is not shown: it can name the seller. */
  name: string;
  url: string;
}

export interface PublicProductCard {
  id: string;
  name: string;
  category: string;
  variety: string | null;
  grade: string | null;
  originCountry: string | null;
  originState: string | null;
  packaging: string | null;
  quantity: string | null;
  unit: string;
  moq: string | null;
  capacityPerMonth: string | null;
  capacityUnit: string | null;
  incoterms: string[];
  /**
   * The price range is for signed-in, verified businesses. When false, every
   * price field below is null and the card says "Price on request".
   */
  priceVisible: boolean;
  priceMin: string | null;
  priceMax: string | null;
  currency: string | null;
  /** Indicative USD values (latest rate) — for comparing across currencies. */
  priceUsd: string | null;
  priceUsdMax: string | null;
  /** Day of the rate behind priceUsd (YYYY-MM-DD). */
  priceUsdAsOf: string | null;
  priceValidUntil: string | null;
  photo: string | null;
  seller: PublicSeller;
}

export interface PublicProductDetail extends PublicProductCard {
  description: string | null;
  photos: string[];
  specs: PublicSpec[];
  certificates: PublicCertificate[];
}

export interface PublicProductList {
  total: number;
  items: PublicProductCard[];
}

export interface CatalogFacets {
  categories: Array<{ value: string; count: number }>;
  originStates: Array<{ value: string; count: number }>;
  /** Range of priceUsd over live lots, in USD; null unless the viewer may see prices. */
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
  orderQuantity?: string;
  q?: string;
  offset?: number;
  limit?: number;
}

export interface SpecParameter {
  id: string;
  category: string;
  code: string;
  name: string;
  valueType: "number" | "text";
  unit: string | null;
  defaultOperator: "MIN" | "MAX" | "EQ";
  testMethod: string | null;
  isRequired: boolean;
  sortOrder: number;
  active: boolean;
}

export interface CertificateType {
  id: string;
  /** A product category, or "*" for every category. */
  category: string;
  code: string;
  name: string;
  helpText: string | null;
  isRequired: boolean;
  sortOrder: number;
  active: boolean;
}

/** What a listing in a category is asked for. */
export interface CategoryTemplate {
  category: string;
  specParameters: SpecParameter[];
  certificateTypes: CertificateType[];
}

/**
 * A country Corridor One X onboards businesses from. Admin ops decides the
 * list (active + at least one required KYB document); the sign-up form reads
 * it anonymously, before any account exists, because the country picked
 * there decides which KYB documents the business must bring.
 */
export interface OpenCountry {
  code: string;
  name: string;
  flag: string | null;
  dialCode: string | null;
  defaultCurrency: string;
}

export const publicApi = {
  listProducts: (filters: CatalogFilters = {}, viewer?: ViewerInit) =>
    get<PublicProductList>("/public/products", { ...filters }, viewer),
  getProduct: (id: string, viewer?: ViewerInit) =>
    get<PublicProductDetail>(`/public/products/${encodeURIComponent(id)}`, undefined, viewer),
  facets: (viewer?: ViewerInit) => get<CatalogFacets>("/public/catalog/facets", undefined, viewer),
  fxRates: () => get<FxRates>("/public/fx/rates"),
  categoryTemplate: (category: string) => get<CategoryTemplate>("/public/catalog/template", { category }),
  countries: () => get<{ items: OpenCountry[] }>("/public/countries").then((r) => r.items),
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
