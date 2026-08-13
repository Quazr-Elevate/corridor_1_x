"use client";

import { useState } from "react";
import Image from "next/image";
import { CheckCircle2 } from "lucide-react";
import { BuyerFlow } from "./BuyerFlow";

export function BuyerOnboardingClient() {
  const [done, setDone] = useState(false);

  if (done) return <SuccessCard />;

  return (
    <main className="min-h-screen bg-white">
      {/* One mobile-first column holds the hero and form so they share the same visual scale */}
      <div className="mx-auto w-full max-w-md px-5 pb-16 pt-6 sm:max-w-lg sm:px-6 sm:pt-8 lg:max-w-xl">
        {/* Hero image — sized to the column, not the viewport. Image already carries
            brand, headline, supporting text and the three feature icons. */}
        <Image
          src="/buyer-hero.png"
          alt="Cor1x — Buy with confidence. Access verified suppliers. Every trade. Every time. Verified Counterparties. Autonomous Settlement. Circumvention Protection."
          width={1774}
          height={887}
          sizes="(min-width: 1024px) 1200px, (min-width: 640px) 1024px, 100vw"
          quality={100}
          priority
          className="h-auto w-full select-none"
        />

        <section className="mt-6 surface p-5 sm:p-6">
          <BuyerFlow onComplete={() => setDone(true)} />
        </section>

        <p className="mt-6 flex items-center justify-center gap-1.5 text-xs text-mute">
          <span aria-hidden>🔒</span>
          Your data is secure and never shared.
        </p>
      </div>
    </main>
  );
}

function SuccessCard() {
  return (
    <main className="mx-auto flex min-h-[80vh] w-full max-w-md flex-col items-center justify-center px-5 py-10 text-center">
      <div className="inline-flex h-14 w-14 items-center justify-center rounded-full bg-accent-soft text-accent">
        <CheckCircle2 className="h-8 w-8" aria-hidden />
      </div>
      <h1 className="mt-5 text-display text-ink">You&apos;re in.</h1>
      <p className="mt-2 text-sm text-mute">
        We&apos;ve received your details. An admin will review and verify your account shortly.
      </p>
      <p className="mt-6 text-xs text-mute-soft">
        You&apos;ll get an SMS once your account is verified.
      </p>
    </main>
  );
}
