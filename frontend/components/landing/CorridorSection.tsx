import { CorridorMap } from "@/components/art/CorridorMap";
import { Photo } from "@/components/art/Photo";
import { PORTS } from "@/components/art/map/geo";
import { Reveal } from "@/components/motion/Reveal";
import { MEDIA } from "@/lib/media";
import { MountInView } from "./MountInView";
import { SectionHead, landingWrap } from "./SectionHead";

/**
 * The corridor, both banks: the drawn India ⇄ UAE map on the Indian side,
 * the Dubai / Jebel Ali dusk photograph on the Gulf side.
 */
const INDIA = (["mundra", "kandla", "nhava-sheva", "kakinada"] as const).map((p) => PORTS[p].name);
const UAE = (["jebel-ali", "khalifa", "sharjah"] as const).map((p) => PORTS[p].name);

export function CorridorSection() {
  return (
    <section aria-labelledby="corridor-title" className={`${landingWrap} pt-24 sm:pt-32`}>
      <SectionHead
        id="corridor-title"
        eyebrow="The corridor"
        title={
          <>
            Indian mills to Gulf importers,
            <br className="hidden md:block" /> on one line.
          </>
        }
        body="Four Indian ports, three in the UAE. Whichever side you trade from, the company on the other side has been checked first."
      />

      <div className="mt-10 grid gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <Reveal className="relief flex flex-col overflow-hidden rounded-[30px] p-5 sm:p-7">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="t-label text-fg-3">India side</p>
              <p className="t-title2 mt-1.5 text-cream">India ⇄ UAE</p>
            </div>
            <span className="t-label rounded-full bg-lime-soft px-2.5 py-1 text-accent">Arabian Sea lanes</span>
          </div>
          <MountInView aspect={4 / 3} className="mt-4 w-full">
            <CorridorMap surface="tower" aspect={4 / 3} title="India ⇄ UAE corridor" />
          </MountInView>
          <ul className="t-code mt-4 flex flex-wrap gap-x-4 gap-y-1.5 border-t border-line pt-4 text-fg-2">
            {INDIA.map((name) => (
              <li key={name} className="flex items-center gap-1.5">
                <span aria-hidden="true" className="size-1.5 rounded-full bg-fg-3" />
                {name}
              </li>
            ))}
          </ul>
        </Reveal>

        <Reveal
          delay={0.08}
          className="relative isolate flex min-h-[380px] flex-col sm:min-h-[440px] justify-end overflow-hidden rounded-[30px] p-5 shadow-[inset_0_0_0_1px_rgb(255_255_255/0.07),0_24px_48px_-26px_rgb(0_0_0/0.9)] sm:p-7"
        >
          <Photo
            media={MEDIA.dubaiDusk}
            fill
            sizes="(min-width: 1024px) 46vw, 100vw"
            objectPosition="60% center"
            className="-z-10"
          />
          <div aria-hidden="true" className="absolute inset-0 -z-10 bg-gradient-to-t from-ink/85 via-ink/30 to-ink/10" />
          <p className="t-label text-cream/70">UAE side</p>
          <p className="t-title2 mt-1.5 text-cream">Jebel Ali, at dusk.</p>
          <p className="t-sub mt-2 max-w-[42ch] text-cream/75">
            Where Indian rice, sugar and spices land for distribution across the Gulf.
          </p>
          <ul className="t-code mt-4 flex flex-wrap gap-x-4 gap-y-1.5 border-t border-white/10 pt-4 text-cream/80">
            {UAE.map((name) => (
              <li key={name} className="flex items-center gap-1.5">
                <span aria-hidden="true" className="size-1.5 rounded-full bg-lime" />
                {name}
              </li>
            ))}
          </ul>
        </Reveal>
      </div>
    </section>
  );
}
