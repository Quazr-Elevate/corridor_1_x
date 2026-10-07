"use client";

import { CheckCircle2 } from "lucide-react";
import { useMe } from "@/lib/useMe";
import { MANDATORY_KEYS } from "@/lib/verification";

/**
 * Small inline marker shown next to a form label to tell the user that
 * this field is one of the seven mandatory inputs for the Verified
 * badge — and whether their *saved* value satisfies it yet.
 *
 * Driven by ``useMe().verification.missing``, so it updates after every
 * successful save without any per-field tracking. Unsaved local edits
 * do not change the state; that's intentional — the user cares whether
 * the server-side profile is complete.
 *
 * ``fieldKey`` is the camelCase key from ``MANDATORY_FIELDS``.
 */
export function VerificationBadge({ fieldKey }: { fieldKey: string }) {
  const { me } = useMe();
  if (!MANDATORY_KEYS.has(fieldKey)) return null;

  const missing = me?.verification?.missing ?? [];
  const filled = me != null && !missing.includes(fieldKey);

  if (filled) {
    return (
      <span className="ml-2 inline-flex items-center gap-1 rounded-pill border border-accent/30 bg-accent/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-widest text-accent">
        <CheckCircle2 className="h-2.5 w-2.5" aria-hidden />
        Filled
      </span>
    );
  }
  return (
    <span
      title="Required to earn the Verified badge"
      className="ml-2 inline-flex items-center gap-1 rounded-pill border border-amber-400/30 bg-amber-400/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-widest text-amber-400"
    >
      Verify-required
    </span>
  );
}
