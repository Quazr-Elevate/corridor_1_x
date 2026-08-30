"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Clock, XCircle } from "lucide-react";
import { Rise } from "@/components/admin/spatial";
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
  return <QueueContent />;
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
    return <p className="text-sm" style={{ color: "var(--sp-text-3)" }}>Loading queue…</p>;
  }

  return (
    <div className="mx-auto max-w-[1000px] space-y-6">
      <Rise i={0}>
        <p className="text-[12px]" style={{ color: "var(--sp-text-3)" }}>Admin console · Verification queue</p>
        <h1 className="mt-1 text-[34px] font-semibold tracking-[-0.025em]" style={{ color: "var(--sp-text)" }}>
          {totalPending} user{totalPending === 1 ? "" : "s"} awaiting review
        </h1>
        <p className="mt-2 max-w-lg text-[13.5px]" style={{ color: "var(--sp-text-2)" }}>
          Grouped by where they&apos;re stuck. Longest dwell time is on top of each list.
        </p>
      </Rise>

      {/* Sticky bulk-action bar */}
      {totalSelected > 0 && (
        <div className="sp-airy sticky top-4 z-20 flex flex-wrap items-center justify-between gap-3 px-4 py-3 backdrop-blur">
          <span className="text-[13px]" style={{ color: "var(--sp-text)" }}>{totalSelected} selected</span>
          <div className="flex items-center gap-3">
            <button type="button" onClick={() => setSelected(new Set())} className="text-[12px]" style={{ color: "var(--sp-text-3)" }} disabled={busy}>
              Clear
            </button>
            <button
              type="button"
              onClick={bulkVerify}
              disabled={busy}
              className="rounded-full px-4 py-2 text-[12.5px] font-bold transition-colors disabled:opacity-60"
              style={{ background: "var(--sp-lime)", color: "var(--sp-lime-fg)" }}
            >
              Approve selected
            </button>
          </div>
        </div>
      )}

      {msg && (
        <p className="sp-airy px-4 py-2.5 text-[12.5px]" style={{ color: "var(--sp-text)" }}>{msg}</p>
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
    <section className="sp-airy overflow-hidden">
      <header className="flex items-center justify-between gap-3 px-5 py-4" style={{ borderBottom: "1px solid var(--sp-border)" }}>
        <div>
          <h2 className="text-[14px] font-semibold" style={{ color: "var(--sp-text)" }}>
            {label} <span className="ml-1" style={{ color: "var(--sp-text-3)" }}>· {rows.length}</span>
          </h2>
          <p className="mt-0.5 text-[11.5px]" style={{ color: "var(--sp-text-3)" }}>{hint}</p>
        </div>
        {rows.length > 0 && (
          <label className="flex items-center gap-2 text-[11px]" style={{ color: "var(--sp-text-3)" }}>
            <input type="checkbox" checked={allChecked} onChange={(e) => onToggleGroup(rows, e.target.checked)} className="h-4 w-4 accent-[#8a9a1f]" />
            Select all
          </label>
        )}
      </header>

      {rows.length === 0 ? (
        <p className="px-5 py-7 text-center text-[12px]" style={{ color: "var(--sp-text-3)" }}>Nothing to review here — nice.</p>
      ) : (
        <ul>
          {rows.map((r, i) => (
            <li
              key={r.userId}
              className="grid grid-cols-[auto_minmax(0,3fr)_minmax(0,2fr)_auto_auto] items-center gap-3 px-5 py-3.5"
              style={{ borderTop: i === 0 ? "none" : "1px solid var(--sp-border)" }}
            >
              <input type="checkbox" checked={selected.has(r.userId)} onChange={() => onToggle(r.userId)} className="h-4 w-4 accent-[#8a9a1f]" />
              <div className="min-w-0">
                <Link href={`/admin/users/${r.userId}`} className="truncate text-[13px] font-medium hover:underline" style={{ color: "var(--sp-text)" }}>
                  {r.fullName || "(no name yet)"}
                </Link>
                <p className="text-[11px]" style={{ color: "var(--sp-text-3)" }}>
                  {r.mobile || "no mobile"}{r.state ? ` · ${r.state}` : ""}
                </p>
              </div>
              <div className="min-w-0 text-[12px]" style={{ color: "var(--sp-text-2)" }}>{r.companyName || "—"}</div>
              <span
                className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-semibold"
                style={
                  r.dwellDays >= 3
                    ? { background: "rgba(224,80,80,0.12)", color: "var(--sp-error)" }
                    : { background: "var(--sp-lime-10)", color: "var(--sp-lime)" }
                }
                title={`Stuck since ${new Date(r.updatedAt).toLocaleDateString()}`}
              >
                <Clock className="h-3 w-3" aria-hidden />
                {r.dwellDays}d
              </span>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => onVerify(r.userId)}
                  disabled={busy}
                  className="inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-[11px] font-bold transition-colors disabled:opacity-50"
                  style={{ background: "var(--sp-lime)", color: "var(--sp-lime-fg)" }}
                >
                  <CheckCircle2 className="h-3 w-3" aria-hidden /> Verify
                </button>
                <button
                  type="button"
                  onClick={() => onReject(r.userId)}
                  disabled={busy}
                  className="inline-flex items-center gap-1 rounded-full px-2.5 py-1.5 text-[11px] transition-colors disabled:opacity-50"
                  style={{ border: "1px solid var(--sp-border)", color: "var(--sp-text-3)" }}
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
