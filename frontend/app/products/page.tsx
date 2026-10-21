import type { Metadata } from "next";
import { Suspense } from "react";
import { LinkButton } from "@/components/ui/Button";
import { EmptyState, Skeleton } from "@/components/ui/Surface";
import { CategoryTiles } from "@/components/market/CategoryTiles";
import { MarketAmbient } from "@/components/market/MarketAmbient";
import { MarketHero } from "@/components/market/MarketHero";
import { MarketPagination } from "@/components/products/MarketPagination";
import { ProductFilters } from "@/components/products/ProductFilters";
import { PublicProductCard } from "@/components/products/PublicProductCard";
import { MEDIA } from "@/lib/media";
import {
  publicApi,
  type CatalogFacets,
  type CatalogFilters,
  type PublicProductList,
} from "@/lib/publicApi";
import {
  activeFilterCount,
  filtersFromRecord,
  MARKET_PAGE_SIZE,
  searchParamsFromFilters,
} from "@/lib/productFilters";

export const metadata: Metadata = {
  title: "The market — Corridor One X",
  description:
    "Rice, sugar, wheat, pulses, spices and more from sellers verified by Corridor ops.",
};

export const dynamic = "force-dynamic";

const EMPTY_FACETS: CatalogFacets = { categories: [], originStates: [], priceMin: null, priceMax: null };

/**
 * Public market — the buying lens. No auth; rendered on the server so the
 * first paint already has the photographs and the grid. A photo-led hero
 * band, commodity tiles that filter, search + refine, then the lots.
 */
export default async function MarketPage({
  searchParams,
}: {
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const filters: CatalogFilters = filtersFromRecord(searchParams ?? {});

  const [listRes, facetsRes] = await Promise.allSettled([
    publicApi.listProducts({ ...filters, limit: MARKET_PAGE_SIZE }),
    publicApi.facets(),
  ]);
  const list: PublicProductList | null = listRes.status === "fulfilled" ? listRes.value : null;
  const facets = facetsRes.status === "fulfilled" ? facetsRes.value : EMPTY_FACETS;
  const filtered = activeFilterCount(filters) > 0;
  const live = facets.categories.reduce((n, c) => n + c.count, 0);

  const stats =
    facetsRes.status === "fulfilled"
      ? [
          { label: "Lots live", value: live },
          { label: "Commodities", value: facets.categories.length },
          { label: "Origin states", value: facets.originStates.length },
        ]
      : [];

  return (
    <div className="relative isolate">
      <MarketAmbient media={MEDIA.portDay} opacity={0.24} />

      <MarketHero
        eyebrow="Buying lens · verified sellers only"
        title="The market"
        subtitle="Every seller here is verified by Corridor ops. Their name and contact open once both sides are verified."
        stats={stats}
      />

      <div className="mt-8 animate-rise" style={{ animationDelay: "80ms" }}>
        <CategoryTiles facets={facets} filters={filters} />
      </div>

      <div className="mt-6 animate-rise" style={{ animationDelay: "140ms" }}>
        <Suspense fallback={<FiltersFallback />}>
          <ProductFilters facets={facets} />
        </Suspense>
      </div>

      <section aria-labelledby="lots-title" className="mt-10">
        <div className="mb-5 flex items-baseline justify-between gap-4">
          <h2 id="lots-title" className="t-title2 text-fg">
            {filtered ? "Matching lots" : "Live lots"}
          </h2>
          {list ? (
            <p className="t-code text-fg-3" aria-live="polite">
              {list.total} {list.total === 1 ? "lot" : "lots"}
              {filtered ? " match" : " live"}
            </p>
          ) : null}
        </div>

        {!list ? (
          <div className="relief rounded-[30px]">
            <EmptyState
              icon="alert"
              title="We couldn’t reach the market"
              action={
                <LinkButton href={`/products${searchParamsFromFilters(filters)}`} variant="secondary">
                  Try again
                </LinkButton>
              }
            >
              {listRes.status === "rejected" && listRes.reason instanceof Error
                ? listRes.reason.message
                : "Please try again in a moment."}
            </EmptyState>
          </div>
        ) : list.items.length === 0 ? (
          <div className="relief rounded-[30px]">
            {filtered ? (
              <EmptyState
                icon="search"
                title="No lots match"
                action={
                  <LinkButton href="/products" variant="secondary" icon="close">
                    Clear filters
                  </LinkButton>
                }
              >
                Widen the filters — new lots land as sellers are verified.
              </EmptyState>
            ) : (
              <EmptyState icon="grain" title="The market is quiet">
                No live lots yet. New ones land as sellers are verified.
              </EmptyState>
            )}
          </div>
        ) : (
          <>
            <ul className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {list.items.map((p, i) => (
                <li
                  key={p.id}
                  className="min-w-0 animate-rise"
                  style={{ animationDelay: `${180 + Math.min(i, 8) * 60}ms` }}
                >
                  <PublicProductCard product={p} priority={i < 3} />
                </li>
              ))}
            </ul>
            <MarketPagination filters={filters} total={list.total} pageSize={MARKET_PAGE_SIZE} />
          </>
        )}
      </section>
    </div>
  );
}

function FiltersFallback() {
  return (
    <div className="space-y-4" aria-hidden="true">
      <Skeleton className="h-[52px] w-full rounded-field" />
      <Skeleton className="h-9 w-full max-w-xs rounded-full" />
    </div>
  );
}
