"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useMe } from "@/lib/useMe";
import { focusField } from "@/lib/useFocusField";
import {
  canSubmit,
  fieldByKey,
  formatDay,
  statusMeta,
  verificationCounts,
  type MandatoryField,
} from "@/lib/verification";
import { api } from "@/lib/api";
import { MEDIA } from "@/lib/media";
import { Photo } from "@/components/art/Photo";
import { Chip, CountPill } from "@/components/ui/Chip";
import { HoldButton, Progress } from "@/components/ui/Controls";
import { Icon } from "@/components/ui/Icon";
import { Notice } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";

/**
 * Verification panel on the Passport page — the inspector photograph on
 * top (Corridor ops checks every passport by hand), then the state.
 * Driven by `me.verification`:
 *   • not sent      — progress x/7, the fields still missing, hold to send
 *   • in review     — amber, since when; editing stays open
 *   • needs changes — ops' reason, hold to resubmit
 *   • verified      — the badge and when it was issued
 *
 * `dirty` blocks sending while the page holds unsaved edits — the review
 * reads what's saved, not what's on screen.
 */
export function SendForVerificationBar({ dirty, className }: { dirty: boolean; className?: string }) {
  const { me, refetch } = useMe();
  const toast = useToast();
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!me) return null;
  const v = me.verification;
  const { filled, total } = verificationCounts(v);
  const meta = statusMeta(v.status);
  const missing = v.missing.map(fieldByKey).filter((f): f is MandatoryField => Boolean(f));
  const submittable = canSubmit(v);

  async function send() {
    setSending(true);
    setError(null);
    try {
      await api.submitForVerification();
      await refetch();
      toast("Sent for verification", "verified");
    } catch (e) {
      const msg =
        e instanceof ApiError && e.status === 429
          ? "Too many attempts. Wait a moment, then hold again."
          : e instanceof Error
            ? e.message
            : "Could not send. Try again.";
      setError(msg);
      toast("Not sent", "frozen");
    } finally {
      setSending(false);
    }
  }

  return (
    <section
      aria-labelledby="verification-title"
      className={cn(
        // Phones and the wide aside: photo on top. Tablets: photo beside.
        "relief overflow-hidden rounded-[30px] sm:grid sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] lg:block",
        className,
      )}
    >
      <div className="relative aspect-[16/7] sm:aspect-auto sm:min-h-[220px] lg:aspect-[16/7] lg:min-h-0">
        <Photo
          media={MEDIA.inspector}
          decorative
          fill
          objectPosition="50% 45%"
          sizes="(min-width: 1024px) 340px, (min-width: 640px) 40vw, 100vw"
          className="rounded-b-[22px] sm:rounded-b-none sm:rounded-r-[22px] lg:rounded-r-none lg:rounded-b-[22px]"
        >
          {/* Ink fade so the cream type keeps its contrast over the photo. */}
          <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-ink/80 via-ink/30 to-transparent" />
          <div className="absolute inset-x-5 bottom-4 flex items-end justify-between gap-3 sm:inset-x-6">
            <div className="min-w-0">
              <h2 id="verification-title" className="t-label text-cream/75">
                Verification
              </h2>
              <p className="t-headline mt-1 text-cream">Reviewed by hand</p>
            </div>
            {/* Over the photo the neutral chip needs its own cream ground. */}
            <Chip
              tone={meta.tone}
              icon={v.status === "pending_verification" ? "clock" : undefined}
              className={meta.tone === "neutral" ? "bg-cream/90 text-ink/75 shadow-none" : undefined}
            >
              {meta.label}
            </Chip>
          </div>
        </Photo>
      </div>

      <div className="p-5 sm:p-6">
        {v.status === "verified" ? (
          <div>
            <p className="t-title3 text-fg">Your passport is verified.</p>
            <p className="t-callout mt-1.5 text-fg-2">
              {v.verifiedAt ? `Approved ${formatDay(v.verifiedAt)}. ` : null}
              Buyers see the badge on every lot you list.
            </p>
          </div>
        ) : v.status === "pending_verification" ? (
          <div>
            <p className="t-title3 text-fg">
              In review{v.submittedAt ? ` since ${formatDay(v.submittedAt)}` : ""}
            </p>
            <p className="t-callout mt-1.5 text-fg-2">
              Corridor ops is checking your file. You&rsquo;ll get the decision by email.
            </p>
            <p className="t-sub mt-3 flex items-start gap-2 text-amber">
              <Icon name="info" size={15} className="mt-px shrink-0" />
              Editing stays open — changes you save now go to ops with your file.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {v.status === "rejected" ? (
              <Notice tone="frozen" title="Needs changes">
                <span className="whitespace-pre-wrap">
                  {v.rejectedReason || "Corridor ops couldn’t approve your passport. Check your details and resubmit."}
                </span>
              </Notice>
            ) : null}

            <div>
              <div className="flex items-center justify-between gap-3">
                <p className="t-headline text-fg">
                  {missing.length ? "Fields for verification" : "All seven fields are in"}
                </p>
                <CountPill>
                  {filled}/{total}
                </CountPill>
              </div>
              <Progress value={filled} max={total} label="Verification fields filled" className="mt-3" />
            </div>

            {missing.length ? (
              <div>
                <p className="t-sub text-fg-3">Still needed</p>
                <ul className="mt-2 flex flex-wrap gap-2">
                  {missing.map((f, i) => (
                    <li key={f.key}>
                      <a
                        href={`#${f.anchor}`}
                        onClick={(e) => {
                          e.preventDefault();
                          focusField(f.anchor);
                        }}
                        className={cn(
                          "inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-[13px] font-medium transition-[box-shadow,color] duration-300 ease-expo",
                          i === 0 ? "bg-amber-soft text-amber" : "relief-sm text-fg-2 hover:text-fg",
                        )}
                      >
                        {i === 0 ? <span className="sr-only">Next: </span> : null}
                        {f.label}
                        {i === 0 ? <Icon name="arrow-right" size={14} /> : null}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="t-callout text-fg-2">
                Hold to send your passport to Corridor ops. You can keep editing while it’s in review.
              </p>
            )}

            <HoldButton
              onCommit={send}
              loading={sending}
              disabled={!submittable || dirty}
              icon="shield"
              className="w-full px-4"
            >
              {v.status === "rejected" ? "Resubmit for verification" : "Send for verification"}
            </HoldButton>
            {dirty && submittable ? (
              <p className="t-sub -mt-1 text-center text-fg-3">Save your changes first.</p>
            ) : null}
            {error ? (
              <p role="alert" className="t-sub flex items-start gap-1.5 text-danger">
                <Icon name="alert" size={14} className="mt-px shrink-0" />
                {error}
              </p>
            ) : null}
          </div>
        )}
      </div>
    </section>
  );
}
