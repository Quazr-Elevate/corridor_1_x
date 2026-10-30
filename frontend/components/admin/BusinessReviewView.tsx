"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  adminApi,
  errorMessage,
  type VerifyDoc,
  type VerifyQueueRow,
} from "@/lib/adminApi";
import { assetUrl } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Reveal } from "@/components/motion";
import { Button, LinkButton } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { HoldButton } from "@/components/ui/Controls";
import { Icon } from "@/components/ui/Icon";
import { Sheet } from "@/components/ui/Sheet";
import { Card, EmptyState, Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { useTower } from "@/components/shell/TowerShell";
import { ClearQueue } from "./ClearQueue";
import {
  BusinessRejectSheet,
  type RejectItem,
} from "./RejectSheet";
import { fmtAgo, refId } from "./format";
import { KbdHints, QueueList, useNow, useQueueKeys, type QueueItem } from "./parts";

/**
 * Business certificate review — the single-review flow surface.
 *
 * The admin sees the business profile (7 mandatory fields) alongside the
 * uploaded business certificate. One Approve hold = business verified
 * (cascades to approving the cert doc(s)). One Reject opens the sheet,
 * admin picks the specific failures and writes a reason — reject
 * cascades to mark the picked cert slot(s) as rejected with the same
 * reason, so the trader sees "Rejected — replace it" on their slot.
 */

interface Decided {
  row: VerifyQueueRow;
  outcome: "approved" | "rejected";
  reason?: string;
  failedItems?: string[];
  at: number;
}

type View = "queue" | "decided";

const FIELD_LABELS: Record<string, string> = {
  fullName: "Full name",
  position: "Position",
  phone: "Phone",
  legalName: "Legal company name",
  industry: "Industry",
  operatingCountries: "Operating countries",
  tradePosition: "Trade position",
};

const REJECT_REASON_PICKS = [
  "Business name on the document doesn't match the legal company name.",
  "Phone number looks personal — please provide a business line.",
  "Operating countries list is empty or clearly incorrect.",
  "Trade position doesn't match the industry.",
  "Document is expired or unreadable — upload a current, clearer scan.",
] as const;

const ownerName = (r: VerifyQueueRow) => r.businessName || r.fullName || r.email;

export function BusinessReviewView() {
  const toast = useToast();
  const { refreshStats } = useTower();
  const now = useNow();

  const [rows, setRows] = useState<VerifyQueueRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [view, setView] = useState<View>("queue");
  const [decided, setDecided] = useState<Decided[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [rejectRow, setRejectRow] = useState<VerifyQueueRow | null>(null);
  const detailRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const q = await adminApi.verifyQueue();
      setRows(q);
      setErr(null);
      setSelectedId((cur) =>
        cur && q.some((r) => r.businessId === cur) ? cur : q[0]?.businessId ?? null,
      );
    } catch (e) {
      setErr(errorMessage(e, "Couldn't load the review queue."));
      setRows((r) => r ?? []);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const list = view === "queue" ? rows ?? [] : decided.map((d) => d.row);
  const selected = list.find((r) => r.businessId === selectedId) ?? null;
  const decision = view === "decided"
    ? decided.find((d) => d.row.businessId === selectedId) ?? null
    : null;

  useEffect(() => setActionErr(null), [selectedId]);

  const move = useCallback(
    (delta: 1 | -1) => {
      if (!list.length) return;
      const i = list.findIndex((r) => r.businessId === selectedId);
      const next = Math.max(0, Math.min(list.length - 1, (i < 0 ? 0 : i) + delta));
      setSelectedId(list[next].businessId);
    },
    [list, selectedId],
  );
  useQueueKeys(list.length, move, !rejectRow);

  const select = (id: string) => {
    setSelectedId(id);
    if (window.matchMedia("(max-width: 1023px)").matches) {
      window.setTimeout(
        () => detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
        50,
      );
    }
  };

  const switchView = (v: View) => {
    setView(v);
    const src = v === "queue" ? rows ?? [] : decided.map((d) => d.row);
    setSelectedId(src[0]?.businessId ?? null);
  };

  const settle = (
    row: VerifyQueueRow,
    outcome: "approved" | "rejected",
    reason?: string,
    failedItems?: string[],
  ) => {
    const cur = rows ?? [];
    const idx = cur.findIndex((r) => r.businessId === row.businessId);
    const remaining = cur.filter((r) => r.businessId !== row.businessId);
    setRows(remaining);
    setDecided((d) => [
      { row, outcome, reason, failedItems, at: Date.now() },
      ...d,
    ]);
    setSelectedId(remaining[Math.min(Math.max(idx, 0), remaining.length - 1)]?.businessId ?? null);
    void refreshStats();
  };

  const approve = async () => {
    if (!selected) return;
    const row = selected;
    setBusy(true);
    setActionErr(null);
    try {
      await adminApi.verifyUser(row.userId);
      toast(`${ownerName(row)} verified.`, "verified");
      settle(row, "approved");
    } catch (e) {
      setActionErr(errorMessage(e, "Approve failed."));
    } finally {
      setBusy(false);
    }
  };

  const openReject = () => {
    if (!selected) return;
    setRejectRow(selected);
  };

  const submitReject = async ({
    reason,
    failedItems,
  }: {
    reason: string;
    failedItems: string[];
  }) => {
    if (!rejectRow) return;
    const row = rejectRow;
    await adminApi.rejectUser(row.userId, reason, failedItems);
    toast(`${ownerName(row)} rejected.`, "frozen");
    settle(row, "rejected", reason, failedItems);
  };

  const items: QueueItem[] = list.map((r) => {
    const d = view === "decided" ? decided.find((x) => x.row.businessId === r.businessId) : undefined;
    return {
      id: r.businessId,
      code: refId("BIZ", r.businessId),
      title: ownerName(r),
      sub: [r.email, r.country].filter(Boolean).join(" · "),
      tag: d ? (
        <span className="t-foot font-semibold">
          {d.outcome === "approved" ? "Approved" : "Rejected"} · {fmtAgo(new Date(d.at).toISOString(), now)}
        </span>
      ) : undefined,
    };
  });

  const loading = rows === null;
  const clear = !loading && items.length === 0;

  return (
    <>
      <div className="mt-6 flex flex-wrap items-end justify-between gap-4">
        <p className="t-sub text-fg-3">
          Open each business, review the certificate and the 7 mandatory fields together, then hold to approve.
        </p>
        <div className="flex items-center gap-3">
          <KbdHints />
          <div className="flex items-center gap-2">
            <ViewTab active={view === "queue"} count={rows?.length ?? 0} onClick={() => switchView("queue")}>
              Queue
            </ViewTab>
            <ViewTab active={view === "decided"} count={decided.length} onClick={() => switchView("decided")}>
              Decided
            </ViewTab>
          </div>
        </div>
      </div>

      {err ? (
        <div className="mt-8">
          <Notice
            tone="frozen"
            title="Couldn't load the queue"
            action={
              <Button variant="secondary" size="sm" onClick={() => void load()}>
                Try again
              </Button>
            }
          >
            {err}
          </Notice>
        </div>
      ) : null}

      {clear && !err ? (
        <div className="mt-8 animate-rise">
          {view === "queue" ? (
            <ClearQueue
              eyebrow="Business certificate · 0"
              title="Nothing to review"
              icon="passport"
              objectPosition="30% 40%"
              actions={
                <LinkButton href="/admin/users" variant="quiet" size="sm" iconRight="arrow-right">
                  KYB directory
                </LinkButton>
              }
            >
              New submissions land here, oldest first — profile + business certificate reviewed together.
              {decided.length ? ` ${decided.length} business${decided.length === 1 ? "" : "es"} decided this session.` : null}
            </ClearQueue>
          ) : (
            <Card className="p-2">
              <EmptyState icon="stamp" title="Nothing decided yet">
                Businesses you approve or reject this session collect here.
              </EmptyState>
            </Card>
          )}
        </div>
      ) : (
        <div className="mt-8 grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)] lg:items-start">
          <div className="lg:sticky lg:top-24">
            <div className="-mx-2 px-2 pb-2 pt-1 lg:max-h-[calc(100dvh-8rem)] lg:overflow-y-auto">
              {loading ? (
                <div className="flex flex-col gap-2.5" aria-busy="true">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-[96px] rounded-[22px]" />
                  ))}
                </div>
              ) : (
                <QueueList
                  label={view === "queue" ? "Businesses awaiting review" : "Decided this session"}
                  items={items}
                  selectedId={selectedId}
                  onSelect={select}
                />
              )}
            </div>
          </div>

          <div ref={detailRef} className="scroll-mt-24">
            {loading ? (
              <Card className="rounded-[32px] p-6 sm:p-7" aria-busy="true">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="mt-4 h-9 w-2/3" />
                <div className="mt-8 grid gap-6 xl:grid-cols-2">
                  <Skeleton className="h-[320px] rounded-[22px]" />
                  <Skeleton className="h-[320px] rounded-[22px]" />
                </div>
              </Card>
            ) : selected ? (
              <BusinessDetail
                row={selected}
                decided={decision}
                busy={busy}
                actionErr={actionErr}
                onApprove={approve}
                onReject={openReject}
              />
            ) : (
              <Card className="rounded-[32px] p-10 text-center">
                <EmptyState icon="eye" title="Pick a business to review">
                  Select one from the queue on the left.
                </EmptyState>
              </Card>
            )}
          </div>
        </div>
      )}

      <BusinessRejectSheet
        open={!!rejectRow}
        onClose={() => setRejectRow(null)}
        title={rejectRow ? `Reject ${ownerName(rejectRow)}` : "Reject"}
        description="Tick everything that failed. The trader sees the list and your note."
        items={rejectRow ? buildRejectItems(rejectRow) : []}
        quickReasons={REJECT_REASON_PICKS}
        onSubmit={submitReject}
      />
    </>
  );
}

function ViewTab({
  active,
  count,
  onClick,
  children,
}: {
  active: boolean;
  count: number;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "t-callout inline-flex items-center gap-2 rounded-full px-4 py-1.5 transition-colors duration-200",
        active ? "bg-fg text-ink" : "text-fg-2 hover:text-fg",
      )}
    >
      {children}
      <span className="t-code tabular rounded-full bg-fg/10 px-2 py-0.5">{count}</span>
    </button>
  );
}

function BusinessDetail({
  row,
  decided,
  busy,
  actionErr,
  onApprove,
  onReject,
}: {
  row: VerifyQueueRow;
  decided: Decided | null;
  busy: boolean;
  actionErr: string | null;
  onApprove: () => void;
  onReject: () => void;
}) {
  // Every mandatory cert the trader has uploaded — one card each so the
  // admin can preview and judge each one, not just the first.
  const certs = (row.docs || []).filter((d) => d.requirementSlug);
  return (
    <Card className="rounded-[32px] p-6 sm:p-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="t-label text-fg-3">Business · {refId("BIZ", row.businessId)}</p>
          <h2 className="t-title2 mt-1 text-fg">{ownerName(row)}</h2>
          <p className="t-sub mt-1 text-fg-3">
            {row.email}
            {row.country ? ` · ${row.country}` : ""}
            {row.submittedAt ? ` · submitted ${fmtAgo(row.submittedAt, Date.now())}` : ""}
          </p>
        </div>
        {decided ? (
          <Chip tone={decided.outcome === "approved" ? "verified" : "frozen"}>
            {decided.outcome === "approved" ? "Approved" : "Rejected"}
          </Chip>
        ) : null}
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <section aria-label="Business certificates">
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="t-label text-fg-3">Business certificates</h3>
            <span className="t-code tabular text-fg-3">{certs.length} uploaded</span>
          </div>
          {certs.length ? (
            <div className="mt-3 space-y-3">
              {certs.map((d) => (
                <CertViewer key={d.id} doc={d} />
              ))}
            </div>
          ) : (
            <div className="relief mt-3 rounded-[22px] p-6 text-center text-fg-3">
              No certificates uploaded yet.
            </div>
          )}
        </section>

        <section aria-label="Mandatory profile fields">
          <h3 className="t-label text-fg-3">Mandatory fields</h3>
          <dl className="mt-3 space-y-2">
            {MANDATORY_KEYS.map((key) => {
              const value = fieldValue(row, key);
              const missing = row.missingFields.includes(key);
              return (
                <div
                  key={key}
                  className={cn(
                    "flex items-start justify-between gap-4 rounded-[14px] px-3 py-2.5",
                    missing ? "bg-danger-soft/40 ring-1 ring-danger/30" : "",
                  )}
                >
                  <dt className="t-sub text-fg-3">{FIELD_LABELS[key]}</dt>
                  <dd className="t-callout text-right text-fg">
                    {value || <span className="text-fg-3 italic">Not provided</span>}
                  </dd>
                </div>
              );
            })}
          </dl>
        </section>
      </div>

      {decided && decided.outcome === "rejected" ? (
        <Notice tone="frozen" className="mt-6" title="Rejected">
          <p>{decided.reason}</p>
          {decided.failedItems && decided.failedItems.length ? (
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {decided.failedItems.map((k) => (
                <li key={k}>
                  <Chip tone="frozen">{labelFor(row, k)}</Chip>
                </li>
              ))}
            </ul>
          ) : null}
        </Notice>
      ) : null}

      {!decided ? (
        <div className="mt-7 flex flex-wrap items-center justify-between gap-3 border-t border-fg/5 pt-6">
          {actionErr ? (
            <p role="alert" className="t-sub flex items-start gap-1.5 text-danger">
              <Icon name="alert" size={14} className="mt-px shrink-0" />
              {actionErr}
            </p>
          ) : <span />}
          <div className="flex items-center gap-3">
            <Button variant="danger" icon="close" onClick={onReject} disabled={busy}>
              Reject
            </Button>
            <HoldButton tone="commit" icon="shield" onCommit={onApprove} loading={busy}>
              Approve business
            </HoldButton>
          </div>
        </div>
      ) : null}
    </Card>
  );
}

const MANDATORY_KEYS = [
  "fullName",
  "position",
  "phone",
  "legalName",
  "industry",
  "operatingCountries",
  "tradePosition",
] as const;

function fieldValue(row: VerifyQueueRow, key: string): string {
  switch (key) {
    case "fullName":
      return row.fullName ?? "";
    case "position":
      return row.position ?? "";
    case "phone":
      return row.phone ?? "";
    case "legalName":
      return row.businessName ?? "";
    case "industry":
      return row.industry ?? "";
    case "operatingCountries":
      return (row.operatingCountries ?? []).join(", ");
    case "tradePosition":
      return row.tradePosition ?? "";
    default:
      return "";
  }
}

function labelFor(row: VerifyQueueRow, key: string): string {
  if (key in FIELD_LABELS) return FIELD_LABELS[key];
  if (key.startsWith("doc:")) {
    const slug = key.slice(4);
    const d = (row.docs || []).find((x) => x.requirementSlug === slug);
    return d?.requirementDisplayName ?? slug;
  }
  return key;
}

function buildRejectItems(row: VerifyQueueRow): RejectItem[] {
  const items: RejectItem[] = MANDATORY_KEYS.map((key) => ({
    key,
    label: FIELD_LABELS[key],
    hint: fieldValue(row, key) ? undefined : "not provided",
  }));
  // One checkbox per mandatory cert slot the business has uploaded —
  // keyed by the catalog slug (stable) and labelled with the admin-defined
  // display name, NOT the trader's free-text cert_type.
  for (const d of row.docs || []) {
    if (!d.requirementSlug) continue;
    items.push({
      key: `doc:${d.requirementSlug}`,
      label: d.requirementDisplayName ?? d.requirementSlug,
      hint: d.filename,
    });
  }
  return items;
}

function CertViewer({ doc }: { doc: VerifyDoc }) {
  const [open, setOpen] = useState(false);
  const isImage = (doc.mimeType || "").startsWith("image/");
  const isPdf = doc.mimeType === "application/pdf";
  const src = assetUrl(doc.url);
  return (
    <>
      <div className="relief mt-3 rounded-[22px] p-4">
        <div className="flex items-start gap-3">
          <div className="grid size-12 shrink-0 place-items-center rounded-[14px] bg-fg/5">
            <Icon name="doc-check" size={22} className="text-fg-3" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="t-headline break-words text-fg">
              {doc.requirementDisplayName ?? doc.certType}
            </p>
            <p className="t-sub mt-1 break-all text-fg-3">
              {doc.filename} · {Math.max(1, Math.round(doc.sizeBytes / 1024))} KB
            </p>
          </div>
          <Button variant="quiet" size="sm" onClick={() => setOpen(true)}>
            View
          </Button>
        </div>
      </div>
      <Sheet
        open={open}
        onClose={() => setOpen(false)}
        size="lg"
        title={doc.filename}
        description={doc.certType}
        footer={
          <LinkButton href={src} variant="quiet" iconRight="arrow-up-right" target="_blank" rel="noopener noreferrer">
            Open in new tab
          </LinkButton>
        }
      >
        <div className="flex max-h-[70vh] items-center justify-center overflow-auto rounded-[22px] bg-black/5 p-2">
          {isImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={src} alt={doc.filename} className="max-h-[66vh] w-auto rounded-[14px] object-contain" />
          ) : isPdf ? (
            <iframe src={src} title={doc.filename} className="h-[70vh] w-full rounded-[14px] bg-white" />
          ) : (
            <div className="p-6 text-center">
              <p className="t-callout text-fg">Preview isn't available for this file type.</p>
              <p className="t-sub mt-1 text-fg-3">Use "Open in new tab" to download it.</p>
            </div>
          )}
        </div>
      </Sheet>
    </>
  );
}
