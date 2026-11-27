"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  adminApi,
  errorMessage,
  type UserDetail,
  type VerifyDoc,
  type VerifyQueueRow,
} from "@/lib/adminApi";
import { entityTypeLabel } from "@/lib/api";
import { cn } from "@/lib/cn";
import { MANDATORY_FIELDS, fieldByKey, isDocumentKey } from "@/lib/verification";
import { useTower } from "@/components/shell/TowerShell";
import { Reveal } from "@/components/motion";
import { Button, LinkButton } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { HoldButton, Segmented } from "@/components/ui/Controls";
import { Icon } from "@/components/ui/Icon";
import { Card, EmptyState, Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import {
  DOC_REJECT_REASONS,
  RejectSheet,
  USER_REJECT_REASONS,
  businessRejectItems,
  type RejectItem,
} from "@/components/admin/RejectSheet";
import { AccessScope, useAccessReason } from "@/components/admin/AccessReason";
import { ClearQueue } from "@/components/admin/ClearQueue";
import { LaneHeader } from "@/components/admin/tower";
import {
  DocPaper,
  KbdHints,
  Paper,
  PaperRow,
  PaperRows,
  QueueList,
  useNow,
  useQueueKeys,
  type QueueItem,
  TwinFlags,
  useUnopenedDocs,
} from "@/components/admin/parts";
import {
  displayValue,
  dueState,
  fmtAgo,
  fmtDateTime,
  plural,
  refId,
  tradeLabel,
} from "@/components/admin/format";

type View = "queue" | "decided";
type Outcome = "approved" | "rejected";

interface Decided {
  row: VerifyQueueRow;
  outcome: Outcome;
  reason?: string;
  at: number;
}

function companyName(row: VerifyQueueRow, detail?: UserDetail | null) {
  const legal = detail?.businessProfile?.legalName;
  return row.businessName || (typeof legal === "string" && legal) || row.fullName || row.email;
}

function rowSub(row: VerifyQueueRow) {
  const base = [tradeLabel(row.tradePosition), row.country].filter(Boolean).join(" · ") || row.email;
  return row.reviewKind === "documents" ? `New documents · ${base}` : base;
}

/** What the admin can tick when rejecting a business. */
function rejectItems(row: VerifyQueueRow, detail?: UserDetail | null): RejectItem[] {
  return businessRejectItems(detail?.docs ?? row.docs, detail?.missingMandatoryFields ?? row.missingFields);
}

export default function KybReviewsPage() {
  const { refreshStats } = useTower();
  const toast = useToast();
  const now = useNow();

  const [rows, setRows] = useState<VerifyQueueRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [view, setView] = useState<View>("queue");
  const [decided, setDecided] = useState<Decided[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, UserDetail | "error">>({});
  const [tab, setTab] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [rejectRow, setRejectRow] = useState<VerifyQueueRow | null>(null);
  const [rejectDoc, setRejectDoc] = useState<{ row: VerifyQueueRow; doc: VerifyDoc } | null>(null);
  const detailRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const q = await adminApi.verifyQueue();
      setRows(q);
      setErr(null);
      setSelectedId((cur) => (cur && q.some((r) => r.userId === cur) ? cur : q[0]?.userId ?? null));
    } catch (e) {
      setErr(errorMessage(e, "Couldn't load the queue."));
      setRows((r) => r ?? []);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // The list the left pane shows.
  const list: VerifyQueueRow[] = useMemo(
    () => (view === "queue" ? rows ?? [] : decided.map((d) => d.row)),
    [view, rows, decided],
  );

  const selected = list.find((r) => r.userId === selectedId) ?? null;
  const decision = view === "decided" ? decided.find((d) => d.row.userId === selectedId) ?? null : null;
  const detail = selectedId ? details[selectedId] : undefined;

  // Pull the full account for the selected company (contact, business, docs).
  // Opening an account needs a reason; one given for the queue covers each
  // account opened from it, and that company's files.
  const access = useAccessReason("kyb-queue");
  useEffect(() => {
    if (!selectedId || details[selectedId]) return;
    let cancelled = false;
    access
      .ask()
      .then((reason) =>
        adminApi.user(selectedId, reason).then((u) => {
          access.remember(u.businessId, reason);
          return u;
        }),
      )
      .then((u) => !cancelled && setDetails((d) => ({ ...d, [selectedId]: u })))
      .catch(() => !cancelled && setDetails((d) => ({ ...d, [selectedId]: "error" })));
    return () => {
      cancelled = true;
    };
  }, [selectedId, details, access]);

  useEffect(() => setActionErr(null), [selectedId]);
  // The picked document belongs to one company.
  useEffect(() => setTab(""), [selectedId]);

  const move = useCallback(
    (delta: 1 | -1) => {
      if (!list.length) return;
      const i = list.findIndex((r) => r.userId === selectedId);
      const next = Math.max(0, Math.min(list.length - 1, (i < 0 ? 0 : i) + delta));
      setSelectedId(list[next].userId);
    },
    [list, selectedId],
  );
  useQueueKeys(list.length, move, !rejectRow);

  const select = (id: string) => {
    setSelectedId(id);
    if (window.matchMedia("(max-width: 1023px)").matches) {
      window.setTimeout(() => detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    }
  };

  const switchView = (v: View) => {
    setView(v);
    const src = v === "queue" ? rows ?? [] : decided.map((d) => d.row);
    setSelectedId(src[0]?.userId ?? null);
  };

  /** Remove from the queue, remember the decision, advance to the next. */
  const settle = (row: VerifyQueueRow, outcome: Outcome, reason?: string) => {
    const cur = rows ?? [];
    const idx = cur.findIndex((r) => r.userId === row.userId);
    const remaining = cur.filter((r) => r.userId !== row.userId);
    setRows(remaining);
    setDecided((d) => [{ row, outcome, reason, at: Date.now() }, ...d]);
    setDetails((d) => {
      const { [row.userId]: _drop, ...rest } = d;
      void _drop;
      return rest;
    });
    setSelectedId(remaining[Math.min(Math.max(idx, 0), remaining.length - 1)]?.userId ?? null);
    void refreshStats();
  };

  const approve = async () => {
    if (!selected) return;
    const row = selected;
    setBusy(true);
    setActionErr(null);
    try {
      await adminApi.verifyUser(row.userId);
      toast(`${companyName(row, typeof detail === "object" ? detail : null)} verified`, "verified");
      settle(row, "approved");
    } catch (e) {
      const msg = errorMessage(e, "Approve failed.");
      setActionErr(msg);
      toast(msg, "frozen");
    } finally {
      setBusy(false);
    }
  };

  const reject = async (reason: string, failedItems: string[]) => {
    if (!rejectRow) return;
    const row = rejectRow;
    const rowDetail = details[row.userId];
    await adminApi.rejectUser(row.userId, reason, failedItems);
    toast(`${companyName(row, typeof rowDetail === "object" ? rowDetail : null)} rejected`);
    settle(row, "rejected", reason);
  };

  /** A single document decided: update it in place; a verified business's
   *  "new documents" row leaves the queue once nothing is pending. */
  const decideDoc = (row: VerifyQueueRow, doc: VerifyDoc, status: "approved" | "rejected", reason?: string) => {
    const patch = (d: VerifyDoc): VerifyDoc =>
      d.id === doc.id ? { ...d, status, rejectionReason: reason ?? null, reviewedAt: new Date().toISOString() } : d;
    const nextRow = { ...row, docs: row.docs.map(patch) };
    setRows((rs) => (rs ?? []).map((r) => (r.userId === row.userId ? nextRow : r)));
    setDetails((ds) => {
      const cur = ds[row.userId];
      return typeof cur === "object" ? { ...ds, [row.userId]: { ...cur, docs: cur.docs.map(patch) } } : ds;
    });
    if (row.reviewKind === "documents" && !nextRow.docs.some((d) => d.status === "pending")) {
      settle(nextRow, status, reason);
    } else {
      void refreshStats();
    }
  };

  const approveDoc = async (row: VerifyQueueRow, doc: VerifyDoc) => {
    setBusy(true);
    setActionErr(null);
    try {
      await adminApi.approveDoc(doc.id);
      toast(`${doc.certType} approved`, "verified");
      decideDoc(row, doc, "approved");
    } catch (e) {
      const msg = errorMessage(e, "Approve failed.");
      setActionErr(msg);
      toast(msg, "frozen");
    } finally {
      setBusy(false);
    }
  };

  const rejectOneDoc = async (reason: string) => {
    if (!rejectDoc) return;
    const { row, doc } = rejectDoc;
    await adminApi.rejectDoc(doc.id, reason);
    toast(`${doc.certType} rejected`);
    decideDoc(row, doc, "rejected", reason);
  };

  const items: QueueItem[] = list.map((r) => {
    const d = decided.find((x) => x.row.userId === r.userId);
    return {
      id: r.userId,
      code: refId("KYB", r.userId),
      title: companyName(r, typeof details[r.userId] === "object" ? (details[r.userId] as UserDetail) : null),
      sub: rowSub(r),
      due: view === "queue" ? dueState(r.submittedAt ?? r.createdAt, now) : undefined,
      tag:
        view === "decided" && d ? (
          <span className="t-foot font-semibold">
            {d.outcome === "approved" ? "Approved" : "Rejected"} · {fmtAgo(new Date(d.at).toISOString(), now)}
          </span>
        ) : undefined,
    };
  });

  const closeReject = useCallback(() => setRejectRow(null), []);
  const loading = rows === null;
  const queueCount = rows?.length ?? 0;
  const overdue = (rows ?? []).filter((r) => dueState(r.submittedAt ?? r.createdAt, now).over).length;
  const clear = !loading && items.length === 0;

  return (
    <div className="pt-4">
      <LaneHeader
        eyebrow="Lane · Verification"
        title="Business reviews"
        subtitle={
          <>
            Check the business profile, approve or reject each document, then verify the company. Rejecting lets you
            flag exactly what to fix. Target: 24 hours.
            {overdue ? <span className="font-medium text-danger"> {plural(overdue, "company", "companies")} past it.</span> : null}
          </>
        }
        actions={
          <>
            <KbdHints />
            <Segmented<View>
              label="Queue view"
              value={view}
              onChange={switchView}
              options={[
                { value: "queue", label: "Queue", count: queueCount },
                { value: "decided", label: "Decided", count: decided.length },
              ]}
            />
          </>
        }
      />

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
              eyebrow="Queue · 0"
              title="Queue is clear"
              actions={
                <>
                  <LinkButton href="/admin/kyb-types" variant="secondary" size="sm" icon="settings">
                    Doc types
                  </LinkButton>
                  <LinkButton href="/admin/users?status=active" variant="quiet" size="sm" iconRight="arrow-right">
                    Active accounts
                  </LinkButton>
                </>
              }
            >
              New submissions land here, oldest first. Every company gets a decision within 24 hours of sending its
              profile.
              {decided.length ? ` ${plural(decided.length, "decision")} made this session.` : null}
            </ClearQueue>
          ) : (
            <Card className="p-2">
              <EmptyState icon="stamp" title="Nothing decided yet">
                Approvals and rejections from this session collect here.
              </EmptyState>
            </Card>
          )}
        </div>
      ) : (
        <div className="mt-8 grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)] lg:items-start">
          {/* ── Queue ── */}
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
                  label={view === "queue" ? "Companies awaiting review" : "Decided this session"}
                  items={items}
                  selectedId={selectedId}
                  onSelect={select}
                />
              )}
            </div>
          </div>

          {/* ── Detail ── */}
          <div ref={detailRef} className="scroll-mt-24">
            {loading ? (
              <Card className="rounded-[32px] p-6 sm:p-7" aria-busy="true">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="mt-4 h-9 w-2/3" />
                <Skeleton className="mt-3 h-4 w-1/2" />
                <div className="mt-8 grid gap-6 xl:grid-cols-2">
                  <Skeleton className="h-[320px] rounded-[22px]" />
                  <div className="space-y-2.5">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Skeleton key={i} className="h-14 rounded-[18px]" />
                    ))}
                  </div>
                </div>
              </Card>
            ) : selected ? (
              <DetailPanel
                key={selected.userId}
                row={selected}
                detail={detail}
                tab={tab}
                onTab={setTab}
                now={now}
                decision={decision}
                busy={busy}
                actionErr={actionErr}
                onApprove={approve}
                onReject={() => setRejectRow(selected)}
                onApproveDoc={(doc) => approveDoc(selected, doc)}
                onRejectDoc={(doc) => setRejectDoc({ row: selected, doc })}
              />
            ) : null}
          </div>
        </div>
      )}

      <RejectSheet
        open={rejectRow !== null}
        onClose={closeReject}
        title={rejectRow ? `Reject ${companyName(rejectRow)}?` : "Reject"}
        description="Tick what failed. They'll see your reason and a “To fix” list, and can resubmit."
        quickReasons={USER_REJECT_REASONS}
        submitLabel="Reject"
        items={rejectRow ? rejectItems(rejectRow, typeof details[rejectRow.userId] === "object" ? (details[rejectRow.userId] as UserDetail) : null) : []}
        onSubmit={reject}
      />
      <RejectSheet
        open={rejectDoc !== null}
        onClose={() => setRejectDoc(null)}
        title={rejectDoc ? `Reject ${rejectDoc.doc.certType}?` : "Reject document"}
        description="Only this document goes back to them with your reason."
        quickReasons={DOC_REJECT_REASONS}
        submitLabel="Reject document"
        onSubmit={rejectOneDoc}
      />
    </div>
  );
}

/* ───────────────────────────── Detail panel ───────────────────────── */

const DOC_STATUS: Record<VerifyDoc["status"], { label: string; tone: "verified" | "frozen" | "move" }> = {
  approved: { label: "Approved", tone: "verified" },
  rejected: { label: "Rejected", tone: "frozen" },
  pending: { label: "To review", tone: "move" },
};

/**
 * One company's review, top to bottom: the business profile as they gave it
 * at onboarding (company, address, the person who signs in), then every
 * document in a list with its own approve / reject, then the company
 * decision, which opens only once each document has been decided.
 */
function DetailPanel({
  row,
  detail,
  tab,
  onTab,
  now,
  decision,
  busy,
  actionErr,
  onApprove,
  onReject,
  onApproveDoc,
  onRejectDoc,
}: {
  row: VerifyQueueRow;
  detail: UserDetail | "error" | undefined;
  tab: string;
  onTab: (t: string) => void;
  now: number;
  decision: Decided | null;
  busy: boolean;
  actionErr: string | null;
  onApprove: () => void | Promise<void>;
  onReject: () => void;
  onApproveDoc: (doc: VerifyDoc) => void | Promise<void>;
  onRejectDoc: (doc: VerifyDoc) => void;
}) {
  const docsOnly = row.reviewKind === "documents";
  const d = typeof detail === "object" ? detail : null;
  const unopened = useUnopenedDocs(d?.unopenedDocIds);
  const p = d?.profile ?? {};
  const b = d?.businessProfile ?? {};
  const docs = d?.docs ?? row.docs;
  const missing = d?.missingMandatoryFields ?? row.missingFields;
  const pendingDocs = docs.filter((x) => x.status === "pending");
  const decidedCount = docs.length - pendingDocs.length;
  const due = dueState(row.submittedAt ?? row.createdAt, now);
  const name = companyName(row, d);
  const loadingDetail = detail === undefined;

  const str = (v: unknown) => displayValue(v) || null;
  const website = str(b.websiteUrl);

  // The document on show: the one picked, else the first still to review.
  const doc =
    docs.find((x) => `doc:${x.id}` === tab) ?? pendingDocs[0] ?? docs[0] ?? null;
  // Until the account loads, this admin's opened list isn't known.
  const docOpened = d !== null && doc !== null && !unopened.includes(doc.id);
  const missingDocs = missing.filter(isDocumentKey).map((k) => fieldByKey(k)).filter(Boolean);
  const missingProfile = MANDATORY_FIELDS.filter((f) => missing.includes(f.key));
  const canApprove = !loadingDetail && missing.length === 0 && pendingDocs.length === 0;

  const link = (href: string, text: string) => (
    <a
      href={/^https?:\/\//i.test(href) ? href : `https://${href}`}
      target="_blank"
      rel="noopener noreferrer"
      className="underline decoration-ink/25 underline-offset-4 hover:decoration-ink"
    >
      {text}
    </a>
  );

  return (
    <Reveal as="section" aria-label={`${name} — KYB review`} className="relief rounded-[32px] p-5 sm:p-7" y={10} duration={0.5}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="t-code text-fg-3">{refId("KYB", row.userId)}</span>
            {decision ? (
              <Chip tone={decision.outcome === "approved" ? "verified" : "frozen"}>
                {decision.outcome === "approved" ? "Approved" : "Rejected"}
              </Chip>
            ) : (
              <Chip tone="neutral">queued</Chip>
            )}
          </div>
          <h2 className="t-title1 mt-2 break-words text-fg">{name}</h2>
          <p className="t-callout mt-1 text-fg-3">
            {[row.fullName, row.email].filter(Boolean).join(" · ")} · submitted {fmtAgo(row.submittedAt ?? row.createdAt, now)}
          </p>
        </div>
        {!decision ? (
          <span
            className={cn(
              "t-code shrink-0 rounded-full px-3 py-1.5",
              due.over ? "bg-danger-soft text-danger" : "well text-fg-2",
            )}
          >
            {due.label}
          </span>
        ) : null}
      </div>

      {detail === "error" ? (
        <p className="t-sub mt-4 text-fg-3">Full account didn&apos;t load — showing the queue summary.</p>
      ) : null}

      {/* ── Business profile: only what onboarding collects ── */}
      <div className="mt-7">
        {loadingDetail ? (
          <Paper eyebrow="Loading the account…" title={name} stamp="none" aria-busy="true">
            <div className="mt-6 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-4 animate-pulse rounded-full bg-ink/[0.07]" style={{ width: `${80 - i * 9}%` }} />
              ))}
            </div>
          </Paper>
        ) : (
          <Paper
            eyebrow={`Business profile · ${str(b.country) ?? row.country ?? "—"}`}
            title={str(b.legalName) ?? name}
            stampIcon="building"
            stamp={missingProfile.length ? "pending" : "none"}
          >
            <PaperRows>
              <PaperRow label="Legal name" value={str(b.legalName)} />
              <PaperRow label="Entity type" value={entityTypeLabel(str(b.entityType)) || null} />
              <PaperRow label="Registered address" value={str(b.addressLine)} />
              <PaperRow label="State / region" value={str(b.state)} />
              <PaperRow label="Country" value={str(b.country) ?? row.country} />
              <PaperRow label="Website" value={website ? link(website, website) : null} />
              <PaperRow label="Signs in as" value={str(p.fullName) ?? row.fullName} />
              <PaperRow label="Email" value={<span className="break-all">{row.email}</span>} />
              <PaperRow label="Email confirmed" value={d?.emailVerifiedAt ? fmtDateTime(d.emailVerifiedAt) : "Not yet"} />
            </PaperRows>
          </Paper>
        )}
        {missingProfile.length && !decision ? (
          <div className="mt-3">
            <Notice tone="move">
              Missing from the profile: {missingProfile.map((f) => f.label).join(", ")}.{" "}
              <Link href={`/admin/users/${row.userId}`} className="font-semibold underline underline-offset-4">
                Fill it on the account page
              </Link>
              .
            </Notice>
          </div>
        ) : null}
      </div>

      {/* ── Documents: a list, then the one picked with its own decision ── */}
      <section aria-labelledby={`kyb-${row.userId}-docs`} className="mt-8">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <h3 id={`kyb-${row.userId}-docs`} className="t-title3 text-fg">
            Documents
          </h3>
          {docs.length ? (
            <span className="t-code text-fg-3">
              {decidedCount} of {docs.length} decided
            </span>
          ) : null}
        </div>

        {missingDocs.length ? (
          <div className="mt-3">
            <Notice tone="move">
              Required but not added yet: {missingDocs.map((f) => f!.label).join(", ")}.
            </Notice>
          </div>
        ) : null}

        {docs.length === 0 ? (
          <p className="t-sub mt-3 text-fg-3">{loadingDetail ? "Loading documents…" : "No documents added yet."}</p>
        ) : (
          <div className="mt-4 grid gap-5 xl:grid-cols-[minmax(0,280px)_minmax(0,1fr)] xl:items-start">
            <ul className="flex flex-col gap-2" aria-label="Documents they added">
              {docs.map((x) => {
                const meta = DOC_STATUS[x.status];
                const on = doc?.id === x.id;
                return (
                  <li key={x.id}>
                    <button
                      type="button"
                      onClick={() => onTab(`doc:${x.id}`)}
                      aria-pressed={on}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-[18px] p-3.5 text-left transition-colors",
                        on ? "bg-cream text-ink" : "well hover:bg-ink/[0.05]",
                      )}
                    >
                      <Icon name={x.hasFile ? "doc-check" : "passport"} size={17} className="shrink-0" />
                      <span className="min-w-0 flex-1">
                        <span className="t-callout block break-words font-medium">{x.certType}</span>
                        <span className={cn("t-foot block", on ? "text-ink/60" : "text-fg-3")}>
                          {[x.isOther ? "Other" : null, x.hasFile ? "File" : null, x.hasValue ? "Number" : null]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      </span>
                      <Chip tone={meta.tone} size="sm" noIcon>
                        {meta.label}
                      </Chip>
                    </button>
                  </li>
                );
              })}
            </ul>

            {doc ? (
              <div className="min-w-0">
                <AccessScope id={row.businessId}>
                  <DocPaper doc={doc} owner={name} preview />
                </AccessScope>
                {doc.status === "rejected" && doc.rejectionReason ? (
                  <p className="t-sub mt-3 text-fg-3">Rejected: “{doc.rejectionReason}”</p>
                ) : null}
                {!decision ? (
                  <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
                    <span className="t-sub mr-auto text-fg-3">
                      {doc.status !== "pending"
                        ? `${DOC_STATUS[doc.status].label} — you can change it.`
                        : docOpened
                          ? "Opened — approve or reject this document."
                          : `Open the ${doc.hasFile ? "file" : "number"} above before approving.`}
                    </span>
                    {doc.status !== "rejected" ? (
                      <Button variant="danger" size="sm" icon="close" onClick={() => onRejectDoc(doc)} disabled={busy}>
                        Reject document…
                      </Button>
                    ) : null}
                    {doc.status !== "approved" ? (
                      // One tap: a document's decision can be changed, unlike the company's.
                      <Button
                        variant="primary"
                        size="sm"
                        icon="check"
                        onClick={() => void onApproveDoc(doc)}
                        loading={busy}
                        disabled={busy || (doc.status === "pending" && !docOpened)}
                      >
                        Approve document
                      </Button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        )}
      </section>

      {actionErr ? (
        <div className="mt-6">
          <Notice tone="frozen">{actionErr}</Notice>
        </div>
      ) : null}

      {/* ── Company decision ── */}
      <div className="mt-8 border-t border-line pt-6">
        {decision ? (
          <div className="well rounded-[18px] p-4">
            <p className="t-callout text-fg-2">
              {decision.outcome === "approved" ? "Approved" : "Rejected"} {fmtAgo(new Date(decision.at).toISOString(), now)}
              {decision.reason ? <span className="text-fg-3"> — “{decision.reason}”</span> : null}
            </p>
            <LinkButton href={`/admin/users/${row.userId}`} variant="quiet" size="sm" iconRight="arrow-up-right" className="-ml-3 mt-2">
              Open account
            </LinkButton>
          </div>
        ) : docsOnly ? (
          <div className="well rounded-[18px] p-4">
            <p className="t-callout text-fg">Verified business · new documents</p>
            <p className="t-sub mt-1 text-fg-3">
              The company stays verified. Approve or reject each new document above.
              {pendingDocs.length ? ` ${plural(pendingDocs.length, "document")} left.` : ""}
            </p>
            <LinkButton href={`/admin/users/${row.userId}`} variant="quiet" size="sm" iconRight="arrow-up-right" className="-ml-3 mt-2">
              Open account
            </LinkButton>
          </div>
        ) : (
          <>
            <p className="t-label text-fg-3">Verify the company</p>
            <p className="t-sub mb-3 mt-1 text-fg-3">
              {loadingDetail
                ? "Loading the account…"
                : missing.length
                  ? `${plural(missing.length, "required item")} missing — the profile and required documents must be in.`
                  : pendingDocs.length
                    ? `Decide each document first: ${plural(pendingDocs.length, "document")} still to review.`
                    : "Every document is decided and the profile is complete."}
            </p>
            <TwinFlags sameNameAs={d?.sameNameAs ?? []} relatedTo={d?.relatedTo ?? []} />
            <div className="grid gap-2 sm:grid-cols-[auto_auto_minmax(0,1fr)]">
              <LinkButton href={`/admin/users/${row.userId}`} variant="secondary" icon="arrow-up-right">
                Open account
              </LinkButton>
              <Button variant="danger" icon="close" onClick={onReject} disabled={busy}>
                Reject…
              </Button>
              <HoldButton
                tone="commit"
                icon="shield"
                block
                className="rounded-[18px]"
                onCommit={onApprove}
                loading={busy}
                disabled={!canApprove}
              >
                Verify company
              </HoldButton>
            </div>
          </>
        )}
      </div>
    </Reveal>
  );
}
