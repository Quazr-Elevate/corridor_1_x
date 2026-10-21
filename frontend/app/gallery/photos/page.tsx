import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import { AmbientPhoto } from "@/components/art/AmbientPhoto";
import { Photo, PhotoThumb } from "@/components/art/Photo";
import { COMMODITY_CATEGORIES, MEDIA, MEDIA_KEYS, commodityPhoto } from "@/lib/media";

/**
 * Dev-only gallery for the photography layer: every photo in lib/media,
 * plus Photo / PhotoThumb / AmbientPhoto in the shapes the product uses.
 * http://localhost:3000/gallery/photos
 */
export default function PhotoGalleryPage() {
  if (process.env.NODE_ENV === "production") notFound();

  return (
    <div data-surface="trader" className="relative min-h-dvh text-fg">
      {/* Page background exactly as the reference trader home. */}
      <AmbientPhoto media={MEDIA.portDay} position="fixed" className="-z-10" />

      <main className="mx-auto w-full max-w-page-wide space-y-16 px-4 pb-24 pt-10 sm:px-8">
        <header className="animate-rise">
          <p className="t-label text-fg-3">Gallery · Photography</p>
          <h1 className="t-hero mt-3">Photo layer</h1>
          <p className="t-title3 mt-3 max-w-2xl font-normal text-fg-2">
            Every photograph in <code className="t-code">lib/media</code>, and the three ways pages use them.
            This page sits on <code className="t-code">&lt;AmbientPhoto media=portDay position=&quot;fixed&quot;&gt;</code>.
          </p>
        </header>

        {/* 1 · Night arrival: full-bleed, art-directed photo + overlays. */}
        <section aria-labelledby="g-night">
          <Heading id="g-night" eyebrow="Photo · fill · portrait · priority">
            Night arrival
          </Heading>
          <div
            data-surface="tower"
            className="relative min-h-[620px] overflow-hidden rounded-[34px] bg-ink text-fg"
          >
            <Photo
              media={MEDIA.portNight}
              portrait={MEDIA.portNightPortrait}
              fill
              priority
              decorative
              objectPosition="70% center"
              sizes="(min-width: 1320px) 1320px, 100vw"
            />
            <div className="absolute inset-0 bg-gradient-to-r from-ink/60 via-ink/25 to-transparent" />
            <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-ink/60 to-transparent" />
            <div
              className="pointer-events-none absolute left-[8%] top-[18%] h-[70%] w-[46%] rounded-full opacity-90 blur-3xl"
              style={{ background: "radial-gradient(closest-side, rgb(255 168 84 / 0.16), rgb(255 168 84 / 0))" }}
            />
            <div
              className="pointer-events-none absolute left-[2%] top-[4%] h-[40%] w-[28%] rounded-full blur-3xl"
              style={{ background: "radial-gradient(closest-side, rgb(196 216 46 / 0.08), rgb(196 216 46 / 0))" }}
            />
            <div className="relative z-10 flex min-h-[620px] items-center p-4 sm:p-10">
              <div className="glass-night w-full max-w-[460px] rounded-[34px] p-7 sm:p-9">
                <p className="t-label text-fg-3">
                  Gallery demo · <span className="text-lime">India ⇄ UAE</span>
                </p>
                <h3 className="t-large mt-3 text-cream">Night glass over the port.</h3>
                <p className="t-callout mt-3 text-fg-2">
                  Landscape on wide screens; the portrait crop on upright phones. Gradients from the left
                  and the bottom keep text above 4.5:1.
                </p>
                <div className="field-night mt-8 flex h-[52px] items-center px-4 text-[15px] text-fg-3">
                  field-night · 52px · 16px corners
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 2 · Ambient photo behind a cream section. */}
        <section aria-labelledby="g-ambient">
          <Heading id="g-ambient" eyebrow="AmbientPhoto · absolute">
            Cream ambient
          </Heading>
          <div className="relative overflow-hidden rounded-[34px] shadow-[inset_0_0_0_1px_var(--c-line)]">
            <AmbientPhoto media={MEDIA.warehouse} />
            <div className="relative px-5 py-10 sm:px-10 sm:py-14">
              <p className="t-label text-fg-3">warehouse · opacity 0.3 · blur 22 · multiply</p>
              <h3 className="t-large mt-3 max-w-xl">The photo is felt, not seen.</h3>
              <p className="t-body mt-3 max-w-xl text-fg-2">
                Content sits in relief on top. The layer fades to cream by 80% of its height.
              </p>
              <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {(["Rice", "Pulses", "Spices"] as const).map((c) => (
                  <li key={c} className="relief flex items-center gap-3 rounded-[26px] p-5">
                    <PhotoThumb media={commodityPhoto(c)} />
                    <div className="min-w-0">
                      <p className="t-headline">{c}</p>
                      <p className="t-sub text-fg-3">PhotoThumb · 44 · r14</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* 3 · Commodity thumbnails, with the drawn fallback. */}
        <section aria-labelledby="g-thumbs">
          <Heading id="g-thumbs" eyebrow="commodityPhoto(category) · PhotoThumb">
            Commodities
          </Heading>
          <ul className="flex flex-wrap gap-x-6 gap-y-5">
            {COMMODITY_CATEGORIES.map((c) => {
              const photo = commodityPhoto(c);
              return (
                <li key={c} className="flex w-[84px] flex-col items-center gap-2 text-center">
                  <PhotoThumb media={photo} size={64} radius={18} />
                  <span className="t-sub">{c}</span>
                  <span className="t-label text-fg-3">{photo ? "photo" : "drawn"}</span>
                </li>
              );
            })}
          </ul>
        </section>

        {/* 4 · A listing-style card photo. */}
        <section aria-labelledby="g-card">
          <Heading id="g-card" eyebrow="Photo · aspect 4/3 · rounded 20 · lazy">
            Card photography
          </Heading>
          <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {(["Rice", "Sugar", "Wheat", "Spices"] as const).map((c) => {
              const photo = commodityPhoto(c);
              return (
                <li key={c} className="relief relief-hover group rounded-card p-3">
                  {photo ? (
                    <Photo
                      media={photo}
                      aspect={4 / 3}
                      rounded={20}
                      sizes="(min-width: 1024px) 300px, (min-width: 640px) 45vw, 90vw"
                      imgClassName="transition-transform duration-700 ease-expo group-hover:scale-[1.02]"
                    />
                  ) : null}
                  <div className="px-2 pb-2 pt-4">
                    <p className="t-label text-fg-3">{c}</p>
                    <p className="t-title3 mt-1.5">{photo?.alt}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>

        {/* 5 · Every photo in the library. */}
        <section aria-labelledby="g-index">
          <Heading id="g-index" eyebrow="MEDIA · lib/media.ts">
            Library
          </Heading>
          <ul className="grid items-start gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {MEDIA_KEYS.map((k) => {
              const m = MEDIA[k];
              return (
                <li key={k} className="relief rounded-card p-3">
                  <Photo
                    media={m}
                    rounded={20}
                    aspect={m.aspect < 1 ? 3 / 4 : undefined}
                    sizes="(min-width: 1024px) 400px, (min-width: 640px) 45vw, 90vw"
                  />
                  <div className="space-y-1.5 px-2 pb-2 pt-4">
                    <p className="t-code text-fg">MEDIA.{k}</p>
                    <p className="t-label text-fg-3">
                      {m.width}×{m.height} · webp {m.widths.join(" / ")}
                    </p>
                    <p className="t-sub text-fg-2">{m.alt}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      </main>
    </div>
  );
}

function Heading({ id, eyebrow, children }: { id: string; eyebrow: string; children: ReactNode }) {
  return (
    <div className="mb-5">
      <p className="t-label text-fg-3">{eyebrow}</p>
      <h2 id={id} className="t-title2 mt-1.5">
        {children}
      </h2>
    </div>
  );
}
