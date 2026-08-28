import Link from "next/link";
import Image from "next/image";
import { AmbientBackground } from "@/components/brand/AmbientBackground";
import { HeroShip } from "@/components/brand/HeroShip";

/**
 * Landing page. Public. No data fetching. Points visitors at either
 * signup (new users) or login (returning) and hints at the product
 * catalog once that ships.
 */
export default function Landing() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-ink text-paper">
      <AmbientBackground />

      <div className="relative mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-5 py-14">
        <header className="flex items-center justify-between enter">
          <Image
            src="/brand/logo.png"
            alt="Corridor One X"
            width={1998}
            height={320}
            priority
            className="h-6 w-auto select-none sm:h-7"
          />
          <div className="flex items-center gap-3 text-xs">
            <Link
              href="/login"
              className="rounded-full border border-line-soft px-3 py-1.5 text-paper-muted transition-colors hover:text-paper"
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className="rounded-full bg-accent px-3 py-1.5 font-medium text-accent-fg hover:bg-accent-hover"
            >
              Get started
            </Link>
          </div>
        </header>

        <section className="mt-16">
          <p className="chip enter" data-delay="2">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" />
            Verified commodity trade infrastructure
          </p>
          <h1
            className="mt-4 text-display sm:text-display-lg text-paper enter"
            data-delay="3"
          >
            Trade direct.{" "}
            <span className="text-gradient">Settle certain.</span>
          </h1>
          <p
            className="mt-3 max-w-lg text-sm leading-relaxed text-paper-muted sm:text-base enter"
            data-delay="4"
          >
            Cor1x connects verified rice producers, exporters, and importers
            through a single dashboard. KYB clearance before contact. Contact
            details revealed only after both sides are verified.
          </p>

          <div className="mt-8 flex flex-wrap gap-3 enter" data-delay="5">
            <Link
              href="/signup"
              className="btn-primary"
            >
              Create your account
            </Link>
            <Link href="/products" className="btn-ghost">
              Browse the catalog
            </Link>
          </div>
        </section>

        <div
          className="pointer-events-none absolute right-6 top-14 h-16 w-16 sm:h-20 sm:w-20"
          aria-hidden
        >
          <HeroShip className="h-full w-full" />
        </div>

        <footer className="mt-auto pt-16 text-xs text-paper-muted">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>© 2026 Corridor One X</span>
            <div className="flex items-center gap-4">
              <Link href="/privacy" className="hover:text-paper">
                Privacy
              </Link>
              <Link href="/terms" className="hover:text-paper">
                Terms
              </Link>
              <a
                href="mailto:privacy@cor1x.com"
                className="hover:text-paper"
              >
                Grievance
              </a>
            </div>
          </div>
        </footer>
      </div>
    </main>
  );
}
