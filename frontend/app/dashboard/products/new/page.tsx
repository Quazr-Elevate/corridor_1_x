"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/ui/Icon";
import { Notice } from "@/components/ui/Surface";
import { LinkButton } from "@/components/ui/Button";
import { MarketAmbient } from "@/components/market/MarketAmbient";
import { ProductForm } from "@/components/products/ProductForm";
import { MEDIA } from "@/lib/media";
import { useMe } from "@/lib/useMe";
import { useUnsavedGuard } from "@/lib/useUnsavedGuard";

/**
 * New listing — the reference's "Say it like you would on a call" composer
 * (portal /market → List a lot), as a page: the sentence first, then what
 * buyers will see, photos and the description.
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
        <h1 className="t-large mt-2 text-fg">Say it like you would on a call.</h1>
        <p className="t-callout mt-2 max-w-xl text-fg-2">
          A name and one photo is enough to publish. Add the detail buyers ask for when you have it.
        </p>
      </header>

      {me && !verified ? (
        <div className="mt-8 animate-rise">
          <Notice
            tone="move"
            title="Goes live after verification"
            action={
              <LinkButton href="/dashboard/account" variant="secondary" size="sm">
                Passport
              </LinkButton>
            }
          >
            You can publish now. Buyers see the lot once Corridor ops verifies your company.
          </Notice>
        </div>
      ) : null}

      <div className="mt-8 animate-rise">
        <ProductForm />
      </div>
    </div>
  );
}
