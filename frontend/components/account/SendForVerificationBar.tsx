"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  CheckCircle2,
  Clock,
  Loader2,
  ShieldCheck,
  X,
} from "lucide-react";
import { api, type Me } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import { MANDATORY_FIELDS } from "@/lib/verification";

/**
 * Inline "Send for verification" control shown at the bottom-right of
 * every My Account section card (Primary / Company / Business profile).
 *
 * Four visible states, driven entirely by ``me.verification``:
 *   * ``active`` or ``email_verified`` with blanks  — disabled grey
 *     button; tooltip tells the user how many fields remain.
 *   * all 7 filled                                   — enabled accent
 *     "Send for verification" button; click opens the confirm modal.
 *   * ``pending_verification``                       — violet
 *     "Under review" pill, non-interactive.
 *   * ``verified``                                   — green "Verified"
 *     pill, non-interactive.
 *   * ``rejected``                                   — enabled
 *     "Resubmit for verification" button; modal also surfaces the
 *     admin's previous rejection note.
 *
 * The component itself only renders inline content — the parent
 * SectionForm places it in the footer row next to Save. The confirm
 * modal still portals to the viewport so it isn't clipped by the card.
 */
export function SendForVerificationControl() {
  const { me, refetch } = useMe();
  const [confirming, setConfirming] = useState(false);

  const filled = useMemo(() => {
    if (!me) return 0;
    return MANDATORY_FIELDS.length - me.verification.missing.length;
  }, [me]);

  if (!me) return null;
  const v = me.verification;
  const total = v.mandatoryTotal || MANDATORY_FIELDS.length;
  const allFilled = v.missing.length === 0;

  if (v.status === "verified") {
    return (
      <StatusPill tone="accent" icon={BadgeCheck}>
        Verified
      </StatusPill>
    );
  }

  if (v.status === "pending_verification") {
    return (
      <StatusPill tone="violet" icon={Clock}>
        Under review
      </StatusPill>
    );
  }

  const buttonLabel =
    v.status === "rejected" ? "Resubmit for verification" : "Send for verification";

  return (
    <>
      <div className="inline-flex items-center gap-3">
        <span className="hidden sm:inline text-[11px] font-semibold uppercase tracking-widest text-paper-muted">
          Verified badge · {filled} / {total}
        </span>
        <button
          type="button"
          onClick={() => setConfirming(true)}
          disabled={!allFilled}
          title={
            allFilled
              ? "Send your profile to Cor1x admins for review"
              : `${v.missing.length} mandatory field${v.missing.length === 1 ? "" : "s"} still blank`
          }
          className={`inline-flex items-center gap-1.5 rounded-field px-4 py-2.5 text-sm font-semibold shadow-cta transition ${
            allFilled
              ? "bg-accent text-accent-fg hover:bg-accent-hover cursor-pointer"
              : "bg-line-soft/40 text-paper-muted cursor-not-allowed"
          }`}
        >
          <ShieldCheck className="h-4 w-4" aria-hidden />
          {buttonLabel}
        </button>
      </div>

      {confirming && (
        <ConfirmModal
          me={me}
          onCancel={() => setConfirming(false)}
          onSubmitted={async () => {
            await refetch();
            setConfirming(false);
          }}
        />
      )}
    </>
  );
}

// Keep the old export name as an alias — legacy mounts (if any) still
// render, but as inline content now, not a floating bar.
export const SendForVerificationBar = SendForVerificationControl;

// ── Status pill (compact non-interactive state) ─────────────────────

function StatusPill({
  tone,
  icon: Icon,
  children,
}: {
  tone: "accent" | "violet";
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  children: React.ReactNode;
}) {
  const style =
    tone === "accent"
      ? "border-accent/30 bg-accent/10 text-accent"
      : "border-violet/30 bg-violet/10 text-violet";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-pill border px-3 py-1.5 text-xs font-semibold ${style}`}
    >
      <Icon className="h-4 w-4" aria-hidden /> {children}
    </span>
  );
}

// ── Confirm modal ───────────────────────────────────────────────────

function ConfirmModal({
  me,
  onCancel,
  onSubmitted,
}: {
  me: Me;
  onCancel: () => void;
  onSubmitted: () => Promise<void>;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rows = buildReviewRows(me);

  async function send() {
    setSubmitting(true);
    setError(null);
    try {
      await api.submitForVerification();
      await onSubmitted();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submission failed");
      setSubmitting(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-card border border-line-soft bg-ink-soft shadow-card overflow-hidden flex flex-col max-h-[90vh]"
      >
        <div className="flex items-start gap-3 p-5 border-b border-line-soft">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent/15 text-accent">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold text-paper">
              Send profile for verification?
            </h2>
            <p className="mt-0.5 text-xs text-paper-muted leading-relaxed">
              Cor1x admins will review the details below. You can&apos;t edit
              them while under review — fix anything that looks wrong first.
            </p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            aria-label="Close"
            className="rounded-full p-1.5 text-paper-muted hover:bg-ink-elevated hover:text-paper transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 overflow-y-auto">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-paper-muted mb-3">
            What admins will see
          </p>
          <ul className="space-y-2.5">
            {rows.map((r) => (
              <li
                key={r.label}
                className="flex items-start gap-2.5 rounded-field border border-line-soft bg-ink px-3 py-2"
              >
                <CheckCircle2
                  className="mt-0.5 h-4 w-4 shrink-0 text-accent"
                  aria-hidden
                />
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-paper-muted">
                    {r.label}
                  </p>
                  <p className="text-sm text-paper break-words">{r.value}</p>
                </div>
              </li>
            ))}
          </ul>

          {me.verification.status === "rejected" &&
            me.verification.rejectedReason && (
              <div className="mt-4 rounded-field border border-amber-400/30 bg-amber-400/5 p-3 flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" aria-hidden />
                <div>
                  <p className="text-xs font-semibold text-amber-400 mb-0.5">
                    Previous rejection
                  </p>
                  <p className="text-xs text-paper leading-relaxed">
                    {me.verification.rejectedReason}
                  </p>
                </div>
              </div>
            )}

          {error && (
            <div className="mt-4 rounded-field border border-danger/40 bg-danger/10 p-3 text-xs text-danger">
              {error}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-line-soft">
          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            className="rounded-field border border-line-soft bg-transparent px-3 py-2 text-xs font-semibold text-paper-muted hover:text-paper transition disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={send}
            disabled={submitting}
            className="inline-flex items-center gap-1.5 rounded-field bg-accent px-4 py-2 text-xs font-semibold text-accent-fg shadow-cta hover:bg-accent-hover transition disabled:opacity-50"
          >
            {submitting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
            ) : (
              <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            )}
            Confirm &amp; send
          </button>
        </div>
      </div>
    </div>
  );
}

// Flatten the Me object into a list of {label, value} pairs covering the
// seven mandatory fields in the same order the user sees them on screen.
function buildReviewRows(me: Me): { label: string; value: string }[] {
  const prim = me.primary;
  const biz = me.business;
  const get = (val: string | string[] | null | undefined): string => {
    if (val == null) return "—";
    if (Array.isArray(val)) return val.length ? val.join(", ") : "—";
    return val || "—";
  };
  return [
    { label: "Full name", value: get(prim.fullName) },
    { label: "Position / role", value: get(prim.position) },
    { label: "Phone", value: get(prim.phone) },
    { label: "Legal company name", value: get(biz.legalName || me.businessName) },
    { label: "Industry", value: get(biz.industry) },
    { label: "Operating countries", value: get(biz.operatingCountries) },
    { label: "Trade position", value: get(biz.tradePosition) },
  ];
}
