"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Clock, XCircle } from "lucide-react";
import { AdminShell } from "@/components/admin/AdminShell";
import {
  adminApi,
  type QueueRow,
  type VerificationQueue,
} from "@/lib/adminApi";

// Human labels + a short blurb per stage, kept together so the four
// section headers below stay in sync.
const STAGE_META: Array<{
  key: keyof VerificationQueue;
  label: string;
  hint: string;
}> = [
  { key: "bankPending", label: "Bank pending", hint: "Business filled, waiting on bank details." },
  { key: "businessPending", label: "Business pending", hint: "Primary filled, needs GSTIN/PAN + company." },
  { key: "primaryPending", label: "Primary pending", hint: "Signed up, hasn't filled name/address yet." },
  { key: "signedUp", label: "Signed up", hint: "OTP-verified only, no profile started." },
];

export default function VerifyQueuePage() {
  return (
    <AdminShell>
      <QueueContent />
    </AdminShell>
  );
}

function QueueContent() {
  const [queue, setQueue] = useState<VerificationQueue | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    const q = await adminApi.verifyQueue();
    setQueue(q);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const totalSelected = selected.size;

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleGroup = (rows: QueueRow[], checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      for (const r of rows) {
        if (checked) next.add(r.userId);
        else next.delete(r.userId);
      }
      return next;
    });
  };

  const bulkVerify = async () => {
    if (!selected.size) return;
    setBusy(true);
    try {
      const res = await adminApi.bulkVerify(Array.from(selected));
      setMsg(
        `Verified ${res.verified}${res.skipped.length ? ` · skipped ${res.skipped.length}` : ""}`,
      );
      setSelected(new Set());
      await load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Bulk verify failed");
    } finally {
      setBusy(false);
      setTimeout(() => setMsg(null), 4000);
    }
  };

  const verifyOne = async (id: string) => {
    setBusy(true);
    try {
      await adminApi.verifyUser(id);
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      await load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Verify failed");
    } finally {
      setBusy(false);
    }
  };

  const rejectOne = async (id: string) => {
    if (!confirm("Reject this user? They won't be able to reveal contacts.")) return;
    setBusy(true);
    try {
      await adminApi.rejectUser(id);
      await load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Reject failed");
    } finally {
      setBusy(false);
    }
  };

  const totalPending = useMemo(
    () =>
      queue
        ? STAGE_META.reduce((n, s) => n + (queue[s.key]?.length ?? 0), 0)
        : 0,
    [queue],
  );

  if (!queue) {
    return <p className="text-sm text-paper-muted">Loading queue…</p>;
  }

  return (
    <div className="space-y-8">
      <header>
        <p className="text-[10px] uppercase tracking-widest text-paper-muted">
          Admin · Verification queue
        </p>
        <h1 className="mt-1 text-display text-paper">
          {totalPending} user{totalPending === 1 ? "" : "s"}{" "}
          <span className="text-gradient">awaiting review</span>
        </h1>
        <p className="mt-2 max-w-lg text-sm text-paper-muted">
          Grouped by where they&apos;re stuck. Biggest dwell time is on top of
          each list — the users who&apos;ve waited longest.
        </p>
      </header>

      {/* Sticky bulk-action bar — only visible when something's checked */}
      {totalSelected > 0 && (
        <div className="sticky top-2 z-20 flex flex-wrap items-center justify-between gap-3 rounded-card border border-line-soft bg-ink-soft/90 px-4 py-3 backdrop-blur">
          <span className="text-sm text-paper">
            {totalSelected} selected
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setSelected(new Set())}
              className="text-xs text-paper-muted hover:text-paper"
              disabled={busy}
            >
              Clear
            </button>
            <button
              type="button"
              onClick={bulkVerify}
              disabled={busy}
              className="btn-primary !py-2 !text-xs"
            >
              Approve selected
            </button>
          </div>
        </div>
      )}

      {msg && (
        <p className="rounded-card border border-line-soft bg-ink-soft/60 px-4 py-2 text-xs text-paper">
          {msg}
        </p>
      )}

      {STAGE_META.map((s) => (
        <StageBlock
          key={s.key}
          label={s.label}
          hint={s.hint}
          rows={queue[s.key] ?? []}
          selected={selected}
          onToggle={toggle}
          onToggleGroup={toggleGroup}
          onVerify={verifyOne}
          onReject={rejectOne}
          busy={busy}
        />
      ))}
    </div>
  );
}

function StageBlock({
  label,
  hint,
  rows,
  selected,
  onToggle,
  onToggleGroup,
  onVerify,
  onReject,
  busy,
}: {
  label: string;
  hint: string;
  rows: QueueRow[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  onToggleGroup: (rows: QueueRow[], checked: boolean) => void;
  onVerify: (id: string) => void;
  onReject: (id: string) => void;
  busy: boolean;
}) {
  const allChecked = rows.length > 0 && rows.every((r) => selected.has(r.userId));

  return (
    <section className="rounded-card border border-line-soft bg-ink-soft/40">
      <header className="flex items-center justify-between gap-3 border-b border-line-soft/60 px-4 py-3">
        <div>
          <h2 className="text-sm font-medium text-paper">
            {label}{" "}
            <span className="ml-1 text-paper-muted">· {rows.length}</span>
          </h2>
          <p className="mt-0.5 text-[11px] text-paper-muted">{hint}</p>
        </div>
        {rows.length > 0 && (
          <label className="flex items-center gap-2 text-[11px] text-paper-muted">
            <input
              type="checkbox"
              checked={allChecked}
              onChange={(e) => onToggleGroup(rows, e.target.checked)}
              className="h-3.5 w-3.5 accent-accent"
            />
            Select all
          </label>
        )}
      </header>

      {rows.length === 0 ? (
        <p className="px-4 py-6 text-center text-xs text-paper-muted">
          Nothing to review here — nice.
        </p>
      ) : (
        <ul>
          {rows.map((r) => (
            <li
              key={r.userId}
              className="grid grid-cols-[auto_minmax(0,3fr)_minmax(0,2fr)_auto_auto] items-center gap-3 border-b border-line-soft/40 px-4 py-3 last:border-b-0"
            >
              <input
                type="checkbox"
                checked={selected.has(r.userId)}
                onChange={() => onToggle(r.userId)}
                className="h-3.5 w-3.5 accent-accent"
              />
              <div className="min-w-0">
                <Link
                  href={`/admin/users/${r.userId}`}
                  className="truncate text-sm font-medium text-paper hover:text-accent"
                >
                  {r.fullName || "(no name yet)"}
                </Link>
                <p className="text-[11px] text-paper-muted">
                  {r.mobile || "no mobile"}
                  {r.state ? ` · ${r.state}` : ""}
                </p>
              </div>
              <div className="min-w-0 text-xs text-paper-muted">
                {r.companyName || "—"}
              </div>
              <span
                className={
                  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium " +
                  (r.dwellDays >= 3
                    ? "bg-danger/10 text-danger ring-1 ring-inset ring-danger/30"
                    : "bg-accent/10 text-accent ring-1 ring-inset ring-accent/25")
                }
                title={`Stuck since ${new Date(r.updatedAt).toLocaleDateString()}`}
              >
                <Clock className="h-3 w-3" aria-hidden />
                {r.dwellDays}d
              </span>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => onVerify(r.userId)}
                  disabled={busy}
                  className="inline-flex items-center gap-1 rounded-md bg-accent px-2.5 py-1 text-[11px] font-medium text-accent-fg hover:bg-accent-hover disabled:opacity-50"
                >
                  <CheckCircle2 className="h-3 w-3" aria-hidden /> Verify
                </button>
                <button
                  type="button"
                  onClick={() => onReject(r.userId)}
                  disabled={busy}
                  className="inline-flex items-center gap-1 rounded-md border border-line px-2.5 py-1 text-[11px] text-paper-muted transition-colors hover:text-danger disabled:opacity-50"
                  title="Reject"
                >
                  <XCircle className="h-3 w-3" aria-hidden />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
