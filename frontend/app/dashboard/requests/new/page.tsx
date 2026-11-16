"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { trade } from "@/lib/trade";
import { PRODUCT_CATEGORIES } from "@/components/products/ListingForm";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { Card, Notice, Skeleton } from "@/components/ui/Surface";

/**
 * Start a request. From a listing (`?listing=<id>`) the draft is created at
 * once and opened; otherwise the buyer names the category and the product
 * first, because the category decides which specifications are asked.
 */
function NewRequest() {
  const router = useRouter();
  const listing = useSearchParams().get("listing");
  const [category, setCategory] = useState("Rice");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (!listing || started.current) return;
    started.current = true;
    trade
      .createRfq({ kind: "listing", listingId: listing })
      .then((r) => router.replace(`/dashboard/requests/${r.id}`))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn’t start the request."));
  }, [listing, router]);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await trade.createRfq({ kind: "open", category, productName: name.trim() });
      router.replace(`/dashboard/requests/${r.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn’t start the request.");
      setBusy(false);
    }
  };

  if (listing) {
    return error ? <Notice tone="frozen" className="mt-8">{error}</Notice> : <Skeleton className="mt-8 h-40 w-full rounded-[26px]" />;
  }
  return (
    <Card as="section" className="mt-8 max-w-xl space-y-4 rounded-[26px] p-5 sm:p-6" aria-label="What are you looking for">
      <Select label="Category" value={category} onChange={(e) => setCategory(e.target.value)} options={PRODUCT_CATEGORIES} />
      <Input label="Product" value={name} maxLength={200} placeholder="e.g. 1121 Steam Basmati" onChange={(e) => setName(e.target.value)} />
      {error ? <Notice tone="frozen">{error}</Notice> : null}
      <Button variant="primary" iconRight="arrow-right" loading={busy} disabled={name.trim().length < 2} onClick={() => void start()}>
        Continue
      </Button>
    </Card>
  );
}

export default function NewRequestPage() {
  return (
    <div className="pt-6 sm:pt-10">
      <header className="animate-rise">
        <p className="t-label text-fg-3">New request</p>
        <h1 className="t-large mt-2 text-fg">What are you looking for?</h1>
        <p className="t-callout mt-2 max-w-xl text-fg-2">A draft is free. You can write it now and submit once your company is verified.</p>
      </header>
      <Suspense fallback={<Skeleton className="mt-8 h-40 w-full rounded-[26px]" />}>
        <NewRequest />
      </Suspense>
    </div>
  );
}
