"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, LinkButton } from "@/components/ui/Button";
import { Segmented } from "@/components/ui/Controls";
import { Notice } from "@/components/ui/Surface";
import { Stagger, StaggerItem } from "@/components/motion/Stagger";
import { MarketAmbient } from "@/components/market/MarketAmbient";
import {
  EmptyWarehouseCard,
  ListingCard,
  ListingCardSkeleton,
  ListLotCard,
} from "@/components/market/ListingCard";
import { api, type ProductRead, type VerificationStatus } from "@/lib/api";
import { MEDIA } from "@/lib/media";
import { useMe } from "@/lib/useMe";

const ALL = "__all";

/**
 * Selling lens — the reference market (portal /market, Selling): header
 * with a segmented filter and New listing, then the "List a lot" well and
 * a card per lot over the warehouse photograph.
 */
export default function ListingsPage() {
  const { me } = useMe();
  const status: VerificationStatus | undefined = me?.verification.status;
  const verified = status === "verified";

  const [items, setItems] = useState<ProductRead[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>(ALL);

  const load = useCallback(async () => {
    setError(null);
    setItems(null);
    try {
      setItems(await api.listProducts());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load your listings");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const categories = useMemo(() => {
    const counts = new Map<string, number>();
    for (const p of items ?? []) counts.set(p.category, (counts.get(p.category) ?? 0) + 1);
    return Array.from(counts, ([value, count]) => ({ value, count })).sort((a, b) => b.count - a.count);
  }, [items]);

  // A filter for a category that no longer has lots falls back to All.
  useEffect(() => {
    if (filter !== ALL && !categories.some((c) => c.value === filter)) setFilter(ALL);
  }, [categories, filter]);

  const visible = useMemo(
    () => (items ?? []).filter((p) => filter === ALL || p.category === filter),
    [items, filter],
  );

  const empty = items?.length === 0;

  return (
    <div className="relative isolate">
      <MarketAmbient media={MEDIA.warehouse} opacity={0.26} />

      <header className="flex animate-rise flex-wrap items-end justify-between gap-6 pt-2 sm:pt-4">
        <div className="min-w-0">
          <p className="t-label text-fg-3">Selling lens</p>
          <h1 className="t-large mt-2 text-fg">What you&rsquo;re selling</h1>
          <p className="t-callout mt-2 max-w-xl text-fg-2">
            Verified buyers find your lots in the market. Your name and contact open only to verified buyers who
            reveal them.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {items && categories.length > 1 ? (
            <Segmented
              label="Filter listings by category"
              size="sm"
              value={filter}
              onChange={setFilter}
              options={[
                { value: ALL, label: "All", count: items.length },
                ...categories.map((c) => ({ value: c.value, label: c.value, count: c.count })),
              ]}
            />
          ) : null}
          <LinkButton href="/dashboard/products/new" variant="primary" icon="plus">
            New listing
          </LinkButton>
        </div>
      </header>

      {me && !verified ? (
        <div className="mt-8 animate-rise">
          <Notice
            tone="move"
            title={
              status === "pending_verification"
                ? "Your company is in review"
                : status === "rejected"
                  ? "Verification needs changes"
                  : "Listings go live after verification"
            }
            action={
              <LinkButton href="/dashboard/account" variant="secondary" size="sm" iconRight="arrow-right">
                {status === "pending_verification" ? "View Passport" : "Finish verification"}
              </LinkButton>
            }
          >
            {status === "pending_verification"
              ? "Your lots appear in the market the moment Corridor ops verifies you."
              : "You can list now. Buyers see your lots once your company is verified."}
          </Notice>
        </div>
      ) : null}

      <section aria-label="Your listings" aria-busy={!items && !error} className="mt-10">
        {error ? (
          <Notice
            tone="frozen"
            title="We couldn’t load your listings"
            action={
              <Button variant="secondary" size="sm" onClick={() => void load()}>
                Try again
              </Button>
            }
          >
            {error}
          </Notice>
        ) : !items ? (
          <ul className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
            <li className="min-w-0">
              <ListLotCard empty={false} />
            </li>
            {[0, 1].map((k) => (
              <li key={k} className="min-w-0">
                <ListingCardSkeleton />
              </li>
            ))}
          </ul>
        ) : (
          <Stagger as="ul" className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
            <StaggerItem as="li" className="min-w-0">
              <ListLotCard empty={empty} />
            </StaggerItem>
            {empty ? (
              <StaggerItem as="li" className="min-w-0 xl:col-span-2">
                <EmptyWarehouseCard className="h-full" />
              </StaggerItem>
            ) : (
              visible.map((p) => (
                <StaggerItem as="li" key={p.id} className="min-w-0">
                  <ListingCard product={p} live={verified} />
                </StaggerItem>
              ))
            )}
          </Stagger>
        )}
      </section>
    </div>
  );
}
