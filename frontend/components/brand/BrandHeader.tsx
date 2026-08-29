import Image from "next/image";
import { HeroShip } from "./HeroShip";
import { MorseDashes } from "./MorseDashes";

interface BrandHeaderProps {
  eyebrow: string;
  /**
   * Two-part title. Renders inline as `<lead> <highlight>` — `highlight`
   * is rendered with the chartreuse→violet gradient text.
   */
  title: { lead: string; highlight: string };
  subtitle: string;
}

/**
 * Onboarding page header. Wordmark top-left, brand mark top-right, then a
 * tight cinematic display title with a chartreuse→violet gradient accent
 * on the highlighted phrase. Reveal is pure CSS `.enter` — bulletproof
 * post-hydration.
 */
export function BrandHeader({ eyebrow, title, subtitle }: BrandHeaderProps) {
  return (
    <header className="relative">
      <div className="flex items-center justify-between gap-4 enter">
        <div className="flex items-center">
          <Image
            src="/brand/logo.png"
            alt="Corridor One X"
            width={1998}
            height={320}
            priority
            className="h-5 w-auto select-none sm:h-6"
          />
        </div>

        <div className="relative h-11 w-11 shrink-0 sm:h-12 sm:w-12">
          <HeroShip className="h-full w-full" />
        </div>
      </div>

      <div className="mt-7 sm:mt-9">
        <p className="chip enter" data-delay="2">
          <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" />
          {eyebrow}
        </p>

        <h1
          className="mt-3 text-display sm:text-display-lg text-paper enter"
          data-delay="3"
        >
          {title.lead}{" "}
          <span className="text-gradient">{title.highlight}</span>
        </h1>

        <p
          className="mt-2.5 max-w-md text-sm leading-relaxed text-paper-muted enter"
          data-delay="4"
        >
          {subtitle}
        </p>

        {/* Splash-echo: morse dashes tie the auth screens back to the
            landing page's rhythm. Subtle, aligned to the eyebrow start. */}
        <MorseDashes className="mt-4 justify-start" count={6} />
      </div>
    </header>
  );
}
