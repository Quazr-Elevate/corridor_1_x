"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, X } from "lucide-react";

interface Props {
  title: string;
  subtitle?: string;
  open: boolean;
  onClose: () => void;
  onSubmit: (reason: string) => Promise<void>;
  // Optional override: document rejection vs user-badge rejection need
  // different quick-pick copy. Omitted → the doc defaults below.
  quickReasons?: readonly string[];
  // Label on the primary action — defaults to "Reject document" to keep
  // the existing doc flow stable.
  submitLabel?: string;
}

const DEFAULT_QUICK_REASONS = [
  "Image is blurry — please re-upload a clearer scan.",
  "Document is expired. Upload a current version.",
  "Wrong document type for the chosen certificate.",
  "Business name on the document doesn't match your profile.",
  "Only part of the document is visible — upload the full page.",
];

export function RejectReasonModal({
  title,
  subtitle,
  open,
  onClose,
  onSubmit,
  quickReasons,
  submitLabel = "Reject document",
}: Props) {
  const picks = quickReasons ?? DEFAULT_QUICK_REASONS;
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (!open) {
      setReason("");
      setError(null);
      setSubmitting(false);
      return;
    }
    const t = setTimeout(() => taRef.current?.focus(), 20);
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(t);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  async function handleSubmit() {
    const trimmed = reason.trim();
    if (!trimmed) {
      setError("A reason is required.");
      return;
    }
    if (trimmed.length > 500) {
      setError("Keep the reason under 500 characters.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(trimmed);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reject failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg rounded-[22px] overflow-hidden"
        style={{
          background: "var(--sp-card)",
          border: "1px solid var(--sp-border)",
        }}
      >
        <div
          className="flex items-start justify-between p-5"
          style={{ borderBottom: "1px solid var(--sp-border)" }}
        >
          <div>
            <h2
              className="text-[16px] font-semibold"
              style={{ color: "var(--sp-text)" }}
            >
              {title}
            </h2>
            {subtitle && (
              <p
                className="mt-1 text-[12px]"
                style={{ color: "var(--sp-text-3)" }}
              >
                {subtitle}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="sp-icon-btn"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div>
            <label
              className="text-[11px] font-bold uppercase tracking-[0.12em]"
              style={{ color: "var(--sp-text-3)" }}
            >
              Reason (shown to the user)
            </label>
            <textarea
              ref={taRef}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={4}
              maxLength={500}
              placeholder="e.g. The GST certificate is expired. Please upload a current one."
              className="mt-2 w-full rounded-field px-3 py-2 text-[13px]"
              style={{
                background: "var(--sp-card-2)",
                color: "var(--sp-text)",
                border: "1px solid var(--sp-border)",
              }}
            />
            <div
              className="mt-1 text-right text-[11px]"
              style={{ color: "var(--sp-text-3)" }}
            >
              {reason.length}/500
            </div>
          </div>

          <div>
            <p
              className="text-[11px] font-bold uppercase tracking-[0.12em] mb-2"
              style={{ color: "var(--sp-text-3)" }}
            >
              Quick picks
            </p>
            <div className="flex flex-wrap gap-2">
              {picks.map((q) => (
                <button
                  type="button"
                  key={q}
                  onClick={() => setReason(q)}
                  className="sp-chip text-left"
                  style={{ fontSize: "11.5px" }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div
              className="rounded-field p-3 text-[12.5px]"
              style={{
                background: "rgba(229,107,111,0.1)",
                color: "var(--sp-error)",
                border: "1px solid rgba(229,107,111,0.3)",
              }}
            >
              {error}
            </div>
          )}
        </div>

        <div
          className="flex items-center justify-end gap-2 p-4"
          style={{ borderTop: "1px solid var(--sp-border)" }}
        >
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="sp-chip"
            style={{ paddingLeft: "0.75rem" }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || !reason.trim()}
            className="inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-[12.5px] font-semibold transition disabled:opacity-50"
            style={{
              background: "var(--sp-error)",
              color: "#fff",
            }}
          >
            {submitting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
            ) : null}
            {submitLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
