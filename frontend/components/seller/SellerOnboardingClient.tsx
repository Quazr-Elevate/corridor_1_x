"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Landmark, User } from "lucide-react";
import { AmbientBackground } from "@/components/brand/AmbientBackground";
import { BrandHeader } from "@/components/brand/BrandHeader";
import { TrustStrip } from "@/components/brand/TrustStrip";
import { HeroShip } from "@/components/brand/HeroShip";
import { Tabs, type TabItem } from "@/components/ui/Tabs";
import { GstinFlow } from "./GstinFlow";
import { PanFlow } from "./PanFlow";

type Path = "gstin" | "pan";

const tabs: TabItem<Path>[] = [
  { value: "gstin", label: "GSTIN", icon: <Landmark className="h-3.5 w-3.5" aria-hidden /> },
  { value: "pan", label: "PAN only", icon: <User className="h-3.5 w-3.5" aria-hidden /> },
];

const EASE = [0.22, 1, 0.36, 1] as const;

export function SellerOnboardingClient() {
  const [path, setPath] = useState<Path>("gstin");
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
              eyebrow="Seller · verified onboarding"
              title={{ lead: "List once.", highlight: "Reach verified buyers." }}
              subtitle="Verify your GSTIN or PAN to join a network of KYB-cleared buyers. Identity stays protected until escrow funds."
            />

            <div className="mt-8 enter" data-delay="5">
              <Tabs
                items={tabs}
                value={path}
                onChange={setPath}
                ariaLabel="Onboarding path"
              />
            </div>

            <section className="mt-3 surface p-4 sm:p-5 enter" data-delay="6">
              <AnimatePresence mode="wait">
                <motion.div
                  key={path}
                  initial={{ opacity: 0, x: path === "gstin" ? -8 : 8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: path === "gstin" ? 8 : -8 }}
                  transition={{ duration: 0.28, ease: EASE }}
                >
                  {path === "gstin" ? (
                    <GstinFlow onComplete={() => setDone(true)} />
                  ) : (
                    <PanFlow onComplete={() => setDone(true)} />
                  )}
                </motion.div>
              </AnimatePresence>
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

/**
 * Success card — form has just slid off to the left. This mounts fresh with:
 *   - ambient star fade
 *   - check icon spring-pop
 *   - headline + supporting lines slide up + fade in from bottom (staggered)
 */
function SuccessCard() {
  return (
    <div className="relative mx-auto flex min-h-screen max-w-sm items-center justify-center px-5 text-center enter-fade">
      <div className="w-full">
        <div className="mx-auto h-16 w-16 enter-fade">
          <HeroShip className="h-full w-full" />
        </div>

        {/* Tick: CSS spring-out pop, reliably fires post-hydration */}
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

        {/* Text lines: CSS `.rise` — slide up + fade in from the bottom */}
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
