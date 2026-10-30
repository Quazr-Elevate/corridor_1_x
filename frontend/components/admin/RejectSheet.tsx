"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { errorMessage } from "@/lib/adminApi";
import { Button } from "@/components/ui/Button";
import { HoldButton } from "@/components/ui/Controls";
import { Textarea } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";

export const REJECT_MAX = 500;

export const DOC_REJECT_REASONS = [
  "Image is blurry — please re-upload a clearer scan.",
  "Document is expired. Upload a current version.",
  "Wrong document type for the chosen certificate.",
  "Business name on the document doesn't match your profile.",
  "Only part of the document is visible — upload the full page.",
] as const;

export const USER_REJECT_REASONS = [
  "Company name doesn't match the registration documents.",
  "Registered address doesn't match the GST / trade licence records.",
  "A registration number is invalid or belongs to another business.",
  "A document is blurry, expired or only partly visible — upload a clear, current copy.",
  "Documents are for a different country than the one on your profile.",
] as const;

export interface RejectItem {
  key: string;
  label: string;
  /** Small grey line under the label (e.g. "Document · In review"). */
  sub?: string;
}

/**
 * Reject with a reason. The person sees the reason verbatim, so it is
 * required (500 characters max). Hold to commit — no second "are you sure?".
 * `onSubmit` should throw on failure; the message is shown in the sheet.
 */
export function RejectSheet({
  open,
  onClose,
  title,
  description,
  quickReasons = [],
  submitLabel = "Reject",
  items,
  onSubmit,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  quickReasons?: ReadonlyArray<string>;
  submitLabel?: string;
  /** When given, the admin ticks what failed (at least one). */
  items?: ReadonlyArray<RejectItem>;
  onSubmit: (reason: string, failedItems: string[]) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Sheet re-runs its focus effect when onClose changes identity — keep it stable.
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const busyRef = useRef(false);
  busyRef.current = busy;
  const close = useCallback(() => {
    if (!busyRef.current) closeRef.current();
  }, []);

  useEffect(() => {
    if (!open) {
      setReason("");
      setPicked([]);
      setError(null);
      setBusy(false);
    }
  }, [open]);

  const trimmed = reason.trim();

  const submit = async () => {
    if (items?.length && !picked.length) {
      setError("Tick at least one item to fix.");
      return;
    }
    if (!trimmed) {
      setError("Write a reason. They'll see it as written.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onSubmit(trimmed, picked);
      setBusy(false);
      closeRef.current();
    } catch (e) {
      setError(errorMessage(e, "Reject failed. Try again."));
      setBusy(false);
    }
  };

  return (
    <Sheet
      open={open}
      onClose={close}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="quiet" onClick={close} disabled={busy}>
            Cancel
          </Button>
          <HoldButton
            tone="danger"
            icon="close"
            onCommit={submit}
            loading={busy}
            disabled={!trimmed || Boolean(items?.length && !picked.length)}
          >
            {submitLabel}
          </HoldButton>
        </>
      }
    >
      {items?.length ? (
        <fieldset className="mb-5">
          <legend className="t-label text-fg-3">What needs fixing</legend>
          <div className="mt-2.5 grid gap-2 sm:grid-cols-2">
            {items.map((it) => {
              const on = picked.includes(it.key);
              return (
                <button
                  key={it.key}
                  type="button"
                  role="checkbox"
                  aria-checked={on}
                  onClick={() => {
                    setPicked((xs) => (on ? xs.filter((x) => x !== it.key) : [...xs, it.key]));
                    setError(null);
                  }}
                  className={cn(
                    "flex items-start gap-2.5 rounded-[14px] px-3 py-2.5 text-left text-[13.5px] transition-[box-shadow,color] duration-300 ease-expo",
                    on ? "bg-danger-soft text-danger" : "relief-sm text-fg-2 hover:text-fg",
                  )}
                >
                  <span
                    aria-hidden="true"
                    className={cn(
                      "mt-0.5 grid size-4 shrink-0 place-items-center rounded-[5px] text-[10px] font-bold",
                      on ? "bg-danger text-cream" : "well",
                    )}
                  >
                    {on ? "✓" : ""}
                  </span>
                  <span className="min-w-0">
                    <span className="block font-medium">{it.label}</span>
                    {it.sub ? <span className="block text-[12px] opacity-70">{it.sub}</span> : null}
                  </span>
                </button>
              );
            })}
          </div>
        </fieldset>
      ) : null}
      <Textarea
        label="Reason"
        required
        counter
        maxLength={REJECT_MAX}
        value={reason}
        onChange={(e) => {
          setReason(e.target.value);
          if (error) setError(null);
        }}
        placeholder="What should they fix?"
        error={error}
        hint="Shown to them verbatim on their next sign-in."
      />
      {quickReasons.length ? (
        <div className="mt-5">
          <p className="t-label text-fg-3">Quick picks</p>
          <div className="mt-2.5 flex flex-wrap gap-2">
            {quickReasons.map((q) => {
              const on = reason === q;
              return (
                <button
                  key={q}
                  type="button"
                  aria-pressed={on}
                  onClick={() => {
                    setReason(q);
                    setError(null);
                  }}
                  className={cn(
                    "rounded-[14px] px-3 py-2 text-left text-[13px] leading-snug transition-[box-shadow,color] duration-300 ease-expo",
                    on ? "solid" : "relief-sm text-fg-2 hover:text-fg",
                  )}
                >
                  {q}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
    </Sheet>
  );
}
