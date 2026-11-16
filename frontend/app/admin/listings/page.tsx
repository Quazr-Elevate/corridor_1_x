"use client";

import { useCallback, useEffect, useState } from "react";
import {
  adminApi,
  docFileUrl,
  errorMessage,
  type AdminListingDetail,
  type AdminListingRow,
  type RevisionChange,
} from "@/lib/adminApi";
import { assetUrl, type ProductCertificate, type ProductRead, type ProductSpec } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/Button";
import { Chip, type ChipTone } from "@/components/ui/Chip";
import { HoldButton, Segmented } from "@/components/ui/Controls";
import { Icon } from "@/components/ui/Icon";
import { EmptyState, Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { RejectSheet } from "@/components/admin/RejectSheet";
import { LaneHeader } from "@/components/admin/tower";
import { fmtAgo, fmtBytes, refId } from "@/components/admin/format";
import { formatQty, priceRangeFigure, specValue } from "@/components/products/format";

const STATUS: Record<ProductRead["status"], { label: string; tone: ChipTone }> = {
  draft: { label: "Draft", tone: "quiet" },
  under_review: { label: "In review", tone: "move" },
  published: { label: "Published", tone: "verified" },
  rejected: { label: "Rejected", tone: "frozen" },
  paused: { label: "Paused", tone: "quiet" },
};

const REJECT_REASONS = [
  "A photo shows a company name, logo or contact details. Replace it.",
  "The description contains contact details. Remove them.",
  "The specifications don’t match the grade stated.",
  "The price range is not realistic for this product. Check the unit and currency.",
  "A document is unreadable or expired. Upload a current copy.",
] as const;

const FIELD_LABEL: Record<string, string> = {
  name: "Product name", category: "Category", variety: "Variety", description: "Description", grade: "Grade",
  hsCode: "HS code", originCountry: "Country of origin", originState: "State of origin", packaging: "Packaging",
  unit: "Unit", capacityPerMonth: "Monthly capacity", capacityUnit: "Capacity unit", leadTimeDays: "Lead time (days)",
  incoterms: "Incoterms", portOfLoading: "Port of loading", photos: "Photos", specs: "Specifications",
};

type Queue = "pending" | "all";

/**
 * Listing review. The queue holds new submissions and edits to published
 * listings. Approving publishes (or applies the edits); rejecting needs a
 * reason the seller will read.
 */
export default function ListingReviewPage() {
  const toast = useToast();
  const [queue, setQueue] = useState<Queue>("pending");
  const [rows, setRows] = useState<AdminListingRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AdminListingDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [rejecting, setRejecting] = useState(false);

  const load = useCallback(async (which: Queue) => {
    setError(null);
    try {
      const res = await adminApi.listings({ queue: which });
      setRows(res.items);
      setSelectedId((cur) => (cur && res.items.some((r) => r.id === cur) ? cur : res.items[0]?.id ?? null));
    } catch (e) {
      setError(errorMessage(e, "Couldn’t load the listings."));
    }
  }, []);

  useEffect(() => {
    setRows(null);
    void load(queue);
  }, [queue, load]);

  const loadDetail = useCallback(async (id: string) => {
    setDetailError(null);
    try {
      setDetail(await adminApi.listing(id));
    } catch (e) {
      setDetailError(errorMessage(e, "Couldn’t load this listing."));
    }
  }, []);

  useEffect(() => {
    setDetail(null);
    if (selectedId) void loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  const decide = async (call: () => Promise<unknown>, message: string) => {
    setBusy(true);
    try {
      await call();
      toast(message, "verified");
      await load(queue);
      if (selectedId) await loadDetail(selectedId);
    } finally {
      setBusy(false);
    }
  };

  const approve = async () => {
    if (!detail) return;
    try {
      await decide(
        () => adminApi.approveListing(detail.listing.id),
        detail.reviewKind === "revision" ? "Changes approved" : "Listing published",
      );
    } catch (e) {
      toast(errorMessage(e, "Approve failed."));
    }
  };

  const waiting = detail?.reviewKind !== null && detail?.reviewKind !== undefined;

  return (
    <div>
      <LaneHeader
        eyebrow="Listings"
        title="Listing review"
        subtitle="Nothing reaches the market until a reviewer approves it. Check photos and text for anything that names the seller."
        actions={
          <Segmented
            label="Which listings"
            size="sm"
            value={queue}
            onChange={setQueue}
            options={[
              { value: "pending", label: "Waiting" },
              { value: "all", label: "All" },
            ]}
          />
        }
      />

      {error ? (
        <Notice tone="frozen" title="Couldn’t load" className="mt-8" action={<Button size="sm" variant="secondary" onClick={() => void load(queue)}>Try again</Button>}>
          {error}
        </Notice>
      ) : null}

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,8fr)] lg:items-start">
        <section aria-label="Queue" className="relief rounded-[26px] p-2">
          {!rows ? (
            <div className="space-y-2 p-2">
              {[0, 1, 2].map((k) => (
                <Skeleton key={k} className="h-16 w-full rounded-[18px]" />
              ))}
            </div>
          ) : rows.length === 0 ? (
            <EmptyState icon="doc-check" title={queue === "pending" ? "Nothing waiting" : "No listings yet"} className="py-12">
              {queue === "pending" ? "New submissions and edits to published listings appear here." : null}
            </EmptyState>
          ) : (
            <ul>
              {rows.map((r) => (
                <li key={r.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(r.id)}
                    aria-current={r.id === selectedId || undefined}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-[18px] px-3 py-3 text-left transition-colors",
                      r.id === selectedId ? "well" : "hover:bg-[rgb(10_10_10/0.04)]",
                    )}
                  >
                    {r.photo ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={assetUrl(r.photo)} alt="" className="size-12 shrink-0 rounded-[12px] object-cover" />
                    ) : (
                      <span className="well grid size-12 shrink-0 place-items-center rounded-[12px] text-fg-3">
                        <Icon name="image" size={18} />
                      </span>
                    )}
                    <span className="min-w-0 flex-1">
                      <span className="t-body block truncate font-medium text-fg">{r.name}</span>
                      <span className="t-sub block truncate text-fg-3">
                        {r.seller.legalName ?? "Unnamed business"} · {r.category}
                      </span>
                    </span>
                    <span className="flex shrink-0 flex-col items-end gap-1">
                      <Chip tone={r.reviewKind ? "move" : STATUS[r.status].tone} size="sm" noIcon>
                        {r.reviewKind === "revision" ? "Edit" : r.reviewKind === "new" ? "New" : STATUS[r.status].label}
                      </Chip>
                      {r.waitingSince ? <span className="t-foot text-fg-3">{fmtAgo(r.waitingSince)}</span> : null}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-label="Listing" className="relief min-w-0 rounded-[32px] p-5 sm:p-7">
          {detailError ? (
            <Notice tone="frozen" title="Couldn’t load this listing">
              {detailError}
            </Notice>
          ) : !selectedId ? (
            <EmptyState icon="sack" title="Pick a listing" className="py-16">
              Choose one from the queue to review it.
            </EmptyState>
          ) : !detail ? (
            <div className="space-y-4">
              <Skeleton className="h-8 w-2/3 rounded-full" />
              <Skeleton className="h-40 w-full rounded-[20px]" />
              <Skeleton className="h-40 w-full rounded-[20px]" />
            </div>
          ) : (
            <ListingDetail
              detail={detail}
              busy={busy}
              onCertificate={(cert, visibility) =>
                decide(
                  () => adminApi.setCertificateVisibility(detail.listing.id, cert.id, visibility),
                  visibility === "downloadable" ? "Buyers can now download it" : "Document set to internal",
                ).catch((e) => toast(errorMessage(e, "Couldn’t change the document.")))
              }
              footer={
                waiting ? (
                  <div className="mt-8 flex flex-wrap items-center justify-end gap-3 border-t border-line pt-6">
                    <Button variant="danger" onClick={() => setRejecting(true)} disabled={busy}>
                      Reject…
                    </Button>
                    <HoldButton tone="commit" onCommit={approve} loading={busy}>
                      {detail.reviewKind === "revision" ? "Approve changes" : "Approve and publish"}
                    </HoldButton>
                  </div>
                ) : detail.listing.status === "published" || detail.listing.status === "paused" ? (
                  <div className="mt-8 flex justify-end border-t border-line pt-6">
                    <Button variant="danger" onClick={() => setRejecting(true)} disabled={busy}>
                      Take down…
                    </Button>
                  </div>
                ) : null
              }
            />
          )}
        </section>
      </div>

      <RejectSheet
        open={rejecting}
        onClose={() => setRejecting(false)}
        title={
          detail?.reviewKind === "revision"
            ? "Reject these changes"
            : detail?.reviewKind === "new"
              ? "Reject this listing"
              : "Take this listing down"
        }
        description={
          detail?.reviewKind === "revision"
            ? "The published version stays in the market. The seller sees your reason."
            : "The seller sees your reason and can fix the listing and submit it again."
        }
        quickReasons={REJECT_REASONS}
        submitLabel={detail?.reviewKind ? "Reject" : "Take down"}
        onSubmit={async (reason) => {
          if (!detail) return;
          await decide(() => adminApi.rejectListing(detail.listing.id, reason), "Seller notified in their listing");
        }}
      />
    </div>
  );
}

function ListingDetail({
  detail,
  busy,
  onCertificate,
  footer,
}: {
  detail: AdminListingDetail;
  busy: boolean;
  onCertificate: (cert: ProductCertificate, visibility: "internal" | "downloadable") => void;
  footer: React.ReactNode;
}) {
  const p = detail.listing;
  const rows: Array<[string, string | null]> = [
    ["Category", p.category],
    ["Grade", p.grade],
    ["Variety", p.variety],
    ["HS code", p.hsCode],
    ["Origin", [p.originState, p.originCountry].filter(Boolean).join(", ") || null],
    ["Packaging", p.packaging],
    ["Volume", formatQty(p.quantity, p.unit)],
    ["Minimum order", formatQty(p.moq, p.unit)],
    ["Monthly capacity", formatQty(p.capacityPerMonth, p.capacityUnit || p.unit)],
    ["Lead time", p.leadTimeDays === null ? null : `${p.leadTimeDays} days`],
    ["Price range", p.priceMin ? priceRangeFigure(p.priceMin, p.priceMax, p.unit, p.currency) : null],
    ["Price valid until", p.priceValidUntil],
    ["Incoterms", p.incoterms.join(" · ") || null],
    ["Port of loading", p.portOfLoading],
  ];
  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="t-code text-fg-3">{refId("LST", p.id)}</p>
          <h2 className="t-title2 mt-1 break-words text-fg">{p.name}</h2>
          <p className="t-sub mt-1 text-fg-3">
            {detail.seller.companyCode ? <span className="t-code mr-2">{detail.seller.companyCode}</span> : null}
            {detail.seller.legalName ?? "Unnamed business"}
            {detail.seller.state ? ` · ${detail.seller.state}` : ""}
            {detail.seller.verified ? "" : " · business not verified"}
          </p>
        </div>
        <Chip tone={STATUS[p.status].tone} noIcon>
          {STATUS[p.status].label}
        </Chip>
      </div>

      {detail.leakFlags.length ? (
        <Notice tone="move" title="Check this text before approving" className="mt-6">
          <ul className="space-y-1">
            {detail.leakFlags.map((f) => (
              <li key={f.field}>
                <span className="t-code">{f.field}</span>: {f.reasons.join(", ")}
              </li>
            ))}
          </ul>
        </Notice>
      ) : null}

      {detail.reviewKind === "revision" ? (
        <div className="mt-6">
          <p className="t-label text-fg-3">Proposed changes</p>
          <ul className="mt-3 space-y-3">
            {detail.changes.map((c) => (
              <ChangeRow key={c.field} change={c} />
            ))}
          </ul>
          <p className="t-sub mt-3 text-fg-3">Everything below is the published version buyers see now.</p>
        </div>
      ) : null}

      {p.rejectionReason ? (
        <Notice tone="frozen" title="Last rejection" className="mt-6">
          {p.rejectionReason}
        </Notice>
      ) : null}

      {p.photos.length ? (
        <ul className="mt-6 grid grid-cols-3 gap-3 sm:grid-cols-5">
          {p.photos.map((rel) => (
            <li key={rel}>
              <a href={assetUrl(rel)} target="_blank" rel="noopener noreferrer">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={assetUrl(rel)} alt="Listing photo" className="aspect-square w-full rounded-[14px] object-cover" />
              </a>
            </li>
          ))}
        </ul>
      ) : (
        <p className="t-sub mt-6 text-fg-3">No photos.</p>
      )}

      <dl className="mt-6 grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-baseline justify-between gap-4 border-b border-line pb-2">
            <dt className="t-sub text-fg-3">{label}</dt>
            <dd className={cn("t-body text-right", value ? "text-fg" : "text-fg-3")}>{value ?? "Not filled"}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-6">
        <p className="t-label text-fg-3">Description</p>
        <p className="t-body mt-2 whitespace-pre-line break-words text-fg-2">{p.description ?? "None."}</p>
      </div>

      <div className="mt-6">
        <p className="t-label text-fg-3">Specifications</p>
        <SpecList specs={p.specs} />
      </div>

      <div className="mt-6">
        <p className="t-label text-fg-3">Documents</p>
        {p.certificates.length === 0 ? (
          <p className="t-sub mt-2 text-fg-3">None uploaded.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {p.certificates.map((c) => (
              <li key={c.id} className="relief-sm flex flex-wrap items-center gap-3 rounded-[16px] px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="t-body truncate text-fg">{c.name}</p>
                  <a
                    href={docFileUrl(c.url)}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Opening the file is logged"
                    className="t-sub block truncate text-fg-3 underline underline-offset-4"
                  >
                    {c.filename} · {fmtBytes(c.sizeBytes)}
                  </a>
                </div>
                <Segmented
                  label={`Who can see ${c.name}`}
                  size="sm"
                  value={c.visibility}
                  onChange={(v) => !busy && onCertificate(c, v)}
                  options={[
                    { value: "internal", label: "Internal" },
                    { value: "downloadable", label: "Buyers can download" },
                  ]}
                />
              </li>
            ))}
          </ul>
        )}
        <p className="t-sub mt-3 text-fg-3">
          A downloadable document is shown to verified buyers by its type, without the filename. Check it doesn’t name
          the seller before you allow it.
        </p>
      </div>

      {footer}
    </div>
  );
}

function SpecList({ specs }: { specs: ProductSpec[] }) {
  if (!specs.length) return <p className="t-sub mt-2 text-fg-3">None stated.</p>;
  return (
    <dl className="mt-2 divide-y divide-line">
      {specs.map((s) => (
        <div key={s.parameterId} className="flex items-baseline justify-between gap-4 py-2">
          <dt className="t-body text-fg-2">
            {s.name}
            {s.testMethod ? <span className="t-foot ml-2 text-fg-3">{s.testMethod}</span> : null}
          </dt>
          <dd className="t-code tabular text-fg">{specValue(s.value, s.unit, s.operator)}</dd>
        </div>
      ))}
    </dl>
  );
}

function show(value: unknown): React.ReactNode {
  if (value === null || value === undefined || value === "") return <span className="text-fg-3">Empty</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-fg-3">None</span>;
    if (typeof value[0] === "object") {
      return (value as ProductSpec[]).map((s) => `${s.name} ${specValue(s.value, s.unit, s.operator)}`).join(" · ");
    }
    return (value as string[]).every((v) => v.startsWith("/uploads/"))
      ? `${value.length} ${value.length === 1 ? "photo" : "photos"}`
      : (value as string[]).join(" · ");
  }
  return String(value);
}

function ChangeRow({ change: c }: { change: RevisionChange }) {
  const photos = c.field === "photos" && Array.isArray(c.proposed) ? (c.proposed as string[]) : null;
  return (
    <li className="well rounded-[16px] p-4">
      <p className="t-label text-fg-3">{FIELD_LABEL[c.field] ?? c.field}</p>
      <div className="mt-2 grid gap-3 sm:grid-cols-2">
        <div className="min-w-0">
          <p className="t-foot text-fg-3">Published</p>
          <p className="t-body mt-0.5 break-words text-fg-2">{show(c.current)}</p>
        </div>
        <div className="min-w-0">
          <p className="t-foot text-amber">Proposed</p>
          <p className="t-body mt-0.5 break-words text-fg">{show(c.proposed)}</p>
          {photos ? (
            <ul className="mt-2 flex flex-wrap gap-2">
              {photos.map((rel) => (
                <li key={rel}>
                  <a href={assetUrl(rel)} target="_blank" rel="noopener noreferrer">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={assetUrl(rel)} alt="Proposed photo" className="size-16 rounded-[10px] object-cover" />
                  </a>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </li>
  );
}
