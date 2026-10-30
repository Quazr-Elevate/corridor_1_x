"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, assetUrl, type DocRequirementsResponse, type DocSlot, type VerificationDoc } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Button, LinkButton } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Icon } from "@/components/ui/Icon";
import { Sheet } from "@/components/ui/Sheet";
import { Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";

const MAX_MB = 10;
const ACCEPT = "application/pdf,image/jpeg,image/png,image/webp,.pdf,.jpg,.jpeg,.png,.webp";
const ACCEPTED_MIME = new Set(["application/pdf", "image/jpeg", "image/png", "image/webp"]);

function errorText(e: unknown, fallback: string): string {
  if (e instanceof ApiError && e.status === 429) return "Too many uploads. Wait a moment and try again.";
  return e instanceof Error ? e.message : fallback;
}

function fileProblem(file: File): string | null {
  const extOk = /\.(pdf|jpe?g|png|webp)$/i.test(file.name);
  if (!ACCEPTED_MIME.has(file.type) && !extOk) return "Only PDF, JPG, PNG or WEBP files.";
  if (file.size > MAX_MB * 1024 * 1024) return `${file.name} is larger than ${MAX_MB} MB.`;
  if (file.size === 0) return "That file is empty.";
  return null;
}

function sizeText(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Required documents — country-driven. Pulls the catalog slots for the
 * signed-in business's home country from the backend and renders one row
 * per slot with its upload state. "Replace" is allowed at any status
 * (per spec); the server deletes the old row's file before saving the new.
 */
export function RequiredDocsBlock({ onChange }: { onChange?: () => void }) {
  const toast = useToast();
  const [data, setData] = useState<DocRequirementsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<VerificationDoc | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    try {
      setData(await api.listDocRequirements());
    } catch (e) {
      setError(errorText(e, "Could not load required documents."));
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const notifyUpload = useCallback(
    async (fresh: VerificationDoc) => {
      toast(`Uploaded ${fresh.filename}.`, "verified");
      await reload();
      onChange?.();
    },
    [reload, toast, onChange],
  );

  if (error) return <Notice tone="frozen">{error}</Notice>;
  if (!data)
    return (
      <div className="space-y-3" aria-busy="true">
        {Array.from({ length: 2 }).map((_, i) => (
          <Skeleton key={i} className="h-20" />
        ))}
      </div>
    );

  if (data.required.length === 0 && data.optional.length === 0) {
    return (
      <p className="t-sub text-fg-3">
        No country-specific documents are currently requested for {data.countryCode}. Add any certification you have below —
        each one is reviewed on its own.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {data.required.length > 0 ? (
        <div>
          <SectionHeading
            label="Required"
            count={data.required.filter((s) => s.upload && s.upload.status !== "rejected").length}
            total={data.required.length}
          />
          <ul className="mt-3 space-y-3">
            {data.required.map((slot) => (
              <SlotRow key={slot.requirementId} slot={slot} onUploaded={notifyUpload} onPreview={setPreview} />
            ))}
          </ul>
        </div>
      ) : null}

      {data.optional.length > 0 ? (
        <div>
          <SectionHeading
            label="Optional"
            count={data.optional.filter((s) => s.upload && s.upload.status !== "rejected").length}
            total={data.optional.length}
          />
          <ul className="mt-3 space-y-3">
            {data.optional.map((slot) => (
              <SlotRow key={slot.requirementId} slot={slot} onUploaded={notifyUpload} onPreview={setPreview} />
            ))}
          </ul>
        </div>
      ) : null}

      <DocPreviewSheet doc={preview} onClose={() => setPreview(null)} />
    </div>
  );
}

/* ─────────────────────────────── Preview ─────────────────────────── */

function DocPreviewSheet({ doc, onClose }: { doc: VerificationDoc | null; onClose: () => void }) {
  const open = doc !== null;
  const isImage = !!doc && doc.mimeType.startsWith("image/");
  const isPdf = !!doc && doc.mimeType === "application/pdf";
  const src = doc ? assetUrl(doc.url) : "";
  return (
    <Sheet
      open={open}
      onClose={onClose}
      size="lg"
      title={doc?.filename ?? "Document"}
      description={doc ? `${doc.mimeType} · ${Math.round(doc.sizeBytes / 1024)} KB` : undefined}
      footer={
        doc ? (
          <LinkButton href={src} variant="quiet" iconRight="arrow-up-right" target="_blank" rel="noopener noreferrer">
            Open in new tab
          </LinkButton>
        ) : null
      }
    >
      {doc ? (
        <div className="flex max-h-[70vh] items-center justify-center overflow-auto rounded-[22px] bg-black/5 p-2">
          {isImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={src} alt={doc.filename} className="max-h-[66vh] w-auto rounded-[14px] object-contain" />
          ) : isPdf ? (
            <iframe
              src={src}
              title={doc.filename}
              className="h-[70vh] w-full rounded-[14px] bg-white"
            />
          ) : (
            <div className="p-6 text-center">
              <p className="t-callout text-fg">Preview isn't available for this file type.</p>
              <p className="t-sub mt-1 text-fg-3">Use "Open in new tab" to download it.</p>
            </div>
          )}
        </div>
      ) : null}
    </Sheet>
  );
}

function SectionHeading({ label, count, total }: { label: string; count: number; total: number }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <h3 className="t-label text-fg-3">{label}</h3>
      <span className="t-code tabular text-fg-3">
        {count}/{total} filled
      </span>
    </div>
  );
}

function SlotRow({
  slot,
  onUploaded,
  onPreview,
}: {
  slot: DocSlot;
  onUploaded: (doc: VerificationDoc) => Promise<void>;
  onPreview: (doc: VerificationDoc) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  async function handleFile(file: File | null) {
    if (!file || !slot.requirementId) return;
    const problem = fileProblem(file);
    if (problem) {
      setLocalError(problem);
      return;
    }
    setLocalError(null);
    setUploading(true);
    try {
      const fresh = await api.uploadVerificationDoc(slot.slug ?? slot.displayName, file, {
        requiredDocTypeId: slot.requirementId,
      });
      await onUploaded(fresh);
    } catch (e) {
      setLocalError(errorText(e, "Upload failed."));
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  const u = slot.upload;
  const status = u ? statusChip(u.status) : <Chip tone="frozen">Not uploaded</Chip>;

  return (
    <li className={cn("relief rounded-[20px] p-4 sm:p-5", slot.isMandatory && !u ? "ring-1 ring-amber-500/40" : null)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="t-callout text-fg">{slot.displayName}</p>
            {status}
          </div>
          {slot.description ? <p className="t-sub mt-1 text-fg-3">{slot.description}</p> : null}
          {slot.helpUrl ? (
            <a
              href={/^https?:\/\//i.test(slot.helpUrl) ? slot.helpUrl : `https://${slot.helpUrl}`}
              target="_blank"
              rel="noopener noreferrer"
              className="t-sub mt-1 inline-flex items-center gap-1 text-fg-2 underline decoration-fg/30 underline-offset-4 hover:text-fg"
            >
              <Icon name="arrow-up-right" size={14} /> How to find this
            </a>
          ) : null}
          {u ? (
            <p className="t-code mt-2 text-fg-3">
              {u.filename} · {sizeText(u.sizeBytes)}
              {u.status === "rejected" && u.rejectionReason ? ` · ${u.rejectionReason}` : null}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="sr-only"
            onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
          />
          <Button
            variant={u ? "quiet" : "primary"}
            icon={u ? "refund" : "upload"}
            onClick={() => inputRef.current?.click()}
            loading={uploading}
            size="sm"
          >
            {u ? "Replace" : "Upload"}
          </Button>
          {u ? (
            <button
              type="button"
              onClick={() => onPreview(u)}
              className="t-sub inline-flex items-center gap-1 rounded-sm text-fg-2 underline decoration-fg/30 underline-offset-4 hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--focus)]"
            >
              <Icon name="eye" size={14} /> View
            </button>
          ) : null}
        </div>
      </div>
      {localError ? <Notice tone="frozen" className="mt-3">{localError}</Notice> : null}
    </li>
  );
}

function statusChip(status: VerificationDoc["status"]) {
  if (status === "approved") return <Chip tone="verified">Approved</Chip>;
  if (status === "rejected") return <Chip tone="frozen">Rejected — replace it</Chip>;
  return <Chip tone="move">In review</Chip>;
}
