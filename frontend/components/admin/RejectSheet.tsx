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
  "Legal company name doesn't match what we can verify online.",
  "Phone number looks personal — please provide a business line.",
  "Operating countries list is empty or clearly incorrect.",
  "Position / role is missing or appears not to be a decision-making title.",
  "Industry mismatch with the trade position you selected.",
] as const;

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
  onSubmit,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  quickReasons?: ReadonlyArray<string>;
  submitLabel?: string;
  onSubmit: (reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
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
      setError(null);
      setBusy(false);
    }
  }, [open]);

  const trimmed = reason.trim();

  const submit = async () => {
    if (!trimmed) {
      setError("Write a reason. They'll see it as written.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onSubmit(trimmed);
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
          <HoldButton tone="danger" icon="close" onCommit={submit} loading={busy} disabled={!trimmed}>
            {submitLabel}
          </HoldButton>
        </>
      }
    >
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
