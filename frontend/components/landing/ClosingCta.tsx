import { Photo } from "@/components/art/Photo";
import { Reveal } from "@/components/motion/Reveal";
import { LinkButton } from "@/components/ui/Button";
import { MEDIA } from "@/lib/media";
import { landingWrap } from "./SectionHead";

/** The last word: the night port again, behind the way in. */
export function ClosingCta() {
  return (
    <section aria-labelledby="closing-title" className={`${landingWrap} pt-24 sm:pt-32`}>
      <Reveal className="solid-panel relative isolate overflow-hidden rounded-[34px] px-6 py-10 sm:px-12 sm:py-16">
        <Photo
          media={MEDIA.portNight}
          fill
          decorative
          objectPosition="75% 40%"
          sizes="(min-width: 1360px) 1280px, 100vw"
          className="-z-10"
        />
        <div
          aria-hidden="true"
          className="absolute inset-0 -z-10 bg-ink/75 md:bg-transparent md:bg-gradient-to-r md:from-ink md:via-ink/75 md:to-ink/10"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -left-24 -top-24 size-[22rem] rounded-full bg-lime/[0.08] blur-3xl"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-32 left-[20%] size-[26rem] rounded-full blur-3xl"
          style={{ background: "radial-gradient(closest-side, rgb(255 168 84 / 0.12), rgb(255 168 84 / 0))" }}
        />
        <div className="relative flex flex-wrap items-end justify-between gap-8">
          <div className="max-w-[620px]">
            <p className="t-label text-accent">Corridor Passport</p>
            <h2 id="closing-title" className="t-large mt-4 text-cream">
              Verify once.
              <br />
              Trade with known names.
            </h2>
            <p className="t-body mt-4 max-w-[48ch] text-fg-2">
              One review by our ops team, and your company carries the Verified badge on every lot you
              list and every buyer you meet.
            </p>
          </div>
          <div className="glass-night flex w-full flex-col gap-3 rounded-[26px] p-3 sm:w-auto sm:min-w-[320px]">
            <LinkButton href="/signup" variant="night" size="lg" block iconRight="arrow-right">
              Get your company verified
            </LinkButton>
            <LinkButton href="/login" variant="night-quiet" size="lg" block>
              Sign in
            </LinkButton>
          </div>
        </div>
      </Reveal>
    </section>
  );
}
