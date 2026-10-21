import type { ComponentType } from "react";
import { notFound } from "next/navigation";
import {
  ART_CATEGORIES,
  CommodityArt,
  CorridorMap,
  IsoContainerStack,
  IsoCrane,
  IsoGrainHeap,
  IsoRiceSack,
  IsoShip,
  IsoWarehouse,
  type ArtProps,
} from "@/components/art";

/**
 * Dev-only gallery of the drawn library: every piece on the cream trader
 * surface and the ink tower surface. `?focus=<Name>[&s=tower]` shows one
 * piece large for inspection (Name = an iso object, a commodity category,
 * or CorridorMap).
 */

const ISO: Record<string, ComponentType<ArtProps>> = {
  IsoContainerStack,
  IsoShip,
  IsoRiceSack,
  IsoGrainHeap,
  IsoWarehouse,
  IsoCrane,
};

const PHOTOS = ["rice", "pulses", "spices"] as const;

export default function GalleryPage({ searchParams }: { searchParams: { focus?: string; s?: string } }) {
  if (process.env.NODE_ENV === "production") notFound();

  const tower = searchParams.s === "tower";
  const focus = searchParams.focus;
  if (focus) {
    const Iso = ISO[focus];
    const cat = ART_CATEGORIES.find((c) => c === focus);
    return (
      <main data-surface={tower ? "tower" : undefined} className="min-h-dvh bg-ground p-4">
        <div className="mx-auto max-w-[960px]">
          {Iso ? <Iso surface={tower ? "tower" : "trader"} title={focus} /> : null}
          {cat ? (
            <div className="relative aspect-[4/3] overflow-hidden rounded-[28px]">
              <CommodityArt category={cat} className="absolute inset-0 h-full" labelled />
            </div>
          ) : null}
          {focus === "CorridorMap" ? <CorridorMap surface={tower ? "tower" : "trader"} aspect={16 / 10} /> : null}
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-dvh pb-16">
      <header className="mx-auto max-w-page-wide px-4 pb-2 pt-10 sm:px-6">
        <p className="t-label text-fg-3">Dev only · components/art</p>
        <h1 className="t-large mt-2">Drawn library</h1>
        <p className="t-body mt-2 max-w-[60ch] text-fg-2">
          Fallback still-lifes for commodities without photographs, the India ⇄ UAE corridor map, and the isometric
          objects — on the cream trader surface and the ink control tower.
        </p>
      </header>

      {/* ── Commodities: photo tiles beside drawn tiles ── */}
      <section className="mx-auto max-w-page-wide px-4 pt-8 sm:px-6">
        <h2 className="t-label text-fg-3">Commodity art · 4:3 beside the macro photographs</h2>
        <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-3">
          {PHOTOS.map((p) => (
            <figure key={p} className="relief overflow-hidden rounded-[22px]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/media/gen/${p}-640.webp`} alt="" className="aspect-[4/3] w-full object-cover" />
              <figcaption className="t-label px-3 py-2 text-fg-3">Photo · {p}</figcaption>
            </figure>
          ))}
          {ART_CATEGORIES.map((c, i) => (
            <figure key={c} className="relief overflow-hidden rounded-[22px]">
              <div className="relative aspect-[4/3]">
                <CommodityArt category={c} variant={i} className="absolute inset-0 h-full" labelled />
              </div>
              <figcaption className="t-label px-3 py-2 text-fg-3">Drawn · {c}</figcaption>
            </figure>
          ))}
        </div>

        <h2 className="t-label mt-10 text-fg-3">Same art at 1:1 and 16:10 (slice crop)</h2>
        <div className="mt-4 grid grid-cols-3 gap-3 sm:grid-cols-6">
          {ART_CATEGORIES.map((c) => (
            <div key={c} className="relative aspect-square overflow-hidden rounded-[16px]">
              <CommodityArt category={c} className="absolute inset-0 h-full" />
            </div>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3">
          {ART_CATEGORIES.map((c) => (
            <div key={c} className="relative aspect-[16/10] overflow-hidden rounded-[20px]">
              <CommodityArt category={c} variant={7} className="absolute inset-0 h-full" />
            </div>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          {ART_CATEGORIES.map((c) => (
            <div key={c} className="relative size-14 overflow-hidden rounded-[14px]">
              <CommodityArt category={c} className="absolute inset-0 h-full" />
            </div>
          ))}
          <p className="t-foot text-fg-3">Thumbnails (56px)</p>
        </div>
      </section>

      {/* ── Corridor map ── */}
      <section className="mx-auto max-w-page-wide px-4 pt-12 sm:px-6">
        <h2 className="t-label text-fg-3">Corridor map · trader</h2>
        <div className="mt-4 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <div className="relief rounded-[34px] p-6">
            <p className="t-label text-fg-3">Corridor</p>
            <p className="t-title2 mt-1">India ⇄ UAE</p>
            <CorridorMap className="mt-4" aspect={16 / 10} />
          </div>
          <div className="relief rounded-[34px] p-6">
            <p className="t-label text-fg-3">Static · with counts</p>
            <CorridorMap className="mt-4" aspect={1} animated={false} counts={{ mundra: 12, "jebel-ali": 3 }} />
          </div>
        </div>
      </section>

      {/* ── Isometric objects · trader ── */}
      <section className="mx-auto max-w-page-wide px-4 pt-12 sm:px-6">
        <h2 className="t-label text-fg-3">Isometric objects · trader</h2>
        <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-3">
          {Object.entries(ISO).map(([k, C]) => (
            <figure key={k} className="relief rounded-[26px] p-3">
              <C title={k} />
              <figcaption className="t-label px-1 pt-1 text-fg-3">{k}</figcaption>
            </figure>
          ))}
        </div>
      </section>

      {/* ── Tower surface ── */}
      <div data-surface="tower" className="mt-12 bg-ground pb-12 text-fg">
        <section className="mx-auto max-w-page-wide px-4 pt-12 sm:px-6">
          <h2 className="t-label text-fg-3">Corridor map · control tower</h2>
          <div className="mt-4 grid gap-6 lg:grid-cols-[1fr_1.4fr]">
            <div className="relief rounded-[34px] p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="t-label text-fg-3">Corridor live</p>
                  <p className="t-title2 mt-1">India ⇄ UAE</p>
                </div>
              </div>
              <CorridorMap className="mt-2" surface="tower" aspect={1} />
            </div>
            <div className="relief rounded-[34px] p-6">
              <CorridorMap surface="tower" aspect={16 / 9} />
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-page-wide px-4 pt-12 sm:px-6">
          <h2 className="t-label text-fg-3">Commodity art · on ink</h2>
          <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
            {ART_CATEGORIES.map((c) => (
              <figure key={c} className="relief overflow-hidden rounded-[22px]">
                <div className="relative aspect-[4/3]">
                  <CommodityArt category={c} className="absolute inset-0 h-full" />
                </div>
                <figcaption className="t-label px-3 py-2 text-fg-3">{c}</figcaption>
              </figure>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-page-wide px-4 pt-12 sm:px-6">
          <h2 className="t-label text-fg-3">Isometric objects · tower</h2>
          <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-3">
            {Object.entries(ISO).map(([k, C]) => (
              <figure key={k} className="relief rounded-[26px] p-3">
                <C surface="tower" />
                <figcaption className="t-label px-1 pt-1 text-fg-3">{k}</figcaption>
              </figure>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
