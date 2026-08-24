"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2 } from "lucide-react";
import { AmbientBackground } from "@/components/brand/AmbientBackground";
import { BrandHeader } from "@/components/brand/BrandHeader";
import { TrustStrip } from "@/components/brand/TrustStrip";
import { HeroShip } from "@/components/brand/HeroShip";
import { BuyerFlow } from "./BuyerFlow";

const EASE = [0.22, 1, 0.36, 1] as const;

export function BuyerOnboardingClient() {
  const [done, setDone] = useState(false);

  return (
    <main className="relative min-h-screen overflow-hidden bg-ink text-paper">
      <AmbientBackground />

      <AnimatePresence mode="wait" initial={false}>
        {done ? (
          <SuccessCard key="success" />
        ) : (
          <motion.div
            key="form"
            className="relative mx-auto w-full max-w-[440px] px-4 pb-14 pt-6 sm:max-w-md sm:px-5 sm:pt-10 lg:max-w-[560px]"
            initial={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -80, filter: "blur(6px)" }}
            transition={{ duration: 0.5, ease: EASE }}
          >
            <BrandHeader
              eyebrow="Buyer · verified onboarding"
              title={{ lead: "Source with certainty.", highlight: "Pay with protection." }}
              subtitle="Access verified suppliers. Funds held in escrow until goods land. No wire-and-hope."
            />

            <section className="mt-8 surface p-4 sm:p-5 enter" data-delay="5">
              <BuyerFlow onComplete={() => setDone(true)} />
            </section>

            <TrustStrip />

            <p className="mt-6 flex items-center justify-center gap-1.5 text-[10px] uppercase tracking-widest text-paper-muted enter" data-delay="9">
              <span aria-hidden className="h-1 w-1 rounded-full bg-accent" />
              Encrypted · SOC-2 mindset · never shared
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}

function SuccessCard() {
  return (
    <div className="relative mx-auto flex min-h-screen max-w-sm items-center justify-center px-5 text-center enter-fade">
      <div className="w-full">
        <div className="mx-auto h-16 w-16 enter-fade">
          <HeroShip className="h-full w-full" />
        </div>

        <div
          className="mt-5 inline-flex h-11 w-11 items-center justify-center rounded-full bg-accent text-accent-fg enter-pop"
          data-delay="5"
          style={{
            boxShadow:
              "0 0 0 6px rgba(211,236,75,0.14), 0 0 32px -4px rgba(211,236,75,0.55), 0 0 48px -6px rgba(139,92,246,0.35)",
          }}
        >
          <CheckCircle2 className="h-6 w-6" aria-hidden strokeWidth={2.5} />
        </div>

        <h1 className="mt-6 text-display text-paper rise" data-delay="8">
          You&apos;re <span className="text-gradient">in.</span>
        </h1>
        <p
          className="mt-3 text-sm leading-relaxed text-paper-muted rise"
          data-delay="10"
        >
          We&apos;ve received your details. An admin will review and verify
          your account shortly.
        </p>
        <p
          className="mt-8 text-[10px] uppercase tracking-widest text-paper-muted/70 rise"
          data-delay="12"
        >
          You&apos;ll get an SMS once your account is verified.
        </p>
      </div>
    </div>
  );
}
