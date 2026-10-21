import Link from "next/link";
import type { ReactNode } from "react";
import { Photo } from "@/components/art/Photo";
import { ApproxPrice } from "@/components/fx/FxContext";
import { Chip } from "@/components/ui/Chip";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Surface";
import { formatQty, joinDot, listingCode, packingLabel, priceFigure } from "@/components/products/format";
import { assetUrl, type ProductRead } from "@/lib/api";
import { cn } from "@/lib/cn";
import { MEDIA } from "@/lib/media";
import { lotCompleteness } from "./completeness";
import { LotThumb } from "./LotPhoto";

/**
 * Selling-lens cards, after the reference market (portal /market):
 *   • ListLotCard — the sunk "List a lot" well with a solid lime-plus disc.
 *   • ListingCard — relief card: 72px photo thumb, Live/Pending chip over a
 *     mono L-id, name, origin line, VOLUME / PRICE, the completeness bar.
 */

export function ListLotCard({ empty, className }: { empty: boolean; className?: string }) {
  return (
    <Link
      href="/dashboard/products/new"
      className={cn(
        "well group flex h-full min-h-[300px] flex-col items-center justify-center rounded-[30px] p-8 text-center",
        "transition-[background-color,box-shadow] duration-500 ease-expo hover:bg-surface hover:shadow-[var(--relief)]",
        "focus-visible:rounded-[30px]",
        className,
      )}
    >
      <span className="solid grid size-14 place-items-center rounded-full text-lime transition-transform duration-500 ease-expo motion-safe:group-hover:rotate-90">
        <Icon name="plus" size={22} />
      </span>
      <span className="t-title3 mt-5 text-fg">List a lot</span>
      <span className="t-sub mt-1.5 max-w-[240px] text-fg-3">
        {empty
          ? "Your first lot takes a minute. One sentence and a photo — enrich later."
          : "One sentence. Publish in under a minute, enrich later."}
      </span>
    </Link>
  );
}

export function ListingCard({ product: p, live }: { product: ProductRead; live: boolean }) {
  const { score, hint } = lotCompleteness(p);
  const volume = formatQty(p.quantity, p.unit);
  const price = priceFigure(p.pricePerUnit, p.unit, p.currency);
  const photo = p.photos[0] ? assetUrl(p.photos[0]) : null;
  const origin = joinDot(
    p.variety || p.category,
    p.originState ? `from ${p.originState}` : null,
    packingLabel(p.packaging),
  );

  const body: ReactNode = (
    <>
      <div className="flex items-start justify-between gap-3">
        <LotThumb src={photo} category={p.category} />
        <div className="flex flex-col items-end gap-1.5">
          {live ? (
            <Chip tone="verified" noIcon>
              Live
            </Chip>
          ) : (
            <Chip tone="move" noIcon>
              Pending
            </Chip>
          )}
          <span className="t-code text-fg-3">{listingCode(p.id)}</span>
        </div>
      </div>

      <h3 className="t-title3 mt-5 line-clamp-2 break-words text-fg">{p.name}</h3>
      <p className="t-sub mt-0.5 truncate text-fg-3">{origin}</p>

      <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-line pt-4">
        <Figure label="Volume" value={volume ?? "—"} muted={!volume} />
        <Figure
          label="Price"
          value={price}
          muted={price === "On request"}
          sub={<ApproxPrice amount={p.pricePerUnit} currency={p.currency} variant="line" />}
        />
      </dl>

      <div className="mt-4">
        <div className="flex justify-between gap-3">
          <span className="t-foot text-fg-3">Listing {score}%</span>
          <span className="t-foot text-fg-3">
            {p.photos.length} {p.photos.length === 1 ? "photo" : "photos"}
          </span>
        </div>
        <div
          role="progressbar"
          aria-label={`${p.name} — listing completeness`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={score}
          className="well mt-1.5 h-1.5 overflow-hidden rounded-full"
        >
          <div className="h-full rounded-full bg-fg" style={{ width: `${score}%` }} />
        </div>
        {score < 100 ? <p className="t-foot mt-2 text-fg-3">{hint}</p> : null}
      </div>

      <div className="mt-auto flex items-center justify-between gap-3 pt-5">
        <span className="t-foot truncate text-fg-3">
          {formatQty(p.moq, p.unit) ? `MOQ ${formatQty(p.moq, p.unit)}` : p.category}
        </span>
        {live ? (
          <span className="t-sub inline-flex shrink-0 items-center gap-1.5 font-semibold text-fg">
            View in market
            <Icon
              name="arrow-right"
              size={15}
              className="transition-transform duration-300 ease-expo group-hover:translate-x-0.5"
            />
          </span>
        ) : (
          <span className="t-sub shrink-0 text-fg-3">Live after verification</span>
        )}
      </div>
    </>
  );

  const cls = "relief flex h-full flex-col rounded-[30px] p-5";
  // Live lots open their public market page — what buyers see.
  if (live) {
    return (
      <Link
        href={`/products/${p.id}`}
        aria-label={`${p.name} — view in the market`}
        className={cn(cls, "relief-hover group focus-visible:rounded-[30px]")}
      >
        {body}
      </Link>
    );
  }
  return <article className={cls}>{body}</article>;
}

function Figure({ label, value, muted, sub }: { label: string; value: string; muted?: boolean; sub?: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="t-label text-fg-3">{label}</dt>
      <dd
        className={cn(
          "tabular mt-1 truncate text-[20px] font-medium leading-tight tracking-[-0.025em]",
          muted ? "text-fg-3" : "text-fg",
        )}
        title={value}
      >
        {value}
      </dd>
      {sub ? <dd>{sub}</dd> : null}
    </div>
  );
}

export function ListingCardSkeleton() {
  return (
    <div className="relief rounded-[30px] p-5" aria-hidden="true">
      <div className="flex items-start justify-between">
        <Skeleton className="size-[72px] rounded-[20px]" />
        <div className="flex flex-col items-end gap-2">
          <Skeleton className="h-6 w-14 rounded-full" />
          <Skeleton className="h-3 w-16 rounded-full" />
        </div>
      </div>
      <Skeleton className="mt-6 h-5 w-3/4 rounded-full" />
      <Skeleton className="mt-2 h-3 w-1/2 rounded-full" />
      <Skeleton className="mt-6 h-12 w-full rounded-[14px]" />
      <Skeleton className="mt-4 h-1.5 w-full rounded-full" />
    </div>
  );
}

/**
 * Empty selling lens: the warehouse photograph with a line, so a new
 * seller's page is not a blank well. Text sits on the reference's ink
 * gradient for contrast.
 */
export function EmptyWarehouseCard({ className }: { className?: string }) {
  return (
    <div className={cn("relative min-h-[300px] overflow-hidden rounded-[30px] text-cream", className)}>
      <Photo media={MEDIA.warehouse} fill decorative sizes="(min-width: 1280px) 760px, (min-width: 640px) 50vw, 100vw" objectPosition="60% center" />
      <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-r from-ink/75 via-ink/40 to-ink/5" />
      <div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-ink/70 to-transparent" />
      <div className="relative flex h-full min-h-[300px] flex-col justify-end p-7 sm:p-8">
        <p className="t-label text-cream/70">Nothing listed yet</p>
        <p className="t-title2 mt-2 max-w-sm text-cream">Buyers browse verified lots like these every day.</p>
        <p className="t-callout mt-2 max-w-sm text-cream/80">
          A name, a category and one photo is enough to publish. Add volume, price and a description when you have them.
        </p>
      </div>
    </div>
  );
}
