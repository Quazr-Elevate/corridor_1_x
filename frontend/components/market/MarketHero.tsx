import type { ReactNode } from "react";
import { Photo } from "@/components/art/Photo";
import { MEDIA } from "@/lib/media";

/**
 * Photo-led hero band for the public market — the warehouse photograph
 * under the reference's ink gradients (left-to-right for the copy, a
 * bottom fade for the figures), cream type on top. Server-safe.
 */
export function MarketHero({
  eyebrow,
  title,
  subtitle,
  stats,
}: {
  eyebrow: ReactNode;
  title: ReactNode;
  subtitle: ReactNode;
  /** Real figures only (from the catalog facets). */
  stats: ReadonlyArray<{ label: string; value: ReactNode }>;
}) {
  return (
    <section
      aria-labelledby="market-title"
      className="grain relative isolate animate-rise overflow-hidden rounded-[34px] bg-ink text-cream shadow-[0_40px_80px_-40px_rgb(60_45_20/0.55)]"
    >
      <Photo
        media={MEDIA.warehouse}
        fill
        priority
        decorative
        sizes="(min-width: 1280px) 1180px, 100vw"
        objectPosition="62% 55%"
      />
      <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-r from-ink/80 via-ink/45 to-ink/5" />
      <div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-3/4 bg-gradient-to-t from-ink/75 via-ink/30 to-transparent" />
      {/* warm lamp glow, as on the night arrival */}
      <div
        aria-hidden="true"
        className="animate-drift absolute -right-24 -top-24 h-[360px] w-[460px] rounded-full blur-3xl"
        style={{ background: "radial-gradient(closest-side, rgb(255 196 120 / 0.22), rgb(255 196 120 / 0))" }}
      />

      <div className="relative flex min-h-[340px] flex-col justify-end gap-8 p-6 sm:min-h-[380px] sm:p-10 lg:min-h-[400px] lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-xl">
          <p className="t-label text-cream/75">{eyebrow}</p>
          <h1 id="market-title" className="t-hero mt-3 text-cream">
            {title}
          </h1>
          <p className="t-body mt-4 max-w-md text-cream/85">{subtitle}</p>
        </div>
        {stats.length ? (
          <dl className="flex flex-wrap gap-x-6 gap-y-4 sm:gap-x-8 lg:justify-end lg:text-right">
            {stats.map((s) => (
              <div key={s.label} className="min-w-0">
                <dt className="t-label text-cream/70">{s.label}</dt>
                <dd className="tabular mt-1.5 text-[24px] font-medium leading-none tracking-[-0.03em] text-cream sm:text-[28px]">
                  {s.value}
                </dd>
              </div>
            ))}
          </dl>
        ) : null}
      </div>
    </section>
  );
}
