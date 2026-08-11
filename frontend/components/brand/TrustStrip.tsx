import { ShieldCheck, FileLock2, Scale } from "lucide-react";

const items = [
  {
    icon: ShieldCheck,
    title: "Verified Counterparties",
    body: "Every participant is verified.",
  },
  {
    icon: FileLock2,
    title: "Autonomous Settlement",
    body: "Escrow-secured. Milestone-based release.",
  },
  {
    icon: Scale,
    title: "Circumvention Protection",
    body: "Fair trade. Protected by design.",
  },
];

export function TrustStrip() {
  return (
    <section
      aria-label="Platform guarantees"
      className="mt-8 rounded-card border border-line-soft bg-paper-soft px-4 py-5"
    >
      <ul className="grid gap-4 sm:grid-cols-3">
        {items.map(({ icon: Icon, title, body }) => (
          <li key={title} className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white ring-1 ring-line-soft">
              <Icon aria-hidden className="h-4 w-4 text-ink" />
            </span>
            <div>
              <p className="text-sm font-semibold leading-tight text-ink">{title}</p>
              <p className="mt-0.5 text-xs leading-snug text-mute">{body}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
