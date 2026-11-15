"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/ui/Icon";
import { Notice } from "@/components/ui/Surface";
import { LinkButton } from "@/components/ui/Button";
import { MarketAmbient } from "@/components/market/MarketAmbient";
import { ListingForm } from "@/components/products/ListingForm";
import { MEDIA } from "@/lib/media";
import { useMe } from "@/lib/useMe";
import { useUnsavedGuard } from "@/lib/useUnsavedGuard";

/**
 * New listing. It starts as a draft: the seller fills what they have, saves,
 * and submits for review once the checklist is met.
 */
export default function NewListingPage() {
  const { me } = useMe();
  const router = useRouter();
  const { confirmIfDirty } = useUnsavedGuard();
  const verified = me?.verification.status === "verified";

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
        <p className="t-label text-fg-3">New listing · Selling</p>
        <h1 className="t-large mt-2 text-fg">List what you’re selling.</h1>
        <p className="t-callout mt-2 max-w-xl text-fg-2">
          A name and a category are enough to save a draft. A reviewer checks the listing before it reaches the market.
        </p>
      </header>

      {me && !verified ? (
        <div className="mt-8 animate-rise">
          <Notice
            tone="move"
            title="Submit after verification"
            action={
              <LinkButton href="/dashboard/account" variant="secondary" size="sm">
                Passport
              </LinkButton>
            }
          >
            You can save drafts now. Listings can be submitted for review once Corridor ops verifies your company.
          </Notice>
        </div>
      ) : null}

      <div className="mt-8 animate-rise">
        <ListingForm />
      </div>
    </div>
  );
}
