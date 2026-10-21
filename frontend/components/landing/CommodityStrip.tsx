import Link from "next/link";
import { Photo } from "@/components/art/Photo";
import { Stagger, StaggerItem } from "@/components/motion/Stagger";
import { Icon } from "@/components/ui/Icon";
import { COMMODITY_PHOTOS, type CommodityCategory, type MediaEntry } from "@/lib/media";
import { SectionHead, landingWrap } from "./SectionHead";

/** The five categories we have macro photography for, in market order. */
const CATEGORIES = (["Rice", "Sugar", "Wheat", "Pulses", "Spices"] as const satisfies readonly CommodityCategory[]).map(
  (name) => ({ name, media: COMMODITY_PHOTOS[name] as MediaEntry }),
);

/**
 * Commodity strip — one tile per category, each a way into the market
 * filtered to it. `counts` are the live market's real lot counts by
 * category (lower-case keys); without one, the tile just says "Browse".
 */
export function CommodityStrip({ counts }: { counts: Readonly<Record<string, number>> }) {
  return (
    <section aria-labelledby="commodities-title" className="pt-24 sm:pt-32">
      <div className={landingWrap}>
        <SectionHead
          id="commodities-title"
          eyebrow="In the market"
          title="What moves on the corridor."
          body="Agri-commodities from Indian mills and growers, listed by the companies that hold them."
          aside={
            <Link
              href="/products"
              className="t-callout inline-flex items-center gap-1.5 rounded-md font-medium text-cream transition-colors hover:text-accent"
            >
              Browse the market
              <Icon name="arrow-right" size={16} />
            </Link>
          }
        />
      </div>

      <div className={`${landingWrap} mt-10`}>
        <Stagger
          as="ul"
          className="no-scrollbar -mx-4 flex snap-x snap-mandatory scroll-px-4 gap-4 overflow-x-auto px-4 pb-2 sm:-mx-10 sm:scroll-px-10 sm:px-10 lg:mx-0 lg:grid lg:grid-cols-5 lg:overflow-visible lg:px-0 lg:pb-0"
        >
          {CATEGORIES.map(({ name, media }) => {
            const n = counts[name.toLowerCase()] ?? 0;
            return (
              <StaggerItem as="li" key={name} className="w-[64vw] max-w-[260px] shrink-0 snap-start lg:w-auto lg:max-w-none">
                <Link
                  href={`/products?category=${encodeURIComponent(name)}`}
                  className="group relative isolate block overflow-hidden rounded-[26px] shadow-[inset_0_0_0_1px_rgb(255_255_255/0.07),0_24px_48px_-26px_rgb(0_0_0/0.9)]"
                >
                  <Photo
                    media={media}
                    aspect={4 / 5}
                    decorative
                    sizes="(min-width: 1024px) 19vw, 64vw"
                    className="-z-10"
                    imgClassName="transition-[filter] duration-500 ease-expo group-hover:brightness-110"
                  />
                  <div
                    aria-hidden="true"
                    className="absolute inset-0 bg-gradient-to-t from-ink/80 via-ink/15 to-transparent"
                  />
                  <span
                    aria-hidden="true"
                    className="absolute right-3 top-3 grid size-9 place-items-center rounded-full bg-ink/40 text-cream opacity-0 backdrop-blur-md transition-opacity duration-300 ease-expo group-hover:opacity-100 group-focus-visible:opacity-100"
                  >
                    <Icon name="arrow-up-right" size={16} />
                  </span>
                  <div className="absolute inset-x-0 bottom-0 p-4 sm:p-5">
                    <p className="t-title2 text-cream">{name}</p>
                    <p className="t-label mt-1.5 text-cream/70">
                      {n > 0 ? `${n} ${n === 1 ? "lot" : "lots"} live` : "Browse"}
                    </p>
                  </div>
                </Link>
              </StaggerItem>
            );
          })}
        </Stagger>
      </div>
    </section>
  );
}
