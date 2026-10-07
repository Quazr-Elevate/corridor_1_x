"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Check,
  Loader2,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";
import { adminApi, type VerifyQueueRow } from "@/lib/adminApi";
import { RejectReasonModal } from "@/components/admin/RejectReasonModal";

const USER_REJECT_QUICK_REASONS = [
  "Legal company name doesn't match what we can verify online.",
  "Phone number looks personal — please provide a business line.",
  "Operating countries list is empty or clearly incorrect.",
  "Position / role is missing or appears not to be a decision-making title.",
  "Industry mismatch with the trade position you selected.",
] as const;

export default function VerifyQueuePage() {
  const [rows, setRows] = useState<VerifyQueueRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  // Target of the open "reject reason" modal. We hold the whole row so
  // the modal can show the user's name/email in the subtitle without
  // another lookup round-trip.
  const [rejectTarget, setRejectTarget] = useState<VerifyQueueRow | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const q = await adminApi.verifyQueue();
      setRows(q);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function approve(userId: string) {
    setBusyId(userId);
    try {
      await adminApi.verifyUser(userId);
      setRows((r) => r.filter((u) => u.userId !== userId));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setBusyId(null);
    }
  }

  async function reject(reason: string) {
    if (!rejectTarget) return;
    const userId = rejectTarget.userId;
    setBusyId(userId);
    try {
      await adminApi.rejectUser(userId, reason);
      setRows((r) => r.filter((u) => u.userId !== userId));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="mx-auto max-w-[1240px] px-6 py-8">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div>
          <p className="text-[12px]" style={{ color: "var(--sp-text-3)" }}>
            Admin console · Verification queue
          </p>
          <h1
            className="mt-1 text-[34px] font-semibold tracking-[-0.025em]"
            style={{ color: "var(--sp-text)" }}
          >
            {rows.length} user{rows.length === 1 ? "" : "s"} awaiting review
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/admin"
            className="sp-chip"
            style={{ paddingLeft: "0.75rem" }}
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> Dashboard
          </Link>
          <button
            type="button"
            onClick={load}
            aria-label="Refresh"
            className="sp-icon-btn"
          >
            <RefreshCw className="h-4 w-4" aria-hidden />
          </button>
        </div>
      </div>

      {err && (
        <div
          className="sp-airy mt-6 p-4 text-[13px]"
          style={{ color: "var(--sp-error)" }}
        >
          {err}
        </div>
      )}

      {loading ? (
        <div className="mt-6 flex justify-center py-12">
          <Loader2
            className="h-6 w-6 animate-spin"
            style={{ color: "var(--sp-lime)" }}
          />
        </div>
      ) : rows.length === 0 ? (
        <section className="sp-airy mt-6 p-10 text-center">
          <div
            className="mx-auto flex h-12 w-12 items-center justify-center rounded-full"
            style={{
              background: "var(--sp-lime-14)",
              color: "var(--sp-lime)",
            }}
          >
            <ShieldCheck className="h-6 w-6" aria-hidden />
          </div>
          <p
            className="mt-4 text-[15px] font-semibold"
            style={{ color: "var(--sp-text)" }}
          >
            Queue is empty
          </p>
          <p
            className="mt-1 text-[12.5px]"
            style={{ color: "var(--sp-text-3)" }}
          >
            All onboarded users have been reviewed. Nothing to do right now.
          </p>
        </section>
      ) : (
        <div className="mt-6 space-y-4">
          {rows.map((row) => (
            <QueueCard
              key={row.userId}
              row={row}
              busy={busyId === row.userId}
              onApprove={() => approve(row.userId)}
              onReject={() => setRejectTarget(row)}
            />
          ))}
        </div>
      )}

      <RejectReasonModal
        open={rejectTarget != null}
        onClose={() => setRejectTarget(null)}
        onSubmit={reject}
        title="Reject Verified-badge application"
        subtitle={
          rejectTarget
            ? `${rejectTarget.businessName || rejectTarget.fullName || "This user"} will see this note on their next login.`
            : undefined
        }
        quickReasons={USER_REJECT_QUICK_REASONS}
        submitLabel="Reject user"
      />
    </div>
  );
}

function QueueCard({
  row,
  busy,
  onApprove,
  onReject,
}: {
  row: VerifyQueueRow;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
}) {
  const initials = (row.fullName || row.businessName || row.email)
    .split(/\s+/)
    .map((s) => s[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <section className="sp-airy p-5">
      <div className="flex flex-wrap items-start gap-4">
        <div
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold"
          style={{ background: "var(--sp-lime-14)", color: "var(--sp-lime)" }}
        >
          {initials || "?"}
        </div>
        <div className="min-w-0 flex-1">
          <p
            className="text-[15px] font-semibold"
            style={{ color: "var(--sp-text)" }}
          >
            {row.businessName || row.fullName || "Unnamed"}
          </p>
          <p
            className="mt-0.5 text-[12.5px]"
            style={{ color: "var(--sp-text-2)" }}
          >
            {row.email}
          </p>
          <div
            className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px]"
            style={{ color: "var(--sp-text-3)" }}
          >
            {row.fullName && row.businessName && <span>{row.fullName}</span>}
            {row.country && <span>· {row.country}</span>}
            {row.industry && <span>· {row.industry}</span>}
            {row.tradePosition && (
              <span>· {capitalize(row.tradePosition)}</span>
            )}
            {row.operatingCountries && row.operatingCountries.length > 0 && (
              <span>
                · Operates in {row.operatingCountries.join(", ")}
              </span>
            )}
            {row.submittedAt && (
              <span>
                · Submitted {new Date(row.submittedAt).toLocaleDateString()}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onReject}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-semibold transition disabled:opacity-50"
            style={{
              borderColor: "var(--sp-border)",
              color: "var(--sp-error)",
            }}
          >
            <X className="h-3.5 w-3.5" aria-hidden /> Reject
          </button>
          <button
            type="button"
            onClick={onApprove}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-semibold transition disabled:opacity-50"
            style={{
              background: "var(--sp-lime)",
              color: "var(--sp-lime-fg)",
            }}
          >
            {busy ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
            ) : (
              <Check className="h-3.5 w-3.5" aria-hidden />
            )}
            Approve
          </button>
        </div>
      </div>

    </section>
  );
}


function capitalize(s: string): string {
  return s.length === 0 ? s : s[0].toUpperCase() + s.slice(1);
}
