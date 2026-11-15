"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { Photo } from "@/components/art/Photo";
import { ApproxPrice } from "@/components/fx/FxContext";
import { Chip } from "@/components/ui/Chip";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Surface";
import { formatQty, joinDot, listingCode, packingLabel, priceRangeFigure } from "@/components/products/format";
import { api, assetUrl, type ProductRead } from "@/lib/api";
import { cn } from "@/lib/cn";
import { MEDIA } from "@/lib/media";
import { LotThumb } from "./LotPhoto";

/**
 * Selling-lens cards, after the reference market (portal /market):
 *   • ListLotCard — the sunk "List a lot" well with a solid lime-plus disc.
 *   • ListingCard — relief card: 72px photo thumb, the review status chip
 *     over a mono L-id, name, origin line, VOLUME / PRICE, what to do next,
 *     and the actions the status allows (edit, pause, withdraw, delete).
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
          ? "Start with a name and a category. Save the draft and finish it when you’re ready."
          : "Start a draft. A reviewer checks it before it reaches the market."}
      </span>
    </Link>
  );
}

const STATUS: Record<ProductRead["status"], { label: string; tone: "verified" | "move" | "frozen" | "quiet" }> = {
  draft: { label: "Draft", tone: "quiet" },
  under_review: { label: "In review", tone: "move" },
  published: { label: "Live", tone: "verified" },
  rejected: { label: "Needs changes", tone: "frozen" },
  paused: { label: "Paused", tone: "quiet" },
};

/** What the seller should know or do next, in one line. */
function nextStep(p: ProductRead, businessVerified: boolean): string {
  if (p.status === "rejected") return p.rejectionReason ?? "The reviewer asked for changes.";
  if (p.status === "under_review") return "A reviewer is checking it.";
  if (p.status === "paused") return "Hidden from the market until you resume it.";
  if (p.status === "published") {
    if (p.pendingRevision) return "Your changes are waiting for review.";
    if (p.revisionRejectionReason) return `Changes not accepted: ${p.revisionRejectionReason}`;
    return businessVerified ? "In the market." : "Hidden while your company is not verified.";
  }
  if (p.missing.length) return `Add ${p.missing[0]}${p.missing.length > 1 ? ` and ${p.missing.length - 1} more` : ""} to submit.`;
  return businessVerified ? "Ready to submit for review." : "Ready. Submit once your company is verified.";
}

export function ListingCard({
  product: p,
  live: businessVerified,
  onChanged,
}: {
  product: ProductRead;
  /** The seller's company is verified. */
  live: boolean;
  /** Called with the updated listing, or null when it was deleted. */
  onChanged?: (id: string, next: ProductRead | null) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const volume = formatQty(p.quantity, p.unit);
  const price = priceRangeFigure(p.priceMin, p.priceMax, p.unit, p.currency);
  const photo = p.photos[0] ? assetUrl(p.photos[0]) : null;
  const origin = joinDot(
    p.grade || p.variety || p.category,
    p.originState ? `from ${p.originState}` : null,
    packingLabel(p.packaging),
  );
  const status = STATUS[p.status];
  const inMarket = p.status === "published" && businessVerified;

  const run = async (call: () => Promise<ProductRead | void>) => {
    setBusy(true);
    setError(null);
    try {
      const next = await call();
      onChanged?.(p.id, next ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn’t work. Try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className="relief flex h-full flex-col rounded-[30px] p-5" aria-busy={busy || undefined}>
      <div className="flex items-start justify-between gap-3">
        <LotThumb src={photo} category={p.category} />
        <div className="flex flex-col items-end gap-1.5">
          <Chip tone={status.tone} noIcon>
            {status.label}
          </Chip>
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
          sub={<ApproxPrice amount={p.priceMin} currency={p.currency} variant="line" />}
        />
      </dl>

      <p
        className={cn("t-sub mt-4 line-clamp-3", p.status === "rejected" || error ? "text-danger" : "text-fg-2")}
        role={error ? "alert" : undefined}
      >
        {error ?? nextStep(p, businessVerified)}
      </p>

      <div className="mt-auto flex flex-wrap items-center gap-2 pt-5">
        <Link
          href={`/dashboard/products/${p.id}`}
          className="relief-sm t-sub inline-flex h-9 items-center gap-1.5 rounded-full px-3.5 font-semibold text-fg hover:shadow-[var(--relief)]"
        >
          <Icon name="pen" size={14} />
          {p.status === "under_review" ? "Open" : "Edit"}
        </Link>
        {p.status === "published" ? (
          <CardAction disabled={busy} onClick={() => run(() => api.pauseProduct(p.id))}>
            Pause
          </CardAction>
        ) : p.status === "paused" ? (
          <CardAction disabled={busy} onClick={() => run(() => api.resumeProduct(p.id))}>
            Resume
          </CardAction>
        ) : p.status === "under_review" ? (
          <CardAction disabled={busy} onClick={() => run(() => api.withdrawProduct(p.id))}>
            Withdraw
          </CardAction>
        ) : null}
        {inMarket ? (
          <Link href={`/products/${p.id}`} className="t-sub inline-flex h-9 items-center gap-1 px-2 text-fg-2 hover:text-fg">
            View
            <Icon name="external" size={13} />
          </Link>
        ) : null}
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            if (window.confirm(`Delete “${p.name}”? This can’t be undone.`)) void run(() => api.deleteProduct(p.id));
          }}
          aria-label={`Delete ${p.name}`}
          title="Delete"
          className="ml-auto grid size-9 place-items-center rounded-full text-fg-3 transition-colors hover:bg-danger-soft hover:text-danger disabled:opacity-40"
        >
          <Icon name="trash" size={15} />
        </button>
      </div>
    </article>
  );
}

function CardAction({ children, onClick, disabled }: { children: ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="t-sub inline-flex h-9 items-center rounded-full px-3 font-medium text-fg-2 transition-colors hover:bg-[rgb(10_10_10/0.05)] hover:text-fg disabled:opacity-40"
    >
      {children}
    </button>
  );
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
          Start a draft with a name and a category. Add the price range, specifications and a photo, then submit it for review.
        </p>
      </div>
    </div>
  );
}
