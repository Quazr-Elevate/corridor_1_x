import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { SplashGlow } from "@/components/brand/SplashGlow";
import { MorseDashes } from "@/components/brand/MorseDashes";

/**
 * Landing / splash. Mirrors the mobile design canvas: warm chartreuse pool
 * top-left, star mark, wordmark, tagline, morse-dash breather, then Sign up
 * + Log in stacked. Trust line pinned near the safe-area bottom.
 *
 * Below the fold on desktop: a short value-prop strip + a browse-catalog
 * link. On mobile the splash fills the viewport and the rest scrolls in.
 * PWA-installed users see the same view — no separate splash asset needed.
 */
export default function Landing() {
  return (
    <main className="relative min-h-[100dvh] overflow-hidden bg-ink text-paper">
      <SplashGlow />

      {/* Splash — vertically centered, safe-area padded */}
      <section
        className="relative mx-auto flex min-h-[100dvh] w-full max-w-[440px] flex-col px-6"
        style={{
          paddingTop: "max(env(safe-area-inset-top), 40px)",
          paddingBottom: "max(env(safe-area-inset-bottom), 32px)",
        }}
      >
        <div className="flex flex-1 flex-col items-center justify-center text-center">
          <StarMark className="h-11 w-11" />
          <p className="mt-4 text-title font-medium tracking-tight text-paper">
            Corridor One X
          </p>
          <p className="mt-1 text-xs tracking-wide text-accent/80">
            Trade direct. Settle certain.
          </p>
          <MorseDashes className="mt-6" />
        </div>

        <div className="flex flex-col gap-2.5 pb-4">
          <Link
            href="/signup"
            className="flex h-12 items-center justify-center rounded-field bg-accent text-sm font-medium text-accent-fg transition-colors hover:bg-accent-hover"
          >
            Sign up
          </Link>
          <Link
            href="/login"
            className="flex h-12 items-center justify-center rounded-field border border-line bg-ink-elevated text-sm font-medium text-paper transition-colors hover:border-line-strong"
          >
            Log in
          </Link>
          <p className="mt-2 text-center text-[11px] text-paper-muted">
            <span
              aria-hidden
              className="mr-1 inline-block h-1 w-1 rounded-full bg-accent align-middle"
            />
            No unverified hands in between.
          </p>
        </div>
      </section>

      {/* Below the splash — brief value prop for scrollers / SEO. Hidden as
          "extra" on mobile so the splash reads clean; visible from md up. */}
      <section className="relative mx-auto max-w-3xl px-6 pb-14 md:pb-20">
        <div className="mx-auto grid gap-4 sm:grid-cols-3">
          <ValueCard title="Verified only" body="KYB clearance for both sides before any contact reveal." />
          <ValueCard title="Direct match" body="Buyers and sellers of rice, spice, grain — same dashboard." />
          <ValueCard title="Audit trail" body="Every reveal logged. Contact and consent, in one place." />
        </div>
        <div className="mt-8 flex items-center justify-center gap-2 text-xs text-paper-muted">
          <Link
            href="/products"
            className="inline-flex items-center gap-1 text-accent hover:underline underline-offset-4"
          >
            Browse the catalog
            <ArrowRight className="h-3 w-3" aria-hidden />
          </Link>
          <span aria-hidden>·</span>
          <Link href="/privacy" className="hover:text-paper">Privacy</Link>
          <span aria-hidden>·</span>
          <Link href="/terms" className="hover:text-paper">Terms</Link>
        </div>
      </section>
    </main>
  );
}

function StarMark({ className = "" }: { className?: string }) {
  // Same 4-point star used in the manifest icons — one primitive, everywhere.
  return (
    <svg viewBox="-160 -160 320 320" className={className} aria-hidden>
      <path
        d="M 0 -140 C 40 -40 40 -40 140 0 C 40 40 40 40 0 140 C -40 40 -40 40 -140 0 C -40 -40 -40 -40 0 -140 Z"
        fill="#D3EC4B"
      />
    </svg>
  );
}

function ValueCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-card border border-line-soft bg-ink-soft/60 px-4 py-4">
      <p className="text-xs font-medium tracking-wide text-accent">{title}</p>
      <p className="mt-1.5 text-xs leading-relaxed text-paper-muted">{body}</p>
    </div>
  );
}
