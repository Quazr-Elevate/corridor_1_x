"use client";

import { useState } from "react";
import { LinkButton } from "@/components/ui/Button";
import { HoldButton } from "@/components/ui/Controls";
import { Icon } from "@/components/ui/Icon";
import { Card, Notice, Skeleton } from "@/components/ui/Surface";
import { api, ApiError, type RevealedContact } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import { FrostName } from "@/components/market/SellerFrost";
import { RevealCard } from "./RevealCard";

interface GateError {
  tone: "move" | "frozen";
  title: string;
  body: string;
  cta?: "verify" | "signin";
}

/**
 * Who-is-selling gate on the lot detail page.
 *
 *   anonymous            → frosted seller + sign in / get verified
 *   signed in, unverified → "your move" notice → Passport
 *   own listing           → quiet note, nothing to reveal
 *   verified              → hold to reveal → RevealCard
 *
 * The frost never carries the real name — it's decoy glyphs. The identity
 * only reaches the page through the reveal endpoint.
 */
export function ContactGate({
  productId,
  sellerId,
  sellerPlace,
}: {
  productId: string;
  sellerId: string;
  sellerPlace?: string | null;
}) {
  const { me, loading } = useMe();
  const [contact, setContact] = useState<RevealedContact | null>(null);
  const [revealing, setRevealing] = useState(false);
  const [error, setError] = useState<GateError | null>(null);

  const reveal = async () => {
    setRevealing(true);
    setError(null);
    try {
      setContact(await api.revealContact(productId));
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError({
          tone: "move",
          title: "Verify your company first",
          body: "Seller contacts open only to verified buyers.",
          cta: "verify",
        });
      } else if (err instanceof ApiError && err.status === 429) {
        setError({
          tone: "move",
          title: "Reveal limit reached",
          body: "You can open 20 new contacts an hour. Try again shortly.",
        });
      } else if (err instanceof ApiError && err.status === 400) {
        setError({ tone: "frozen", title: "This is your listing", body: "There's no contact to reveal." });
      } else if (err instanceof ApiError && err.status === 401) {
        setError({
          tone: "move",
          title: "Your session ended",
          body: "Sign in again to reveal this contact.",
          cta: "signin",
        });
      } else {
        setError({
          tone: "frozen",
          title: "Couldn't open the contact",
          body: err instanceof Error ? err.message : "Please try again.",
        });
      }
    } finally {
      setRevealing(false);
    }
  };

  if (contact) return <RevealCard contact={contact} />;

  if (loading && !me) {
    return (
      <Card className="space-y-4 rounded-[30px] p-6" aria-busy="true">
        <Skeleton className="h-3 w-24 rounded-full" />
        <Skeleton className="h-9 w-2/3 rounded-full" />
        <Skeleton className="h-12 w-full rounded-field" />
      </Card>
    );
  }

  const next = encodeURIComponent(`/products/${productId}`);

  if (!me) {
    return (
      <Card as="section" className="rounded-[30px] p-6 sm:p-7" aria-labelledby="gate-title">
        <SellerFrost place={sellerPlace} />
        <h2 id="gate-title" className="t-title3 mt-6 text-fg">
          Contact the seller
        </h2>
        <p className="t-callout mt-1.5 text-fg-2">
          Sign in with a verified company to see who&rsquo;s selling and how to reach them.
        </p>
        <div className="mt-5 flex flex-col gap-2.5 sm:flex-row">
          <LinkButton href={`/login?next=${next}`} variant="primary" size="lg" icon="lock" className="sm:flex-1">
            Sign in to contact
          </LinkButton>
          <LinkButton href={`/signup?next=${next}`} variant="secondary" size="lg" className="sm:flex-1">
            Get verified
          </LinkButton>
        </div>
      </Card>
    );
  }

  if (me.businessId === sellerId) {
    return (
      <Notice tone="verified" title="This is your listing">
        Verified buyers can reveal your contact from this page.
      </Notice>
    );
  }

  if (me.verification.status !== "verified") {
    const inReview = me.verification.status === "pending_verification";
    return (
      <Card as="section" className="rounded-[30px] p-6 sm:p-7" aria-label="Contact the seller">
        <SellerFrost place={sellerPlace} />
        <div className="mt-6">
          <Notice
            tone="move"
            title={inReview ? "Your company is in review" : "Verify your company to contact sellers"}
            action={
              inReview ? null : (
                <LinkButton href="/dashboard/account" variant="secondary" size="sm" iconRight="arrow-right">
                  Get verified
                </LinkButton>
              )
            }
          >
            {inReview
              ? "Contacts open the moment Corridor ops verifies you."
              : "Seller contacts open only once both sides are verified."}
          </Notice>
        </div>
      </Card>
    );
  }

  return (
    <Card as="section" className="rounded-[30px] p-6 sm:p-7" aria-labelledby="gate-title">
      <SellerFrost place={sellerPlace} />
      <h2 id="gate-title" className="t-title3 mt-6 text-fg">
        Reveal the seller
      </h2>
      <p className="t-callout mt-1.5 text-fg-2">
        Name, contact person, email and address. Logged to your account.
      </p>
      <HoldButton onCommit={reveal} loading={revealing} icon="unlock" className="mt-5 w-full">
        Reveal contact
      </HoldButton>
      {error ? (
        <div className="mt-4">
          <Notice
            tone={error.tone}
            title={error.title}
            action={
              error.cta === "verify" ? (
                <LinkButton href="/dashboard/account" variant="secondary" size="sm">
                  Passport
                </LinkButton>
              ) : error.cta === "signin" ? (
                <LinkButton href={`/login?next=${next}`} variant="secondary" size="sm">
                  Sign in
                </LinkButton>
              ) : null
            }
          >
            {error.body}
          </Notice>
        </div>
      ) : null}
    </Card>
  );
}

/**
 * Frosted seller identity — the reference's "Exporter · HR-21 [frost] ·
 * Haryana". Decoy glyphs under frost, never the real name.
 */
function SellerFrost({ place }: { place?: string | null }) {
  return (
    <div>
      <p className="t-label text-fg-3">Listed by</p>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="t-headline text-fg">Verified seller</span>
        <FrostName
          size="md"
          width={176}
          label="Seller name hidden until you reveal the contact"
        />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="inline-flex items-center gap-1.5 text-accent">
          <Icon name="shield" size={15} />
          <span className="t-sub font-medium">Verified by Corridor ops</span>
        </span>
        {place ? (
          <span className="t-sub inline-flex items-center gap-1 text-fg-3">
            <Icon name="pin" size={14} />
            {place}
          </span>
        ) : null}
      </div>
    </div>
  );
}
