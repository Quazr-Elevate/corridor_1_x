import Link from "next/link";
import type { ReactNode } from "react";
import { ApproxPrice } from "@/components/fx/FxContext";
import { Chip } from "@/components/ui/Chip";
import { Skeleton } from "@/components/ui/Surface";
import { LotCover } from "@/components/market/LotPhoto";
import { FrostName } from "@/components/market/SellerFrost";
import type { PublicProductCard as CardData } from "@/lib/publicApi";
import { photoUrl } from "@/lib/publicApi";
import { formatQty, joinDot, listingCode, packingLabel, priceFigure } from "./format";

/**
 * Market card (buying lens) — a relief card led by the lot's photograph:
 * the seller's own photo, else the commodity's macro shot, else the drawn
 * still-life. The seller stays frosted: identity only opens through the
 * contact gate on the detail page.
 */
export function PublicProductCard({ product: p, priority }: { product: CardData; priority?: boolean }) {
  const photo = photoUrl(p.photo);
  const place = p.seller.city || p.seller.state || "India";
  const volume = formatQty(p.quantity, p.unit);
  const moq = formatQty(p.moq, p.unit);
  const price = priceFigure(p.pricePerUnit, p.unit, p.currency);

  return (
    <Link
      href={`/products/${p.id}`}
      className="relief relief-hover group flex h-full flex-col rounded-[30px] p-2.5 focus-visible:rounded-[30px]"
      aria-label={`${p.name} — ${p.category}${p.originState ? `, ${p.originState}` : ""}`}
    >
      <div className="relative aspect-[4/3] w-full overflow-hidden rounded-[22px] bg-[#e6dac2]">
        <LotCover
          src={photo}
          category={p.category}
          priority={priority}
          imgClassName="transition-[filter] duration-700 ease-expo group-hover:brightness-[1.05]"
        />
        <span aria-hidden="true" className="absolute inset-x-0 top-0 h-1/3 bg-gradient-to-b from-ink/25 to-transparent" />
        <span className="glass t-sub absolute left-3 top-3 inline-flex h-7 items-center rounded-full px-3 font-medium text-fg">
          {p.category}
        </span>
        <span className="glass t-code absolute right-3 top-3 inline-flex h-7 items-center rounded-full px-2.5 text-fg-2">
          {listingCode(p.id)}
        </span>
      </div>

      <div className="flex flex-1 flex-col px-2.5 pb-2.5 pt-4">
        <h3 className="t-title3 line-clamp-2 break-words text-fg">{p.name}</h3>
        <p className="t-sub mt-0.5 truncate text-fg-3">
          {joinDot(p.variety || p.category, p.originState && `from ${p.originState}`, packingLabel(p.packaging))}
        </p>

        <dl className="mt-4 grid grid-cols-2 gap-4 border-t border-line pt-4">
          <Figure label="Volume" value={volume ?? "—"} muted={!volume} />
          <Figure
            label="Price"
            value={price}
            muted={price === "On request"}
            sub={<ApproxPrice amount={p.pricePerUnit} currency={p.currency} variant="line" />}
          />
        </dl>

        <div className="mt-auto flex min-w-0 items-center gap-2 pt-4">
          <Chip tone="verified" size="sm">
            Verified
          </Chip>
          <FrostName width={78} />
          <span className="t-sub min-w-0 truncate text-fg-3">· {place}</span>
          {moq ? <span className="t-foot ml-auto shrink-0 text-fg-3">MOQ {moq}</span> : null}
        </div>
      </div>
    </Link>
  );
}

function Figure({ label, value, muted, sub }: { label: string; value: string; muted?: boolean; sub?: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="t-label text-fg-3">{label}</dt>
      <dd
        className={`tabular mt-1 truncate text-[20px] font-medium leading-tight tracking-[-0.025em] ${muted ? "text-fg-3" : "text-fg"}`}
        title={value}
      >
        {value}
      </dd>
      {sub ? <dd>{sub}</dd> : null}
    </div>
  );
}

/** Loading placeholder with the card's proportions. */
export function PublicProductCardSkeleton() {
  return (
    <div className="relief rounded-[30px] p-2.5" aria-hidden="true">
      <Skeleton className="aspect-[4/3] w-full rounded-[22px]" />
      <div className="space-y-2.5 px-2.5 pb-2.5 pt-4">
        <Skeleton className="h-5 w-3/4 rounded-full" />
        <Skeleton className="h-3 w-1/2 rounded-full" />
        <Skeleton className="mt-5 h-12 w-full rounded-[14px]" />
        <Skeleton className="h-5 w-2/3 rounded-full" />
      </div>
    </div>
  );
}
