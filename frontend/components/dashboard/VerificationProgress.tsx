"use client";

import Link from "next/link";
import { useMemo } from "react";
import {
  ArrowRight,
  BadgeCheck,
  CheckCircle2,
  Clock,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { useMe } from "@/lib/useMe";
import { MANDATORY_FIELDS, fieldByKey, nextStepHref } from "@/lib/verification";

/**
 * Verified-badge progress card shown on /dashboard.
 *
 * Four states, driven entirely by ``me.verification``:
 *
 *   not-started  → 0 fields filled; sales-pitch copy + CTA
 *   in-progress  → 1..6 fields filled; list of what's missing + CTA
 *   pending      → all 7 filled, admin reviewing; a quiet "under review"
 *   rejected     → admin rejected; shows the reason + "Fix profile" CTA
 *   verified     → admin approved; collapses to a thin ribbon
 *
 * The component is self-contained — the rejected modal that pops over
 * /dashboard on first visit is a separate component, this card is the
 * persistent status bar.
 */
export function VerificationProgress() {
  const { me, loading } = useMe();

  const filled = useMemo(() => {
    if (!me) return 0;
    return MANDATORY_FIELDS.length - me.verification.missing.length;
  }, [me]);

  if (loading || !me) return null;
  const v = me.verification;
  const total = v.mandatoryTotal || MANDATORY_FIELDS.length;

  // Verified — a thin ribbon so the card doesn't eat vertical space once
  // the user is past the funnel.
  if (v.status === "verified") {
    return (
      <div className="rounded-card border border-accent/30 bg-accent/10 px-4 py-2.5 flex items-center gap-2.5">
        <BadgeCheck className="h-4 w-4 text-accent" aria-hidden />
        <p className="text-xs text-paper">
          <span className="font-semibold text-accent">Verified</span>
          {v.verifiedAt && (
            <span className="text-paper-muted">
              {" "}
              · approved {formatDate(v.verifiedAt)}
            </span>
          )}
        </p>
      </div>
    );
  }

  // Pending admin review.
  if (v.status === "pending_verification") {
    return (
      <StateCard
        tone="pending"
        icon={Clock}
        title="Under review"
        body="Our team is checking your profile. Verification usually completes within 24 hours — we'll notify you by email."
        footnote={
          v.submittedAt ? `Submitted ${formatDate(v.submittedAt)}` : null
        }
      />
    );
  }

  // Rejected — the modal handles the first-time surprise, this bar is
  // the always-visible reminder until they resubmit.
  if (v.status === "rejected") {
    return (
      <StateCard
        tone="danger"
        icon={ShieldAlert}
        title="Verification needs attention"
        body={
          v.rejectedReason ||
          "Our team couldn't approve your profile. Open My Account and update the flagged fields."
        }
        cta={{ label: "Fix profile", href: "/dashboard/account?tab=primary" }}
      />
    );
  }

  // Active or earlier — not yet in the queue. Three sub-states:
  // 0 filled, some filled, all 7 filled but not yet submitted.
  if (filled === 0) {
    return (
      <StateCard
        tone="accent"
        icon={ShieldCheck}
        title="Get your Verified badge"
        body={`Fill ${total} profile fields and send them to Cor1x admins for review. Verified sellers rank higher in search and get more buyer messages.`}
        progress={{ filled: 0, total }}
        cta={{ label: "Start verification", href: nextStepHref(v.missing) }}
      />
    );
  }

  // All seven filled, submission pending the user's click. (The
  // rejected status is already handled above with its own card, so by
  // this point status is active / email_verified / signed_up.)
  if (v.missing.length === 0) {
    return (
      <StateCard
        tone="accent"
        icon={ShieldCheck}
        title="Ready to submit"
        body="All mandatory fields are filled. Open My Account and hit “Send for verification” to put your profile in the admin queue."
        progress={{ filled, total }}
        cta={{ label: "Review & send", href: "/dashboard/account?tab=primary" }}
      />
    );
  }

  const missingLabels = v.missing
    .map((k) => fieldByKey(k)?.label)
    .filter((label): label is string => Boolean(label));

  return (
    <StateCard
      tone="accent"
      icon={ShieldCheck}
      title="Almost there"
      body={`Missing: ${missingLabels.join(", ")}.`}
      progress={{ filled, total }}
      cta={{ label: "Finish", href: nextStepHref(v.missing) }}
    />
  );
}

// ── Shared card shell ────────────────────────────────────────────────

type Tone = "accent" | "pending" | "danger";

const TONE_STYLES: Record<Tone, { border: string; bg: string; icon: string }> = {
  accent: {
    border: "border-accent/30",
    bg: "bg-accent/5",
    icon: "bg-accent/15 text-accent",
  },
  pending: {
    border: "border-violet/30",
    bg: "bg-violet/5",
    icon: "bg-violet/15 text-violet",
  },
  danger: {
    border: "border-danger/40",
    bg: "bg-danger/5",
    icon: "bg-danger/15 text-danger",
  },
};

function StateCard({
  tone,
  icon: Icon,
  title,
  body,
  cta,
  progress,
  footnote,
}: {
  tone: Tone;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  title: string;
  body: string;
  cta?: { label: string; href: string };
  progress?: { filled: number; total: number };
  footnote?: string | null;
}) {
  const s = TONE_STYLES[tone];
  const pct = progress ? Math.round((progress.filled / progress.total) * 100) : 0;
  return (
    <div
      className={`rounded-card border ${s.border} ${s.bg} p-5 flex items-start gap-4`}
    >
      <div
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-field ${s.icon}`}
      >
        <Icon className="h-5 w-5" aria-hidden />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <h2 className="text-sm font-semibold text-paper">{title}</h2>
          {progress && (
            <span className="text-[11px] font-semibold text-paper-muted">
              {progress.filled} / {progress.total} filled
            </span>
          )}
        </div>

        {progress && (
          <div className="mt-2 h-1.5 w-full rounded-full bg-ink">
            <div
              className="h-1.5 rounded-full bg-accent transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
        )}

        <p className="mt-2 text-xs text-paper leading-relaxed">{body}</p>

        {footnote && (
          <p className="mt-2 text-[11px] text-paper-muted/80">{footnote}</p>
        )}

        {cta && (
          <Link
            href={cta.href}
            className="mt-3 inline-flex items-center gap-1.5 rounded-field bg-accent px-3.5 py-1.5 text-xs font-semibold text-accent-fg shadow-cta hover:bg-accent-hover transition"
          >
            {cta.label}
            <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          </Link>
        )}
      </div>
    </div>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

// Keep this import in the public API so VerificationProgress can be
// swapped for a bare completeness check elsewhere without re-walking the
// catalogue.
export { CheckCircle2 };
