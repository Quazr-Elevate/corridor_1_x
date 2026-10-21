"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type DragEvent, type SetStateAction } from "react";
import { api, ApiError, assetUrl, type VerificationDoc } from "@/lib/api";
import { CERTIFICATION_CATALOGUE } from "@/lib/certifications";
import { cn } from "@/lib/cn";
import { formatDay } from "@/lib/verification";
import { Button, IconButton } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { HoldButton } from "@/components/ui/Controls";
import { FieldShell } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { Sheet } from "@/components/ui/Sheet";
import { Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { Combobox } from "./Combobox";

const MAX_MB = 10;
const ACCEPT = "application/pdf,image/jpeg,image/png,image/webp,.pdf,.jpg,.jpeg,.png,.webp";
const ACCEPTED_MIME = new Set(["application/pdf", "image/jpeg", "image/png", "image/webp"]);

function errorText(e: unknown, fallback: string): string {
  if (e instanceof ApiError && e.status === 429) return "Too many uploads. Wait a moment and try again.";
  return e instanceof Error ? e.message : fallback;
}

/** Client-side check mirroring the API: PDF/JPG/PNG/WEBP, ≤ 10 MB. */
function fileProblem(file: File): string | null {
  const extOk = /\.(pdf|jpe?g|png|webp)$/i.test(file.name);
  if (!ACCEPTED_MIME.has(file.type) && !extOk) return "Only PDF, JPG, PNG or WEBP files.";
  if (file.size > MAX_MB * 1024 * 1024) return `${file.name} is larger than ${MAX_MB} MB.`;
  if (file.size === 0) return "That file is empty.";
  return null;
}

function fileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── Data hook — the page shares this with the Passport card counts ─────

export interface VerificationDocsState {
  docs: VerificationDoc[];
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  setDocs: Dispatch<SetStateAction<VerificationDoc[]>>;
}

export function useVerificationDocs(): VerificationDocsState {
  const [docs, setDocs] = useState<VerificationDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    try {
      setDocs(await api.listVerificationDocs());
    } catch (e) {
      setError(errorText(e, "Could not load your documents."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { docs, loading, error, reload, setDocs };
}

// ── Block ──────────────────────────────────────────────────────────────

export function CertificationsBlock({ state }: { state: VerificationDocsState }) {
  const { docs, loading, error, reload, setDocs } = state;
  const toast = useToast();
  const [deleting, setDeleting] = useState<VerificationDoc | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const onUploaded = (doc: VerificationDoc) => setDocs((d) => [doc, ...d.filter((x) => x.id !== doc.id)]);

  const onReplaced = (oldId: string, doc: VerificationDoc) =>
    setDocs((d) => [doc, ...d.filter((x) => x.id !== oldId && x.id !== doc.id)]);

  async function confirmDelete() {
    if (!deleting) return;
    setDeleteError(null);
    try {
      await api.deleteVerificationDoc(deleting.id);
      setDocs((d) => d.filter((x) => x.id !== deleting.id));
      setDeleting(null);
      toast("Document deleted");
    } catch (e) {
      setDeleteError(errorText(e, "Could not delete. Try again."));
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-end justify-between gap-3">
          <h3 className="t-headline text-fg">On file</h3>
          {!loading && docs.length ? (
            <span className="t-sub text-fg-3">
              {docs.filter((d) => d.status === "approved").length} of {docs.length} approved
            </span>
          ) : null}
        </div>

        {loading ? (
          <div className="mt-4 grid gap-4 sm:grid-cols-2" aria-busy="true" aria-label="Loading documents">
            <Skeleton className="h-[188px] rounded-[26px]" />
            <Skeleton className="h-[188px] rounded-[26px]" />
          </div>
        ) : error ? (
          <div className="mt-3">
            <Notice
              tone="frozen"
              title="Couldn’t load your documents"
              action={
                <Button variant="secondary" size="sm" icon="refund" onClick={() => void reload()}>
                  Try again
                </Button>
              }
            >
              {error}
            </Notice>
          </div>
        ) : docs.length === 0 ? (
          <div className="well mt-4 flex flex-col items-center rounded-[26px] px-6 py-8 text-center">
            <span className="grid size-[60px] place-items-center rounded-full border-[2.5px] border-dashed border-fg/25 text-fg-3">
              <Icon name="stamp" size={24} />
            </span>
            <p className="t-headline mt-4 text-fg">No documents yet</p>
            <p className="t-sub mt-1 max-w-sm text-fg-3">
              Optional. GST, IEC, FSSAI or lab certificates — each one becomes a stamp once Corridor ops approves it.
            </p>
          </div>
        ) : (
          <ul className="mt-4 grid gap-4 sm:grid-cols-2">
            {docs.map((d) => (
              <DocRow
                key={d.id}
                doc={d}
                onDelete={() => {
                  setDeleteError(null);
                  setDeleting(d);
                }}
                onReplaced={onReplaced}
              />
            ))}
          </ul>
        )}
      </div>

      {/* "Add a stamp" — dashed, like an empty slot waiting for a seal. */}
      <section
        aria-labelledby="add-document-title"
        className="rounded-[26px] border border-dashed border-fg/20 p-4 sm:p-5"
      >
        <h3 id="add-document-title" className="t-headline flex items-center gap-2 text-fg">
          <Icon name="plus" size={16} className="text-fg-3" />
          Add a document
        </h3>
        <div className="mt-4">
          <UploadPanel onUploaded={onUploaded} />
        </div>
      </section>

      <Sheet
        open={!!deleting}
        onClose={() => setDeleting(null)}
        size="sm"
        title="Delete this document?"
        description={deleting ? `${deleting.certType} · ${deleting.filename}` : undefined}
        footer={
          <>
            <Button variant="quiet" onClick={() => setDeleting(null)}>
              Keep it
            </Button>
            <HoldButton tone="danger" icon="trash" holdMs={900} onCommit={confirmDelete}>
              Delete
            </HoldButton>
          </>
        }
      >
        <p className="t-callout text-fg-2">Corridor ops stops seeing it. This can&rsquo;t be undone.</p>
        {deleteError ? (
          <p role="alert" className="t-sub mt-3 flex items-start gap-1.5 text-danger">
            <Icon name="alert" size={14} className="mt-px shrink-0" />
            {deleteError}
          </p>
        ) : null}
      </Sheet>
    </div>
  );
}

// ── Upload: type picker + well dropzone ────────────────────────────────

function UploadPanel({ onUploaded }: { onUploaded: (doc: VerificationDoc) => void }) {
  const toast = useToast();
  const [certType, setCertType] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const options = useMemo(() => CERTIFICATION_CATALOGUE.map((c) => ({ value: c, label: c })), []);

  const take = (f: File | undefined | null) => {
    if (!f) return;
    const problem = fileProblem(f);
    setError(problem);
    setFile(problem ? null : f);
  };

  const onDrop = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setDragging(false);
    take(e.dataTransfer.files?.[0]);
  };

  async function upload() {
    if (!certType || !file) return;
    setUploading(true);
    setError(null);
    try {
      const doc = await api.uploadVerificationDoc(certType, file);
      onUploaded(doc);
      setCertType(null);
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      toast("Uploaded — in review", "verified");
    } catch (e) {
      setError(errorText(e, "Upload failed. Try again."));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-4">
      {certType ? (
        <FieldShell label="Certificate type">
          <div className="well flex h-12 items-center justify-between gap-3 rounded-field pl-4 pr-1.5">
            <span className="min-w-0 truncate text-[15px] text-fg">{certType}</span>
            <IconButton icon="close" label="Change certificate type" onClick={() => setCertType(null)} className="size-9" />
          </div>
        </FieldShell>
      ) : (
        <Combobox
          id="cert-type"
          label="Certificate type"
          options={options}
          onPick={setCertType}
          allowCustom
          placeholder="Search — GST, FSSAI, phytosanitary…"
          emptyText="No match. Type the name to add it."
        />
      )}

      <FieldShell label="File" htmlFor="cert-file" hint="PDF, JPG, PNG or WEBP · up to 10 MB">
        <label
          htmlFor="cert-file"
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            "well flex min-h-[112px] cursor-pointer flex-col items-center justify-center gap-2 rounded-[20px] px-4 py-5 text-center transition-shadow duration-300 ease-expo",
            "focus-within:shadow-[var(--well),0_0_0_1px_var(--c-fg),0_0_0_4px_rgb(196_216_46/0.35)]",
            dragging && "shadow-[var(--well),0_0_0_1px_var(--c-fg)]",
          )}
        >
          <input
            ref={inputRef}
            id="cert-file"
            type="file"
            accept={ACCEPT}
            className="sr-only"
            onChange={(e) => take(e.target.files?.[0])}
          />
          {file ? (
            <>
              <span className="relief-sm grid size-10 place-items-center rounded-full text-fg-2">
                <Icon name={file.type.startsWith("image/") ? "image" : "doc-check"} size={18} />
              </span>
              <span className="t-headline max-w-full truncate text-fg">{file.name}</span>
              <span className="t-sub text-fg-3">{fileSize(file.size)} · tap to choose another</span>
            </>
          ) : (
            <>
              <span className="relief-sm grid size-10 place-items-center rounded-full text-fg-2">
                <Icon name="upload" size={18} />
              </span>
              <span className="t-callout text-fg">
                <span className="font-medium">Choose a file</span>
                <span className="hidden text-fg-2 sm:inline"> or drop it here</span>
              </span>
            </>
          )}
        </label>
      </FieldShell>

      {error ? (
        <p role="alert" className="t-sub flex items-start gap-1.5 text-danger">
          <Icon name="alert" size={14} className="mt-px shrink-0" />
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center justify-end gap-3">
        {!certType && file ? <span className="t-sub text-fg-3">Pick the certificate type.</span> : null}
        <Button icon="upload" onClick={() => void upload()} disabled={!certType || !file} loading={uploading}>
          Upload
        </Button>
      </div>
    </div>
  );
}

// ── One document ───────────────────────────────────────────────────────

function DocRow({
  doc,
  onDelete,
  onReplaced,
}: {
  doc: VerificationDoc;
  onDelete: () => void;
  onReplaced: (oldId: string, doc: VerificationDoc) => void;
}) {
  const toast = useToast();
  const replaceRef = useRef<HTMLInputElement>(null);
  const [replacing, setReplacing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rejected = doc.status === "rejected";

  async function replace(file: File | undefined) {
    if (!file) return;
    const problem = fileProblem(file);
    if (problem) {
      setError(problem);
      return;
    }
    setReplacing(true);
    setError(null);
    try {
      const fresh = await api.uploadVerificationDoc(doc.certType, file);
      // The replacement is in; drop the rejected copy (best effort).
      await api.deleteVerificationDoc(doc.id).catch(() => undefined);
      onReplaced(doc.id, fresh);
      toast("Replaced — back in review", "verified");
    } catch (e) {
      setError(errorText(e, "Upload failed. Try again."));
    } finally {
      setReplacing(false);
      if (replaceRef.current) replaceRef.current.value = "";
    }
  }

  const approved = doc.status === "approved";
  return (
    <li
      id={`doc-${doc.id}`}
      className={cn(
        // A stamp: relief card, dashed seal (tilted once approved), mono date.
        "relief relative flex min-h-[188px] scroll-mt-32 flex-col rounded-[26px] p-5",
        rejected && "shadow-[var(--relief),inset_0_0_0_1.5px_var(--c-danger)] sm:col-span-2",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <span
          aria-hidden="true"
          className={cn(
            "grid size-[60px] shrink-0 place-items-center rounded-full border-[2.5px] border-dashed",
            approved && "-rotate-12 border-accent text-accent",
            doc.status === "pending" && "border-amber text-amber",
            rejected && "border-danger text-danger",
          )}
        >
          <Icon name={doc.mimeType.startsWith("image/") ? "image" : approved ? "stamp" : "doc-check"} size={22} />
        </span>
        <div className="flex items-center gap-1">
          <DocChip status={doc.status} />
          {doc.status !== "approved" ? (
            <IconButton icon="trash" size="sm" label={`Delete ${doc.certType}`} onClick={onDelete} className="-mr-1.5 shrink-0" />
          ) : null}
        </div>
      </div>
      <p className="t-headline mt-5 break-words text-fg">{doc.certType}</p>
      <a
        href={assetUrl(doc.url)}
        target="_blank"
        rel="noreferrer"
        className="t-sub mt-0.5 inline-flex max-w-full items-center gap-1 text-fg-3 underline-offset-4 hover:text-fg hover:underline"
      >
        <span className="truncate">{doc.filename}</span>
        <span className="shrink-0">· {fileSize(doc.sizeBytes)}</span>
        <Icon name="external" size={13} className="shrink-0" />
        <span className="sr-only">(opens in a new tab)</span>
      </a>
      <p className="t-code mt-auto pt-4 text-fg-3">
        {approved && doc.reviewedAt ? `Approved ${formatDay(doc.reviewedAt)}` : `Uploaded ${formatDay(doc.uploadedAt)}`}
      </p>

      {rejected ? (
        <div className="mt-4 flex flex-col gap-3 rounded-[16px] bg-danger-soft p-3.5 text-danger">
          <div className="min-w-0">
            <p className="t-label">Ops note</p>
            <p className="t-callout mt-1 whitespace-pre-wrap">{doc.rejectionReason || "Rejected without a note."}</p>
          </div>
          <input
            ref={replaceRef}
            type="file"
            accept={ACCEPT}
            className="sr-only"
            tabIndex={-1}
            aria-hidden="true"
            onChange={(e) => void replace(e.target.files?.[0])}
          />
          <Button
            variant="secondary"
            size="sm"
            icon="upload"
            loading={replacing}
            onClick={() => replaceRef.current?.click()}
            className="shrink-0 self-start"
          >
            Replace
          </Button>
        </div>
      ) : null}
      {error ? (
        <p role="alert" className="t-sub mt-3 flex items-start gap-1.5 text-danger">
          <Icon name="alert" size={14} className="mt-px shrink-0" />
          {error}
        </p>
      ) : null}
    </li>
  );
}

function DocChip({ status }: { status: VerificationDoc["status"] }) {
  if (status === "approved") return <Chip tone="verified">Approved</Chip>;
  if (status === "rejected") return <Chip tone="frozen">Rejected</Chip>;
  return (
    <Chip tone="move" icon="clock">
      In review
    </Chip>
  );
}
