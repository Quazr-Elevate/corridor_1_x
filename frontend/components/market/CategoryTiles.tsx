import Link from "next/link";
import { CommodityArt } from "@/components/art/CommodityArt";
import { Photo } from "@/components/art/Photo";
import { Icon } from "@/components/ui/Icon";
import { cn } from "@/lib/cn";
import { commodityPhoto } from "@/lib/media";
import { searchParamsFromFilters } from "@/lib/productFilters";
import type { CatalogFacets, CatalogFilters } from "@/lib/publicApi";

/** Categories with a macro photograph — always offered, even before they have lots. */
const PHOTO_CATEGORIES = ["Rice", "Sugar", "Wheat", "Pulses", "Spices"] as const;

/**
 * Commodity tiles that filter the market — the style guide's "Commodity
 * tiles": photography for the five macro shots, the drawn still-life for
 * the rest. Plain links (bookmarkable, work without JS); the chosen tile
 * is ringed and pressing it again clears the filter. Server-safe.
 */
export function CategoryTiles({ facets, filters }: { facets: CatalogFacets; filters: CatalogFilters }) {
  const counts = new Map(facets.categories.map((c) => [c.value, c.count]));
  const order: string[] = [
    ...facets.categories.map((c) => c.value),
    ...PHOTO_CATEGORIES.filter((c) => !counts.has(c)),
  ];
  if (filters.category && !order.includes(filters.category)) order.push(filters.category);
  const total = facets.categories.reduce((n, c) => n + c.count, 0);

  const href = (category: string | undefined) =>
    `/products${searchParamsFromFilters({ ...filters, category, offset: undefined })}`;

  return (
    <nav aria-label="Browse by commodity">
      <ul className="no-scrollbar -mx-4 flex snap-x snap-mandatory scroll-px-4 gap-3 overflow-x-auto px-4 pb-3 pt-1 sm:-mx-1 sm:grid sm:grid-cols-3 sm:gap-4 sm:overflow-visible sm:px-1 lg:grid-cols-6 xl:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]">
        <li className="w-[128px] shrink-0 snap-start sm:w-auto">
          <Link
            href={href(undefined)}
            aria-current={!filters.category ? "true" : undefined}
            aria-label={`All commodities — ${total} ${total === 1 ? "lot" : "lots"}`}
            className={cn(
              tileFrame,
              "bg-ink bg-[radial-gradient(120%_90%_at_0%_0%,rgb(196_216_46/0.16),transparent_55%)]",
              !filters.category && selectedRing,
            )}
          >
            <span className="absolute left-4 top-4 grid size-10 place-items-center rounded-full bg-white/[0.06] text-lime shadow-[inset_0_0_0_1px_rgb(255_255_255/0.1)]">
              <Icon name="grain" size={19} />
            </span>
            <TileText name="All lots" count={total} />
            {!filters.category ? <SelectedMark /> : null}
          </Link>
        </li>
        {order.map((c, i) => {
          const selected = filters.category === c;
          const n = counts.get(c) ?? 0;
          const media = commodityPhoto(c);
          return (
            <li key={c} className="w-[128px] shrink-0 snap-start sm:w-auto">
              <Link
                href={href(selected ? undefined : c)}
                aria-current={selected ? "true" : undefined}
                aria-label={`${c} — ${n ? `${n} ${n === 1 ? "lot" : "lots"}` : "no lots yet"}${selected ? " (selected, press to clear)" : ""}`}
                className={cn(tileFrame, "bg-[#e6dac2]", selected && selectedRing)}
              >
                {media ? (
                  <Photo
                    media={media}
                    fill
                    decorative
                    sizes="(min-width: 640px) 190px, 128px"
                    imgClassName="transition-[filter] duration-500 ease-expo group-hover:brightness-[1.06]"
                  />
                ) : (
                  <CommodityArt category={c} variant={i} className="absolute inset-0 size-full" />
                )}
                <span
                  aria-hidden="true"
                  className="absolute inset-x-0 bottom-0 h-3/4 bg-gradient-to-t from-ink/85 via-ink/60 to-transparent"
                />
                <TileText name={c} count={n} />
                {selected ? <SelectedMark /> : null}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

const tileFrame =
  "group relative block aspect-[4/5] overflow-hidden rounded-[24px] text-cream sm:aspect-[5/4] " +
  "shadow-[0_14px_30px_-18px_rgb(90_70_30/0.55),inset_0_0_0_1px_rgb(10_10_10/0.06)] " +
  "transition-[box-shadow,transform] duration-500 ease-expo hover:-translate-y-0.5 hover:shadow-[0_22px_40px_-20px_rgb(90_70_30/0.6)] " +
  "focus-visible:rounded-[24px]";

const selectedRing = "shadow-[0_0_0_2px_var(--c-ground),0_0_0_4px_var(--c-fg)] hover:shadow-[0_0_0_2px_var(--c-ground),0_0_0_4px_var(--c-fg)]";

function TileText({ name, count }: { name: string; count: number }) {
  return (
    <span className="absolute inset-x-0 bottom-0 p-3.5 [text-shadow:0_1px_10px_rgb(0_0_0/0.35)] sm:p-4">
      <span className="t-headline block truncate text-cream">{name}</span>
      <span className="t-code mt-0.5 block text-cream/75">
        {count ? `${count} ${count === 1 ? "lot" : "lots"}` : "No lots yet"}
      </span>
    </span>
  );
}

function SelectedMark() {
  return (
    <span
      aria-hidden="true"
      className="absolute right-3 top-3 grid size-7 place-items-center rounded-full bg-lime text-ink shadow-[0_6px_14px_-6px_rgb(0_0_0/0.5)]"
    >
      <Icon name="check" size={14} strokeWidth={2.2} />
    </span>
  );
}
