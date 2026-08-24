import { ShieldCheck, FileLock2, Scale } from "lucide-react";

const items = [
  {
    icon: ShieldCheck,
    title: "Verified counterparties",
    body: "KYB-cleared before contact.",
  },
  {
    icon: FileLock2,
    title: "Autonomous settlement",
    body: "Escrow · milestone release.",
  },
  {
    icon: Scale,
    title: "Circumvention protection",
    body: "Identity revealed post-escrow.",
  },
];

const delays = [5, 6, 7] as const;

export function TrustStrip() {
  return (
    <section
      aria-label="Platform guarantees"
      className="relative mt-6 rounded-card border border-line-soft bg-ink-soft/60 p-4 backdrop-blur-sm enter"
      data-delay="5"
    >
      <ul className="grid gap-3 sm:grid-cols-3">
        {items.map(({ icon: Icon, title, body }, i) => (
          <li
            key={title}
            className="flex items-start gap-2.5 enter"
            data-delay={delays[i]}
          >
            <span className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-ink-elevated ring-1 ring-line">
              <Icon aria-hidden className="h-3.5 w-3.5 text-accent" />
            </span>
            <div>
              <p className="text-xs font-medium leading-tight text-paper">
                {title}
              </p>
              <p className="mt-0.5 text-[11px] leading-snug text-paper-muted">
                {body}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
