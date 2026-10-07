"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, ArrowRight, X } from "lucide-react";
import { useMe } from "@/lib/useMe";

/**
 * First-time popup on /dashboard whenever the admin rejects a Verified-
 * badge application. Mirrors ``RejectedDocsPopup`` but keyed on the
 * user's ``verification_submitted_at`` timestamp — once dismissed for
 * that submission the user still has the persistent bar from
 * ``VerificationProgress`` as a reminder, so hiding this popup doesn't
 * lose the information.
 *
 * We key acknowledgement on the submission timestamp (not just a bool)
 * so a user who fixes their profile, gets rejected a second time, sees
 * a fresh popup for the new rejection.
 */

// Keyed per user so dismissals on a shared machine don't bleed between
// accounts. The stored value is the submission timestamp of the
// rejection the user already saw — a resubmit + fresh rejection stamps
// a new timestamp and surfaces the popup again.
const ACK_KEY_PREFIX = "cor1x.verificationRejectionAcknowledged.";

function ackKey(userId: string): string {
  return `${ACK_KEY_PREFIX}${userId}`;
}

function loadAcknowledged(userId: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(ackKey(userId));
  } catch {
    return null;
  }
}

function saveAcknowledged(userId: string, stamp: string) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(ackKey(userId), stamp);
  } catch {
    // Private windows throw — silently ignore.
  }
}

export function RejectedVerificationPopup() {
  const router = useRouter();
  const { me } = useMe();
  const [dismissed, setDismissed] = useState(false);

  // The identifier for "this rejection round" — use submitted_at because
  // a resubmission issues a new timestamp and the stored ack won't match.
  const stamp = me?.verification?.submittedAt ?? me?.verification?.verifiedAt ?? "";

  useEffect(() => {
    if (!me) return;
    if (me.verification.status !== "rejected") return;
    const prev = loadAcknowledged(me.userId);
    // Only treat as dismissed if the ack matches the current rejection
    // stamp. A fresh rejection (new submitted_at after a resubmit) does
    // NOT match, so the popup fires again. Default to showing when
    // either side is empty.
    setDismissed(Boolean(prev && stamp && prev === stamp));
  }, [me, stamp]);

  if (!me) return null;
  if (me.verification.status !== "rejected") return null;
  if (dismissed) return null;

  const reason =
    me.verification.rejectedReason ||
    "Our team couldn't approve your profile. Please update the flagged fields and resubmit.";

  function dismiss() {
    if (stamp && me) saveAcknowledged(me.userId, stamp);
    setDismissed(true);
  }

  function goFix() {
    dismiss();
    router.push("/dashboard/account?tab=primary");
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={dismiss}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-card border border-danger/40 bg-ink-soft shadow-card overflow-hidden"
      >
        <div className="flex items-start gap-3 p-5 border-b border-line-soft">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-danger/15 text-danger">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold text-paper">
              Verification not approved
            </h2>
            <p className="mt-0.5 text-xs text-paper-muted">
              Your Cor1x profile needs changes before we can issue the Verified
              badge.
            </p>
          </div>
          <button
            type="button"
            onClick={dismiss}
            aria-label="Dismiss"
            className="rounded-full p-1.5 text-paper-muted hover:bg-ink-elevated hover:text-paper transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-paper-muted mb-2">
            Admin&apos;s note
          </p>
          <div className="rounded-field border border-danger/30 bg-danger/5 p-3">
            <p className="text-sm text-paper leading-relaxed whitespace-pre-wrap">
              {reason}
            </p>
          </div>
          <p className="mt-4 text-xs text-paper-muted leading-relaxed">
            Update your profile with the changes above and save — we&apos;ll
            re-review automatically.
          </p>
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-line-soft">
          <button
            type="button"
            onClick={dismiss}
            className="rounded-field border border-line-soft bg-transparent px-3 py-2 text-xs font-semibold text-paper-muted hover:text-paper transition"
          >
            Later
          </button>
          <button
            type="button"
            onClick={goFix}
            className="inline-flex items-center gap-1.5 rounded-field bg-accent px-4 py-2 text-xs font-semibold text-accent-fg shadow-cta hover:bg-accent-hover transition"
          >
            Fix profile
            <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          </button>
        </div>
      </div>
    </div>
  );
}
