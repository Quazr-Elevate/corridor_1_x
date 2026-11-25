"use client";

import type { ReviewEvent } from "@/lib/adminApi";
import { cn } from "@/lib/cn";
import { Icon, type IconName } from "@/components/ui/Icon";
import { fmtAgo, fmtDateTime } from "@/components/admin/format";

/**
 * Who decided what on a business's KYB, and why — read from the audit trail
 * (`reviewHistory` / `lastReview`). Several admins review, so every decision
 * names its reviewer; decisions made before named admin accounts carry only
 * an email.
 */

const KIND: Record<ReviewEvent["kind"], { verb: string; icon: IconName; tone: string }> = {
  business_approved: { verb: "Approved", icon: "shield", tone: "text-accent" },
  business_rejected: { verb: "Rejected", icon: "alert", tone: "text-danger" },
  document_approved: { verb: "Approved document", icon: "check", tone: "text-accent" },
  document_rejected: { verb: "Rejected document", icon: "close", tone: "text-danger" },
};

export function reviewerLabel(e: ReviewEvent): string {
  return e.reviewerName || e.reviewerEmail;
}

/** Directory cell: "Approved · Riya Reviewer · 3h ago", or a dash. */
export function LastReview({ event, className }: { event: ReviewEvent | null; className?: string }) {
  if (!event) return <span className={cn("t-sub text-fg-3", className)}>Not reviewed</span>;
  const k = KIND[event.kind];
  return (
    <span className={cn("block min-w-0", className)} title={`${k.verb} by ${event.reviewerEmail} · ${fmtDateTime(event.at)}`}>
      <span className={cn("t-sub flex items-center gap-1.5 font-medium", k.tone)}>
        <Icon name={k.icon} size={13} className="shrink-0" />
        {k.verb}
      </span>
      <span className="t-foot block truncate text-fg-3">
        {reviewerLabel(event)} · {fmtAgo(event.at)}
      </span>
    </span>
  );
}

/** The full trail, newest first. */
export function ReviewTrail({ events, className }: { events: ReviewEvent[]; className?: string }) {
  if (!events.length) {
    return <p className={cn("t-sub text-fg-3", className)}>No KYB decision yet.</p>;
  }
  return (
    <ol className={cn("relative space-y-5", className)}>
      {events.map((e, i) => {
        const k = KIND[e.kind];
        return (
          <li key={`${e.at}-${i}`} className="relative pl-7">
            <span
              aria-hidden="true"
              className={cn("absolute left-0 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-white/[0.06]", k.tone)}
            >
              <Icon name={k.icon} size={12} />
            </span>
            <p className="t-sub text-fg">
              <span className={cn("font-medium", k.tone)}>{k.verb}</span>
              {e.document ? <span className="text-fg-2"> · {e.document}</span> : null}
            </p>
            <p className="t-foot mt-0.5 text-fg-3">
              <span className="text-fg-2" title={e.reviewerEmail}>
                {reviewerLabel(e)}
              </span>{" "}
              · <time dateTime={e.at}>{fmtDateTime(e.at)}</time>
            </p>
            {e.reason ? <p className="t-sub mt-1.5 whitespace-pre-wrap text-fg-2">“{e.reason}”</p> : null}
            {e.items.length ? (
              <p className="t-foot mt-1 text-fg-3">
                Flagged: <span className="text-fg-2">{e.items.join(", ")}</span>
              </p>
            ) : null}
            {e.documentsApproved ? (
              <p className="t-foot mt-1 text-fg-3">
                With {e.documentsApproved} required document{e.documentsApproved === 1 ? "" : "s"}
              </p>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
