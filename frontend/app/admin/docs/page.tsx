"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { adminApi, errorMessage, type PendingDocRow } from "@/lib/adminApi";
import { cn } from "@/lib/cn";
import { useTower } from "@/components/shell/TowerShell";
import { Reveal } from "@/components/motion";
import { Button, LinkButton } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { HoldButton, Segmented } from "@/components/ui/Controls";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Card, EmptyState, Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { DOC_REJECT_REASONS, RejectSheet } from "@/components/admin/RejectSheet";
import { ClearQueue } from "@/components/admin/ClearQueue";
import { LaneHeader } from "@/components/admin/tower";
import {
  DocPaper,
  KbdHints,
  OpenDocLink,
  QueueList,
  useNow,
  useQueueKeys,
  type QueueItem,
} from "@/components/admin/parts";
import { dueState, fmtAgo, plural, refId } from "@/components/admin/format";

type View = "queue" | "decided";
type Outcome = "approved" | "rejected";

interface Decided {
  row: PendingDocRow;
  outcome: Outcome;
  reason?: string;
  at: number;
}

const owner = (r: PendingDocRow) => r.userBusinessName || r.userFullName || r.userEmail;

export default function DocsLanePage() {
  const { refreshStats } = useTower();
  const toast = useToast();
  const now = useNow();

  const [rows, setRows] = useState<PendingDocRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [view, setView] = useState<View>("queue");
  const [decided, setDecided] = useState<Decided[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [rejectRow, setRejectRow] = useState<PendingDocRow | null>(null);
  const detailRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const q = await adminApi.pendingDocs();
      setRows(q);
      setErr(null);
      setSelectedId((cur) => (cur && q.some((r) => r.doc.id === cur) ? cur : q[0]?.doc.id ?? null));
    } catch (e) {
      setErr(errorMessage(e, "Couldn't load documents."));
      setRows((r) => r ?? []);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const list: PendingDocRow[] = useMemo(
    () => (view === "queue" ? rows ?? [] : decided.map((d) => d.row)),
    [view, rows, decided],
  );
  const selected = list.find((r) => r.doc.id === selectedId) ?? null;
  const decision = view === "decided" ? decided.find((d) => d.row.doc.id === selectedId) ?? null : null;

  useEffect(() => setActionErr(null), [selectedId]);

  const move = useCallback(
    (delta: 1 | -1) => {
      if (!list.length) return;
      const i = list.findIndex((r) => r.doc.id === selectedId);
      const next = Math.max(0, Math.min(list.length - 1, (i < 0 ? 0 : i) + delta));
      setSelectedId(list[next].doc.id);
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
    setSelectedId(src[0]?.doc.id ?? null);
  };

  const settle = (row: PendingDocRow, outcome: Outcome, reason?: string) => {
    const cur = rows ?? [];
    const idx = cur.findIndex((r) => r.doc.id === row.doc.id);
    const remaining = cur.filter((r) => r.doc.id !== row.doc.id);
    setRows(remaining);
    setDecided((d) => [
      {
        row: { ...row, doc: { ...row.doc, status: outcome, rejectionReason: reason ?? null } },
        outcome,
        reason,
        at: Date.now(),
      },
      ...d,
    ]);
    setSelectedId(remaining[Math.min(Math.max(idx, 0), remaining.length - 1)]?.doc.id ?? null);
    void refreshStats();
  };

  const approve = async () => {
    if (!selected) return;
    const row = selected;
    setBusy(true);
    setActionErr(null);
    try {
      await adminApi.approveDoc(row.doc.id);
      toast(`${row.doc.certType} approved`, "verified");
      settle(row, "approved");
    } catch (e) {
      const msg = errorMessage(e, "Approve failed.");
      setActionErr(msg);
      toast(msg, "frozen");
    } finally {
      setBusy(false);
    }
  };

  const reject = async (reason: string) => {
    if (!rejectRow) return;
    const row = rejectRow;
    await adminApi.rejectDoc(row.doc.id, reason);
    toast(`${row.doc.certType} rejected`);
    settle(row, "rejected", reason);
  };
  const closeReject = useCallback(() => setRejectRow(null), []);

  const items: QueueItem[] = list.map((r) => {
    const d = view === "decided" ? decided.find((x) => x.row.doc.id === r.doc.id) : undefined;
    return {
      id: r.doc.id,
      code: refId("DOC", r.doc.id),
      title: r.doc.certType,
      sub: [owner(r), r.userCountry].filter(Boolean).join(" · "),
      due: view === "queue" ? dueState(r.doc.uploadedAt, now) : undefined,
      tag: d ? (
        <span className="t-foot font-semibold">
          {d.outcome === "approved" ? "Approved" : "Rejected"} · {fmtAgo(new Date(d.at).toISOString(), now)}
        </span>
      ) : undefined,
    };
  });

  const loading = rows === null;
  const clear = !loading && items.length === 0;
  const overdue = (rows ?? []).filter((r) => dueState(r.doc.uploadedAt, now).over).length;

  return (
    <div className="pt-4">
      <LaneHeader
        eyebrow="Lane · Documents"
        title="Document checks"
        subtitle={
          <>
            Open each file, match it to the account, then hold to approve. Oldest uploads first.
            {overdue ? <span className="font-medium text-danger"> {plural(overdue, "file")} past 24 hours.</span> : null}
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
                { value: "queue", label: "Queue", count: rows?.length ?? 0 },
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
            title="Couldn't load documents"
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
              eyebrow="Documents · 0"
              title="Nothing to check"
              icon="doc-check"
              objectPosition="22% 30%"
              actions={
                <>
                  <LinkButton href="/admin/verify" variant="secondary" size="sm" icon="passport">
                    KYB lane
                  </LinkButton>
                  <LinkButton href="/admin/users" variant="quiet" size="sm" iconRight="arrow-right">
                    Directory
                  </LinkButton>
                </>
              }
            >
              New uploads land here, oldest first — certificates companies add to their passport.
              {decided.length ? ` ${plural(decided.length, "document")} decided this session.` : null}
            </ClearQueue>
          ) : (
            <Card className="p-2">
              <EmptyState icon="stamp" title="Nothing decided yet">
                Documents you approve or reject this session collect here.
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
                  label={view === "queue" ? "Documents awaiting review" : "Decided this session"}
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
                  <Skeleton className="h-[240px] rounded-[18px]" />
                </div>
              </Card>
            ) : selected ? (
              <DocPanel
                key={selected.doc.id}
                row={selected}
                now={now}
                decision={decision}
                busy={busy}
                actionErr={actionErr}
                onApprove={approve}
                onReject={() => setRejectRow(selected)}
              />
            ) : null}
          </div>
        </div>
      )}

      <RejectSheet
        open={rejectRow !== null}
        onClose={closeReject}
        title={rejectRow ? `Reject ${rejectRow.doc.certType}?` : "Reject document"}
        description={rejectRow ? `${owner(rejectRow)} will see your reason and can upload a new file.` : undefined}
        quickReasons={DOC_REJECT_REASONS}
        submitLabel="Reject"
        onSubmit={reject}
      />
    </div>
  );
}

function DocPanel({
  row,
  now,
  decision,
  busy,
  actionErr,
  onApprove,
  onReject,
}: {
  row: PendingDocRow;
  now: number;
  decision: Decided | null;
  busy: boolean;
  actionErr: string | null;
  onApprove: () => void | Promise<void>;
  onReject: () => void;
}) {
  const { doc } = row;
  const due = dueState(doc.uploadedAt, now);

  const facts: Array<{ icon: IconName; label: string; value: string | null; mono?: boolean }> = [
    { icon: "building", label: "Company", value: row.userBusinessName },
    { icon: "user", label: "Contact", value: row.userFullName },
    { icon: "mail", label: "Email", value: row.userEmail },
    { icon: "globe", label: "Country", value: row.userCountry },
  ];

  return (
    <Reveal
      as="section"
      aria-label={`${doc.certType} — document review`}
      className="relief rounded-[32px] p-5 sm:p-7"
      y={10}
      duration={0.5}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="t-code text-fg-3">{refId("DOC", doc.id)}</span>
            {decision ? (
              <Chip tone={decision.outcome === "approved" ? "verified" : "frozen"}>
                {decision.outcome === "approved" ? "Approved" : "Rejected"}
              </Chip>
            ) : (
              <Chip tone="neutral">pending</Chip>
            )}
          </div>
          <h2 className="t-title1 mt-2 break-words text-fg">{doc.certType}</h2>
          <p className="t-callout mt-1 text-fg-3">
            {owner(row)} · uploaded {fmtAgo(doc.uploadedAt, now)}
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

      <div className="mt-7 grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <div className="min-w-0">
          <DocPaper doc={doc} owner={owner(row)} preview />
        </div>

        <div className="flex min-w-0 flex-col">
          <p className="t-label text-fg-3">Match against the account</p>
          <ul className="mt-3 space-y-2.5">
            {facts.map((f) => (
              <li key={f.label} className="well flex items-start gap-3 rounded-[18px] p-3.5">
                <span className="relief-sm mt-0.5 grid size-7 shrink-0 place-items-center rounded-full text-fg-2">
                  <Icon name={f.icon} size={14} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="t-label text-fg-3">{f.label}</p>
                  <p className={cn("t-callout mt-1 break-words", f.value ? "text-fg" : "text-fg-3")}>
                    {f.value || "Not filled"}
                  </p>
                </div>
              </li>
            ))}
          </ul>
          <p className="t-sub mt-3 text-fg-3">
            The name and details on the file should match the company above. If they don&apos;t, reject with what to fix.
          </p>

          {decision?.reason ? (
            <div className="mt-4">
              <Notice tone="frozen" title="Rejected">
                {decision.reason}
              </Notice>
            </div>
          ) : null}
          {actionErr ? (
            <div className="mt-4">
              <Notice tone="frozen">{actionErr}</Notice>
            </div>
          ) : null}

          <div className="mt-auto pt-6">
            {decision ? (
              <div className="well rounded-[18px] p-4">
                <p className="t-callout text-fg-2">
                  {decision.outcome === "approved" ? "Approved" : "Rejected"} {fmtAgo(new Date(decision.at).toISOString(), now)}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <LinkButton href={`/admin/users/${row.userId}`} variant="quiet" size="sm" iconRight="arrow-up-right" className="-ml-3">
                    Open account
                  </LinkButton>
                  <OpenDocLink doc={doc} />
                </div>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-2">
                  <LinkButton href={`/admin/users/${row.userId}`} variant="secondary" icon="arrow-up-right">
                    Open account
                  </LinkButton>
                  <Button variant="danger" icon="close" onClick={onReject} disabled={busy}>
                    Reject…
                  </Button>
                </div>
                <HoldButton
                  tone="commit"
                  icon="check"
                  block
                  className="mt-2 rounded-[18px]"
                  onCommit={onApprove}
                  loading={busy}
                >
                  Approve document
                </HoldButton>
              </>
            )}
          </div>
        </div>
      </div>
    </Reveal>
  );
}
