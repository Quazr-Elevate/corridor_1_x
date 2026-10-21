import { ClosingCta } from "@/components/landing/ClosingCta";
import { CommodityStrip } from "@/components/landing/CommodityStrip";
import { CorridorSection } from "@/components/landing/CorridorSection";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { LandingFooter } from "@/components/landing/LandingFooter";
import { LandingHero } from "@/components/landing/LandingHero";
import { ProofBand } from "@/components/landing/ProofBand";
import { publicApi } from "@/lib/publicApi";

/**
 * Landing — the public front door. A night screen over the port photograph
 * (the promise + the way in), then on ink: the three guarantees, the
 * corridor (map + Gulf photograph), how it works in three photographed
 * steps, the commodities in the market, and a closing call.
 */

/** Live lot counts by category (lower-case keys). Never blocks the page for long; empty on failure. */
async function liveCounts(): Promise<Record<string, number>> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const timeout = new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error("timeout")), 1500);
    });
    const facets = await Promise.race([publicApi.facets(), timeout]);
    return Object.fromEntries(facets.categories.map((c) => [c.value.toLowerCase(), c.count]));
  } catch {
    return {};
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export default async function LandingPage() {
  const counts = await liveCounts();
  return (
    <div data-surface="tower" className="min-h-dvh overflow-x-clip bg-ink text-fg">
      <main>
        <LandingHero />
        <ProofBand />
        <CorridorSection />
        <HowItWorks />
        <CommodityStrip counts={counts} />
        <ClosingCta />
      </main>
      <LandingFooter />
    </div>
  );
}
