import { Photo } from "@/components/art/Photo";
import { Stagger, StaggerItem } from "@/components/motion/Stagger";
import { Icon, type IconName } from "@/components/ui/Icon";
import { MEDIA, type MediaEntry } from "@/lib/media";
import { SectionHead, landingWrap } from "./SectionHead";

/** How the product really works today: Passport → listing → contact reveal. */
const STEPS: ReadonlyArray<{
  media: MediaEntry;
  label: string;
  icon: IconName;
  title: string;
  body: string;
}> = [
  {
    media: MEDIA.inspector,
    label: "Verification",
    icon: "passport",
    title: "Get your company verified",
    body: "Fill in your Corridor Passport and send it for review. Our ops team checks every company before it can reach anyone.",
  },
  {
    media: MEDIA.warehouse,
    label: "Listing",
    icon: "sack",
    title: "List what you have",
    body: "Publish lots with variety, volume, origin and packing. Buyers find them in the market, filtered to what they source.",
  },
  {
    media: MEDIA.portDay,
    label: "Trade",
    icon: "ship",
    title: "Meet your counterparty",
    body: "A verified buyer holds to reveal the seller’s contact. Both sides are told, and the deal is yours to make — direct.",
  },
];

export function HowItWorks() {
  return (
    <section id="how" aria-labelledby="how-title" className={`${landingWrap} scroll-mt-8 pt-24 sm:pt-32`}>
      <SectionHead
        id="how-title"
        eyebrow="How Corridor works"
        title="Three steps. No middlemen."
        body="Verification comes first, so everyone you meet here has been checked — and nobody sits between you and the other side."
      />

      <Stagger as="ol" className="mt-10 grid gap-5 lg:grid-cols-3">
        {STEPS.map((s, i) => (
          <StaggerItem
            as="li"
            key={s.label}
            className="relief flex flex-col rounded-[30px] p-3 md:max-lg:grid md:max-lg:grid-cols-[minmax(0,280px)_minmax(0,1fr)] md:max-lg:items-center md:max-lg:gap-3"
          >
            <Photo
              media={s.media}
              aspect={4 / 3}
              rounded={22}
              sizes="(min-width: 1024px) 31vw, (min-width: 768px) 280px, 92vw"
            >
              <span
                aria-hidden="true"
                className="pointer-events-none absolute inset-0 rounded-[inherit] shadow-[inset_0_0_0_1px_rgb(255_255_255/0.06)]"
              />
            </Photo>
            <div className="flex flex-1 flex-col px-3 pb-3 pt-5 sm:px-4">
              <div className="flex items-center justify-between gap-3">
                <p className="t-label text-fg-3">
                  Step 0{i + 1} · <span className="text-fg-2">{s.label}</span>
                </p>
                <span className="grid size-9 place-items-center rounded-full text-fg-2 shadow-[inset_0_0_0_1px_var(--c-line-2)]">
                  <Icon name={s.icon} size={17} />
                </span>
              </div>
              <h3 className="t-title2 mt-3 text-cream">{s.title}</h3>
              <p className="t-sub mt-2 text-fg-2">{s.body}</p>
            </div>
          </StaggerItem>
        ))}
      </Stagger>
    </section>
  );
}
