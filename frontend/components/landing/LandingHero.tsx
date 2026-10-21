import Link from "next/link";
import type { CSSProperties } from "react";
import { NightBackdrop, NightCard, NightWordmark } from "@/components/shell/NightShell";
import { LinkButton } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { landingWrap } from "./SectionHead";

/**
 * The front door — one night screen over the port photograph, built like
 * the reference's arrival: the promise and the way in sit on the dark
 * water (left), the lit port carries the right. First screen, so the
 * arrival is CSS (`animate-rise`), visible before hydration.
 */
const delay = (ms: number): CSSProperties => ({ animationDelay: `${ms}ms` });

const navLink =
  "t-sub flex h-9 items-center whitespace-nowrap rounded-full px-3.5 font-medium text-fg-2 transition-colors duration-300 ease-expo hover:bg-white/[0.07] hover:text-fg";

export function LandingHero() {
  return (
    <section aria-labelledby="hero-title" className="relative isolate min-h-dvh overflow-hidden">
      <NightBackdrop scrim="text" />
      {/* hand the photo over to the ink below */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 h-32 bg-gradient-to-b from-transparent to-ink"
      />

      <div className={`${landingWrap} relative z-10 flex min-h-dvh flex-col py-6 sm:py-10`}>
        <header className="flex items-center justify-between gap-4">
          <NightWordmark />
          <nav aria-label="Primary" className="glass-night flex items-center gap-1 rounded-full p-1">
            <Link href="/products" className={`${navLink} hidden sm:flex`}>
              Market
            </Link>
            <Link href="/login" className={navLink}>
              Sign in
            </Link>
          </nav>
        </header>

        <div className="flex flex-1 items-center py-12 sm:py-16">
          <div className="w-full max-w-[620px]">
            <p className="t-label animate-rise text-fg-3">
              Verified commodity trade · <span className="text-accent">India ⇄ UAE</span>
            </p>
            <h1
              id="hero-title"
              className="t-hero mt-5 animate-rise text-cream sm:text-[64px] xl:text-[76px]"
              style={delay(80)}
            >
              Trade direct.
              <br />
              Settle certain.
            </h1>
            <p
              className="t-body mt-5 max-w-[44ch] animate-rise text-cream/75 sm:text-[17px]"
              style={delay(160)}
            >
              Verified before contact. Masked until escrow. Released on delivery. Rice, sugar, wheat,
              pulses and spices between India and the Gulf.
            </p>

            <NightCard className="mt-10 max-w-[440px] p-6 sm:p-7" style={delay(240)}>
              <p className="t-label text-fg-3">Start here</p>
              <p className="t-title3 mt-2 text-cream">Verify once. Trade with known names.</p>
              <div className="mt-5 flex flex-col gap-3">
                <LinkButton href="/signup" variant="night" size="lg" block iconRight="arrow-right">
                  Get your company verified
                </LinkButton>
                <LinkButton href="/login" variant="night-quiet" size="lg" block>
                  Sign in
                </LinkButton>
              </div>
              <Link
                href="/products"
                className="t-callout mt-5 inline-flex items-center gap-1.5 rounded-md text-fg-2 transition-colors hover:text-cream"
              >
                Browse the market
                <Icon name="chevron-right" size={15} />
              </Link>
            </NightCard>
          </div>
        </div>

        <a
          href="#how"
          className="t-label inline-flex w-fit animate-fade items-center gap-2 rounded-full text-cream/60 transition-colors hover:text-cream"
          style={delay(600)}
        >
          <Icon name="chevron-down" size={14} />
          How Corridor works
        </a>
      </div>
    </section>
  );
}
