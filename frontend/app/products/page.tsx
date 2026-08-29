import type { Metadata } from "next";
import { Suspense } from "react";
import { AmbientBackground } from "@/components/brand/AmbientBackground";
import { PublicNav } from "@/components/products/PublicNav";
import { ProductFilters } from "@/components/products/ProductFilters";
import { PublicProductCard } from "@/components/products/PublicProductCard";
import { publicApi, type CatalogFilters } from "@/lib/publicApi";
import { filtersFromSearchParams } from "@/lib/productFilters";

export const metadata: Metadata = {
  title: "Catalog — Cor1x",
  description: "Verified rice, sugar, wheat, and pulses from KYB-cleared Indian sellers.",
};

// Public catalog — no auth. Server component so the initial paint has
// the grid already rendered (better perceived speed than a spinner).
export default async function ProductsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const filters: CatalogFilters = filtersFromSearchParams(
    new URLSearchParams(
      Object.entries(sp).flatMap(([k, v]) =>
        v === undefined ? [] : Array.isArray(v) ? v.map((x) => [k, x]) : [[k, v]],
      ),
    ),
  );

  const [list, facets] = await Promise.all([
    publicApi.listProducts(filters),
    publicApi.facets(),
  ]);

  return (
    <main className="relative min-h-dvh safe-x overflow-hidden bg-ink text-paper">
      <AmbientBackground />

      <div className="relative mx-auto max-w-6xl px-5 py-8">
        <PublicNav />

        <section className="mt-10 enter" data-delay="2">
          <p className="chip">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" />
            Public catalog · verified sellers only
          </p>
          <h1 className="mt-3 text-display sm:text-display-lg text-paper">
            {list.total} listing{list.total === 1 ? "" : "s"}{" "}
            <span className="text-gradient">from India</span>
          </h1>
          <p className="mt-2 max-w-xl text-sm text-paper-muted">
            Every seller has been admin-verified. Contact details are shared only
            after both sides pass verification.
          </p>
        </section>

        <div className="mt-6 enter" data-delay="3">
          <Suspense fallback={<div className="text-xs text-paper-muted">Loading filters…</div>}>
            <ProductFilters facets={facets} />
          </Suspense>
        </div>

        {list.items.length === 0 ? (
          <p className="mt-16 rounded-card border border-dashed border-line px-6 py-10 text-center text-sm text-paper-muted enter" data-delay="4">
            No listings match those filters. Try clearing them, or check back — the
            catalog updates as new sellers are verified.
          </p>
        ) : (
          <div className="mt-6 grid grid-cols-1 gap-4 enter sm:grid-cols-2 lg:grid-cols-3" data-delay="4">
            {list.items.map((p) => (
              <PublicProductCard key={p.id} product={p} />
            ))}
          </div>
        )}

        <footer className="mt-16 border-t border-line-soft pt-6 text-xs text-paper-muted">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>© 2026 Corridor One X</span>
            <div className="flex items-center gap-4">
              <a href="/privacy" className="hover:text-paper">Privacy</a>
              <a href="/terms" className="hover:text-paper">Terms</a>
              <a href="mailto:privacy@cor1x.com" className="hover:text-paper">Grievance</a>
            </div>
          </div>
        </footer>
      </div>
    </main>
  );
}
