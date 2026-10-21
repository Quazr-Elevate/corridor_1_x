"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, useTransition, type FormEvent } from "react";
import { DISPLAY_CURRENCIES, isDisplayCurrency, useFx, type DisplayCurrency } from "@/components/fx/FxContext";
import { convertAmount, currencySymbol, formatApproxMoney } from "@/components/products/format";
import { Button, IconButton } from "@/components/ui/Button";
import { Segmented } from "@/components/ui/Controls";
import { Input, Select } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { cn } from "@/lib/cn";
import type { CatalogFacets, CatalogFilters } from "@/lib/publicApi";
import {
  activeFilterCount,
  filtersFromSearchParams,
  searchParamsFromFilters,
} from "@/lib/productFilters";

/**
 * Market filter bar. All state lives in the URL so links, Back and share
 * behave. Category is picked with the commodity tiles above (and kept
 * here); origin applies instantly; typed values (search, price, MOQ) apply
 * on Enter or "Apply".
 *
 * Prices are typed in the viewer's display currency (signed-out viewers
 * pick INR / AED / USD here, kept in the URL as `priceCurrency`); the
 * backend converts them to USD and compares every lot's `priceUsd`.
 */
export function ProductFilters({ facets }: { facets: CatalogFacets }) {
  const router = useRouter();
  const pathname = usePathname() || "/products";
  const sp = useSearchParams();
  const [pending, startTransition] = useTransition();

  const current = useMemo(
    () => filtersFromSearchParams(new URLSearchParams(sp?.toString() ?? "")),
    [sp],
  );

  // Typed values are local until applied; re-sync when the URL changes.
  const [q, setQ] = useState(current.q ?? "");
  const [minPrice, setMinPrice] = useState(current.minPrice ?? "");
  const [maxPrice, setMaxPrice] = useState(current.maxPrice ?? "");
  const [minMoq, setMinMoq] = useState(current.minMoq ?? "");
  useEffect(() => {
    setQ(current.q ?? "");
    setMinPrice(current.minPrice ?? "");
    setMaxPrice(current.maxPrice ?? "");
    setMinMoq(current.minMoq ?? "");
  }, [current.q, current.minPrice, current.maxPrice, current.minMoq]);

  const fx = useFx();
  const { setGuestCurrency, signedIn } = fx;
  // Signed-out viewers: the URL pick (default USD) is their display currency.
  useEffect(() => {
    if (!signedIn) setGuestCurrency(current.priceCurrency);
  }, [signedIn, current.priceCurrency, setGuestCurrency]);
  // Bounds already in the URL keep the currency they were typed in.
  const priceCurrency: DisplayCurrency =
    (current.minPrice || current.maxPrice) && isDisplayCurrency(current.priceCurrency)
      ? (current.priceCurrency.toUpperCase() as DisplayCurrency)
      : fx.displayCurrency;
  const symbol = currencySymbol(priceCurrency);

  const refined = !!(current.originState || current.minPrice || current.maxPrice || current.minMoq);
  const [moreOpen, setMoreOpen] = useState(refined);

  const navigate = (next: CatalogFilters) => {
    startTransition(() => {
      router.replace(`${pathname}${searchParamsFromFilters(next)}`, { scroll: false });
    });
  };

  const push = (patch: Partial<CatalogFilters>) => {
    const next: CatalogFilters = { ...current, ...patch };
    delete next.offset; // any filter change starts from page one
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === "") delete (next as Record<string, unknown>)[k];
    }
    navigate(next);
  };

  const priceError =
    minPrice && maxPrice && Number(minPrice) > Number(maxPrice)
      ? "Min is above max"
      : null;

  const apply = (e?: FormEvent) => {
    e?.preventDefault();
    if (priceError) return;
    const priced = !!(minPrice || maxPrice);
    push({
      q: q.trim() || undefined,
      minPrice: minPrice || undefined,
      maxPrice: maxPrice || undefined,
      // Signed-in: the saved display currency; guests keep their URL pick.
      priceCurrency: priced || !signedIn ? (signedIn ? priceCurrency : current.priceCurrency) : undefined,
      minMoq: minMoq || undefined,
    });
  };

  const clearAll = () => {
    setQ("");
    setMinPrice("");
    setMaxPrice("");
    setMinMoq("");
    navigate({});
  };

  const stateOptions = facets.originStates.map((s) => ({
    value: s.value,
    label: `${s.value} (${s.count})`,
  }));
  if (current.originState && !facets.originStates.some((s) => s.value === current.originState)) {
    stateOptions.unshift({ value: current.originState, label: current.originState });
  }

  const active = activeFilterCount(current);
  const numeric = (v: string) => v.replace(/[^\d.]/g, "");
  // Facets come in USD; show the range in the currency the bounds are typed in.
  const rangeIn = (v: string | null) => {
    if (v === null || v === "") return null;
    const n = convertAmount(Number(v), facets.priceCurrency || "USD", priceCurrency, fx.rates);
    return n === null ? null : formatApproxMoney(n, priceCurrency);
  };
  const lo = rangeIn(facets.priceMin);
  const hi = rangeIn(facets.priceMax);
  const priceHint = lo && hi ? `Market range ${lo}–${hi}` : undefined;

  // Guests switch the currency they type prices in (kept in the URL).
  const pickGuestCurrency = (c: DisplayCurrency) => {
    setGuestCurrency(c);
    push({ priceCurrency: c === "USD" ? undefined : c });
  };

  return (
    <form onSubmit={apply} role="search" aria-label="Filter the market" aria-busy={pending || undefined} className="space-y-4">
      <div className="flex gap-2">
        <Input
          type="search"
          aria-label="Search lots"
          placeholder="Search lots — basmati, turmeric…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          leading={<Icon name="search" size={18} />}
          trailing={
            q ? (
              <IconButton
                icon="close"
                label="Clear search"
                className="size-8"
                onClick={() => {
                  setQ("");
                  if (current.q) push({ q: undefined });
                }}
              />
            ) : null
          }
          size="lg"
          className="flex-1"
          inputClassName="[&::-webkit-search-cancel-button]:hidden"
        />
        <Button type="submit" variant="primary" size="lg" className="shrink-0 px-5" loading={pending}>
          <span className="hidden sm:inline">Search</span>
          <span className="sr-only sm:hidden">Search</span>
          {!pending ? <Icon name="arrow-right" size={16} className="sm:hidden" /> : null}
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <p className="t-sub min-w-0 text-fg-3" aria-live="polite">
          {current.category ? (
            <>
              Showing <span className="font-medium text-fg">{current.category}</span>
              {current.q ? <> matching &ldquo;{current.q}&rdquo;</> : null}
            </>
          ) : current.q ? (
            <>Matching &ldquo;{current.q}&rdquo;</>
          ) : (
            "Every commodity"
          )}
        </p>
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="quiet"
            size="sm"
            icon="filter"
            aria-expanded={moreOpen}
            aria-controls="market-refine"
            onClick={() => setMoreOpen((o) => !o)}
            className="hover:bg-[rgb(10_10_10/0.05)]"
          >
            Refine
            {refined ? <span className="t-code text-fg-3">· on</span> : null}
          </Button>
          {active > 0 ? (
            <Button variant="quiet" size="sm" icon="close" onClick={clearAll} className="hover:bg-[rgb(10_10_10/0.05)]">
              Clear {active}
            </Button>
          ) : null}
        </div>
      </div>

      <div
        id="market-refine"
        hidden={!moreOpen}
        className={cn("relief rounded-[26px] p-4 sm:p-5", moreOpen ? "block" : "hidden")}
      >
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto] lg:items-start">
          <Select
            label="Origin state"
            placeholder="Any state"
            value={current.originState ?? ""}
            onChange={(e) => push({ originState: e.target.value || undefined })}
            options={stateOptions}
          />
          <Input
            label={`Min price (${priceCurrency})`}
            inputMode="decimal"
            placeholder="0"
            value={minPrice}
            onChange={(e) => setMinPrice(numeric(e.target.value))}
            leading={<span className="t-code">{symbol}</span>}
            error={priceError}
            hint={priceHint}
          />
          <Input
            label={`Max price (${priceCurrency})`}
            inputMode="decimal"
            placeholder="Any"
            value={maxPrice}
            onChange={(e) => setMaxPrice(numeric(e.target.value))}
            leading={<span className="t-code">{symbol}</span>}
          />
          <Input
            label="Min MOQ"
            inputMode="decimal"
            placeholder="Any"
            value={minMoq}
            onChange={(e) => setMinMoq(numeric(e.target.value))}
          />
          <div className="sm:col-span-2 lg:col-span-1 lg:pt-[27px]">
            <Button type="submit" variant="secondary" block className="h-12 lg:w-auto" disabled={!!priceError || pending}>
              Apply
            </Button>
          </div>
          {!signedIn ? (
            <div className="flex flex-wrap items-center gap-3 sm:col-span-2 lg:col-span-5">
              <span className="t-sub text-fg-3">Show prices in</span>
              <Segmented
                size="sm"
                label="Currency for prices and the price filter"
                value={priceCurrency}
                onChange={pickGuestCurrency}
                options={DISPLAY_CURRENCIES.map((c) => ({ value: c, label: c }))}
              />
            </div>
          ) : null}
        </div>
      </div>
    </form>
  );
}
