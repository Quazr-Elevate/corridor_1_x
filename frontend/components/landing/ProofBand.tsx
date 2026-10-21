import { Stagger, StaggerItem } from "@/components/motion/Stagger";
import { Icon, type IconName } from "@/components/ui/Icon";
import { landingWrap } from "./SectionHead";

/** The three guarantees, as one relief band right under the hero. */
const PROOF: ReadonlyArray<{ icon: IconName; title: string; body: string }> = [
  {
    icon: "shield",
    title: "Verified before contact",
    body: "Every company is checked by our ops team before it can reach anyone.",
  },
  {
    icon: "eye-off",
    title: "Masked until escrow",
    body: "Who you are stays hidden until the deal is secured.",
  },
  {
    icon: "vault",
    title: "Released on delivery",
    body: "Money moves when the goods arrive. Not before.",
  },
];

export function ProofBand() {
  return (
    <section aria-labelledby="proof-title" className={`${landingWrap} relative`}>
      <h2 id="proof-title" className="sr-only">
        What Corridor guarantees
      </h2>
      <Stagger
        as="ul"
        className="relief grid overflow-hidden rounded-[30px] sm:grid-cols-3"
      >
        {PROOF.map((p, i) => (
          <StaggerItem
            as="li"
            key={p.title}
            className="flex items-start gap-4 border-line p-6 max-sm:[&:not(:first-child)]:border-t sm:p-8 sm:[&:not(:first-child)]:border-l"
          >
            <span className="grid size-11 shrink-0 place-items-center rounded-full bg-lime-soft text-accent">
              <Icon name={p.icon} size={20} />
            </span>
            <div className="min-w-0">
              <p className="t-code text-fg-3">0{i + 1}</p>
              <h3 className="t-title3 mt-1 text-cream">{p.title}</h3>
              <p className="t-sub mt-1.5 text-fg-2">{p.body}</p>
            </div>
          </StaggerItem>
        ))}
      </Stagger>
    </section>
  );
}
