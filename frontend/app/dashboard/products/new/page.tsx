"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, Sparkles, X } from "lucide-react";
import { FormCard } from "@/components/dashboard/FormCard";
import { ProductForm } from "@/components/products/ProductForm";
import { useMe } from "@/lib/useMe";

const NUDGE_SEEN_KEY = "cor1x.sellerNudgeSeen";

export default function NewProductPage() {
  const router = useRouter();
  const { me } = useMe();
  const [nudgeVisible, setNudgeVisible] = useState(false);
  const [checked, setChecked] = useState(false);

  // Gate check — user must be verified (Primary + Business + Bank all complete)
  useEffect(() => {
    if (!me) return;
    if (me.status !== "verified") {
      router.replace("/dashboard/products");
      return;
    }
    // One-time seller-nudge check
    const sellerDone = me.completion.seller;
    const nudgeSeen =
      typeof window !== "undefined" &&
      window.localStorage.getItem(NUDGE_SEEN_KEY) === "1";
    if (!sellerDone && !nudgeSeen) {
      setNudgeVisible(true);
    }
    setChecked(true);
  }, [me, router]);

  const dismissNudge = () => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(NUDGE_SEEN_KEY, "1");
    }
    setNudgeVisible(false);
  };

  if (!checked) return null;

  if (nudgeVisible) {
    return (
      <div className="mx-auto max-w-2xl">
        <div className="surface relative p-6 sm:p-7">
          <button
            type="button"
            onClick={dismissNudge}
            aria-label="Dismiss"
            className="absolute right-3 top-3 rounded-full p-1.5 text-paper-muted transition-colors hover:bg-ink-elevated hover:text-paper"
          >
            <X className="h-3.5 w-3.5" />
          </button>

          <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-accent/10 text-accent">
            <Sparkles className="h-4 w-4" aria-hidden />
          </span>
          <p className="mt-4 text-[10px] uppercase tracking-widest text-paper-muted">
            One more thing · optional
          </p>
          <h2 className="mt-1 text-display text-paper">Boost your trust score</h2>
          <p className="mt-3 text-sm text-paper-muted">
            Adding Udyam, Aadhaar, and TAN helps buyers verify you faster and can
            raise your trust score. All fields are optional — you can skip and
            publish your product right away.
          </p>

          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/dashboard/profile/seller"
              onClick={dismissNudge}
              className="btn-primary"
            >
              Add seller details <ArrowRight aria-hidden className="h-4 w-4" />
            </Link>
            <button type="button" onClick={dismissNudge} className="btn-ghost">
              Skip for now
            </button>
          </div>

          <p className="mt-5 text-[11px] text-paper-muted/70">
            You&apos;ll only see this once. Continue to the product form after
            choosing either option.
          </p>
        </div>
      </div>
    );
  }

  return (
    <FormCard
      eyebrow="Add product"
      title="New listing"
      subtitle="Publishing your first product will mark you as a seller on Cor1x."
    >
      <ProductForm />
    </FormCard>
  );
}
