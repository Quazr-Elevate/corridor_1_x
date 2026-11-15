"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Icon } from "@/components/ui/Icon";
import { MarketAmbient } from "@/components/market/MarketAmbient";
import { ListingForm } from "@/components/products/ListingForm";
import { MEDIA } from "@/lib/media";
import { useUnsavedGuard } from "@/lib/useUnsavedGuard";

/** Edit a listing: a draft, one sent back by a reviewer, or a published one. */
export default function EditListingPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { confirmIfDirty } = useUnsavedGuard();

  return (
    <div className="relative isolate mx-auto max-w-[980px]">
      <MarketAmbient media={MEDIA.warehouse} opacity={0.22} />

      <Link
        href="/dashboard/products"
        onClick={(e) => {
          e.preventDefault();
          confirmIfDirty(() => router.push("/dashboard/products"));
        }}
        className="t-callout inline-flex items-center gap-1.5 rounded-full py-1 pr-2 text-fg-2 transition-colors hover:text-fg"
      >
        <Icon name="arrow-left" size={16} />
        Listings
      </Link>

      <header className="mt-6 animate-rise">
        <p className="t-label text-fg-3">Listing · Selling</p>
        <h1 className="t-large mt-2 text-fg">Edit listing</h1>
      </header>

      <div className="mt-8 animate-rise">
        <ListingForm key={id} productId={id} />
      </div>
    </div>
  );
}
