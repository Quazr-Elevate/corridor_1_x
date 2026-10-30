"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, assetUrl, type KybDocType, type VerificationDoc } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatDay } from "@/lib/verification";
import { Button, IconButton } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Input, Select } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { Sheet } from "@/components/ui/Sheet";
import { Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { useReviewConfirm } from "./ReviewConfirm";

const OTHER = "__other__";
const MAX_MB = 10;
const ACCEPT = "application/pdf,image/jpeg,image/png,image/webp,.pdf,.jpg,.jpeg,.png,.webp";

function errorText(e: unknown, fallback: string): string {
  if (e instanceof ApiError && e.status === 429) return "Too many attempts. Wait a moment and try again.";
  return e instanceof Error ? e.message : fallback;
}

function fileProblem(file: File): string | null {
  if (!/\.(pdf|jpe?g|png|webp)$/i.test(file.name) && !/^(application\/pdf|image\/(jpeg|png|webp))$/.test(file.type))
    return "Only PDF, JPG, PNG or WEBP files.";
  if (file.size > MAX_MB * 1024 * 1024) return `${file.name} is larger than ${MAX_MB} MB.`;
  if (file.size === 0) return "That file is empty.";
  return null;
}

function statusChip(doc: VerificationDoc) {
  if (doc.status === "approved") return <Chip tone="verified" size="sm">Approved</Chip>;
  if (doc.status === "rejected") return <Chip tone="frozen" size="sm">Needs changes</Chip>;
  return <Chip tone="move" size="sm" icon="clock">In review</Chip>;
}

/**
 * Business verification — the KYB entries of the business.
 *
 * Each row: a document from the admin's list for the business's country
 * (left) and its number and/or a copy (right). "Other" takes a custom name.
 * Numbers are stored encrypted and shown masked; "Show" reveals one.
 */
export function KybSection({
  country,
  rejectedItems = [],
  onChanged,
}: {
  country: string;
  /** Keys Corridor ops flagged on the last rejection (kyb:<code> / doc:<id>). */
  rejectedItems?: string[];
  onChanged: () => void;
}) {
  const flagged = new Set(rejectedItems);
  const toast = useToast();
  const [types, setTypes] = useState<KybDocType[] | null>(null);
  const [entries, setEntries] = useState<VerificationDoc[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [adding, setAdding] = useState<string | null>(null); // type id, OTHER, or null

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const [t, e] = await Promise.all([api.kybDocTypes(), api.listVerificationDocs()]);
      setTypes(t);
      setEntries(e);
    } catch (err) {
      setLoadError(errorText(err, "Could not load your documents."));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, country]);

  const byType = useMemo(() => {
    const m = new Map<string, VerificationDoc>();
    for (const e of entries ?? []) if (e.documentTypeId) m.set(e.documentTypeId, e);
    return m;
  }, [entries]);

  const others = (entries ?? []).filter((e) => e.isOther || (e.documentTypeId && !types?.some((t) => t.id === e.documentTypeId)));
  const available = (types ?? []).filter((t) => !byType.has(t.id));

  function changed(next: VerificationDoc[] | ((prev: VerificationDoc[]) => VerificationDoc[])) {
    setEntries((prev) => (typeof next === "function" ? next(prev ?? []) : next));
    onChanged();
  }

  if (loadError) {
    return (
      <Notice tone="frozen" action={<Button size="sm" variant="secondary" onClick={() => void load()}>Retry</Button>}>
        {loadError}
      </Notice>
    );
  }
  if (!types || !entries) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-20 rounded-[22px]" />
        <Skeleton className="h-20 rounded-[22px]" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {types.length === 0 ? (
        <Notice tone="info">No documents are listed for this country yet. Add any certificate with “Other”.</Notice>
      ) : null}

      {types.map((t) => {
        const entry = byType.get(t.id);
        if (entry) {
          return (
            <EntryRow
              key={t.id}
              anchor={`kyb-${t.code}`}
              doc={entry}
              type={t}
              flagged={flagged.has(`kyb:${t.code}`)}
              onUpdated={(d) => changed((xs) => xs.map((x) => (x.id === d.id ? d : x)))}
              onDeleted={() => changed((xs) => xs.filter((x) => x.id !== entry.id))}
            />
          );
        }
        if (!t.isMandatory) return null;
        return adding === t.id ? (
          <AddEntryForm
            key={t.id}
            anchor={`kyb-${t.code}`}
            types={types}
            initialType={t.id}
            lockType
            onCancel={() => setAdding(null)}
            onAdded={(d) => {
              changed((xs) => [...xs, d]);
              setAdding(null);
              toast(`${d.certType} added`, "verified");
            }}
          />
        ) : (
          <MissingRow key={t.id} anchor={`kyb-${t.code}`} type={t} onAdd={() => setAdding(t.id)} />
        );
      })}

      {others.map((e) => (
        <EntryRow
          key={e.id}
          anchor={`doc-${e.id}`}
          doc={e}
          type={null}
          flagged={flagged.has(`doc:${e.id}`)}
          onUpdated={(d) => changed((xs) => xs.map((x) => (x.id === d.id ? d : x)))}
          onDeleted={() => changed((xs) => xs.filter((x) => x.id !== e.id))}
        />
      ))}

      {adding === OTHER || (adding && !types.find((t) => t.id === adding)?.isMandatory) ? (
        <AddEntryForm
          types={available.filter((t) => !t.isMandatory)}
          initialType={adding}
          onCancel={() => setAdding(null)}
          onAdded={(d) => {
            changed((xs) => [...xs, d]);
            setAdding(null);
            toast(`${d.certType} added`, "verified");
          }}
        />
      ) : (
        <button
          type="button"
          onClick={() => setAdding(available.find((t) => !t.isMandatory)?.id ?? OTHER)}
          className="well flex w-full items-center justify-center gap-2 rounded-[22px] px-4 py-4 text-[14px] font-medium text-fg-2 transition-colors hover:text-fg"
        >
          <Icon name="plus" size={16} />
          Add another document
        </button>
      )}
    </div>
  );
}

// ── Rows ───────────────────────────────────────────────────────────────

function MissingRow({ anchor, type, onAdd }: { anchor: string; type: KybDocType; onAdd: () => void }) {
  return (
    <div
      id={anchor}
      tabIndex={-1}
      className="flex flex-wrap items-center justify-between gap-3 rounded-[22px] border border-dashed border-amber/50 px-4 py-4 outline-none sm:px-5"
    >
      <div className="min-w-0">
        <p className="t-headline flex items-center gap-2 text-fg">
          {type.name}
          <Chip tone="move" size="sm" noIcon>Required</Chip>
        </p>
        <p className="t-sub mt-0.5 text-fg-3">{type.helpText ?? requirementText(type)}</p>
      </div>
      <Button size="sm" variant="secondary" icon="plus" onClick={onAdd}>
        Add
      </Button>
    </div>
  );
}

function requirementText(t: KybDocType): string {
  switch (t.inputKind) {
    case "value":
      return "Enter the number.";
    case "file":
      return "Upload a copy.";
    case "value_and_file":
      return "Enter the number and upload a copy.";
    default:
      return "Enter the number or upload a copy.";
  }
}

function EntryRow({
  anchor,
  doc,
  type,
  flagged,
  onUpdated,
  onDeleted,
}: {
  anchor?: string;
  doc: VerificationDoc;
  type: KybDocType | null;
  flagged?: boolean;
  onUpdated: (d: VerificationDoc) => void;
  onDeleted: () => void;
}) {
  const toast = useToast();
  const confirmReview = useReviewConfirm();
  const required = Boolean(type?.isMandatory);
  const [revealed, setRevealed] = useState<string | null>(null);
  const [busy, setBusy] = useState<"reveal" | "delete" | "save" | null>(null);
  const [editing, setEditing] = useState(false);
  const [viewing, setViewing] = useState(false);
  const [value, setValue] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const showValueInput = !type || type.inputKind !== "file";
  const showFileInput = !type || type.inputKind !== "value" || doc.hasFile;

  async function reveal() {
    if (revealed) return setRevealed(null);
    setBusy("reveal");
    try {
      setRevealed((await api.revealKybValue(doc.id)).value);
    } catch (e) {
      toast(errorText(e, "Couldn’t show the number."), "frozen");
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    if (required ? !(await confirmReview(`your ${doc.certType}`)) : !window.confirm(`Remove ${doc.certType}?`)) return;
    setBusy("delete");
    try {
      await api.deleteVerificationDoc(doc.id);
      onDeleted();
      toast(`${doc.certType} removed`);
    } catch (e) {
      toast(errorText(e, "Couldn’t remove it."), "frozen");
      setBusy(null);
    }
  }

  async function save() {
    setError(null);
    if (!value.trim() && !file) return setError("Enter a new number or choose a new file.");
    if (required && !(await confirmReview(`your ${doc.certType}`))) return;
    setBusy("save");
    try {
      const d = await api.updateKybEntry(doc.id, { value: value.trim() || undefined, file });
      onUpdated(d);
      setEditing(false);
      setValue("");
      setFile(null);
      setRevealed(null);
      toast(`${d.certType} updated — back in review`, "verified");
    } catch (e) {
      setError(errorText(e, "Couldn’t save."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div
      id={anchor}
      tabIndex={-1}
      className={cn(
        "relief rounded-[22px] px-4 py-4 outline-none sm:px-5",
        flagged && doc.status === "rejected" && "![box-shadow:var(--relief),inset_0_0_0_1.5px_var(--c-danger)]",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="t-headline flex flex-wrap items-center gap-2 text-fg">
            {doc.certType}
            {doc.isOther ? <Chip tone="quiet" size="sm" noIcon>Other</Chip> : null}
            {statusChip(doc)}
          </p>
          <div className="t-sub mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-fg-3">
            {doc.hasValue ? (
              <span className="inline-flex items-center gap-1.5">
                <span className="t-code text-[13px] text-fg">{revealed ?? doc.valueMasked}</span>
                <button
                  type="button"
                  onClick={reveal}
                  disabled={busy === "reveal"}
                  className="inline-flex items-center gap-1 rounded-full px-1.5 text-fg-3 hover:text-fg"
                  aria-label={revealed ? "Hide number" : "Show number"}
                >
                  <Icon name={revealed ? "eye-off" : "eye"} size={14} />
                  {revealed ? "Hide" : "Show"}
                </button>
              </span>
            ) : null}
            {doc.hasFile && doc.url ? (
              <button
                type="button"
                onClick={() => setViewing(true)}
                className="inline-flex max-w-[240px] items-center gap-1 underline-offset-4 hover:text-fg hover:underline"
                aria-label={`View ${doc.filename ?? doc.certType}`}
              >
                <Icon name="file" size={14} className="shrink-0" />
                <span className="truncate">{doc.filename}</span>
              </button>
            ) : null}
            <span className="t-code text-[11px]">Added {formatDay(doc.uploadedAt)}</span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {doc.status !== "approved" || !type ? (
            <IconButton icon="pen" size="sm" label={`Change ${doc.certType}`} onClick={() => setEditing((x) => !x)} />
          ) : null}
          <IconButton
            icon="trash"
            size="sm"
            label={`Remove ${doc.certType}`}
            onClick={remove}
            disabled={busy === "delete"}
          />
        </div>
      </div>

      <FileViewer doc={doc} open={viewing} onClose={() => setViewing(false)} />

      {doc.status === "rejected" && doc.rejectionReason ? (
        <p className="t-sub mt-3 border-l-2 border-danger/50 pl-3 text-fg-2">Corridor ops: {doc.rejectionReason}</p>
      ) : null}

      {editing ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
          <div className="grid gap-3 sm:grid-cols-2">
            {showValueInput ? (
              <Input
                label="New number"
                optional={!type?.needsValue}
                placeholder={type?.valuePlaceholder ?? undefined}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                autoComplete="off"
                spellCheck={false}
              />
            ) : null}
            {showFileInput ? (
              <FilePick file={file} onFile={setFile} inputRef={fileRef} label="New copy" onError={setError} />
            ) : null}
          </div>
          <div className="flex gap-2">
            <Button size="md" variant="quiet" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button size="md" loading={busy === "save"} onClick={save}>
              Save
            </Button>
          </div>
          {error ? <p role="alert" className="t-sub text-danger sm:col-span-2">{error}</p> : null}
        </div>
      ) : null}
    </div>
  );
}

// ── Add form ───────────────────────────────────────────────────────────

function AddEntryForm({
  anchor,
  types,
  initialType,
  lockType,
  onCancel,
  onAdded,
}: {
  anchor?: string;
  types: KybDocType[];
  initialType: string | null;
  lockType?: boolean;
  onCancel: () => void;
  onAdded: (d: VerificationDoc) => void;
}) {
  const [typeId, setTypeId] = useState<string>(initialType ?? OTHER);
  const [customName, setCustomName] = useState("");
  const [value, setValue] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const confirmReview = useReviewConfirm();
  const fileRef = useRef<HTMLInputElement>(null);
  const type = types.find((t) => t.id === typeId) ?? null;
  const isOther = typeId === OTHER;
  const showValue = isOther || type?.inputKind !== "file";
  const showFile = isOther || type?.inputKind !== "value";

  async function submit() {
    setError(null);
    if (isOther && customName.trim().length < 2) return setError("Enter the document’s name.");
    if (type?.needsValue && !value.trim()) return setError(`Enter the ${type.name} number.`);
    if (type?.needsFile && !file) return setError(`Upload a copy of the ${type.name}.`);
    if (!value.trim() && !file) return setError("Enter the number or upload a copy.");
    if (type?.valuePattern && value.trim()) {
      const clean = value.replace(/\s+/g, "").toUpperCase();
      if (!new RegExp(`^(?:${type.valuePattern})$`).test(clean)) {
        return setError(`That doesn’t look like a valid ${type.name}.${type.valuePlaceholder ? ` Expected: ${type.valuePlaceholder}` : ""}`);
      }
    }
    if (type?.isMandatory && !(await confirmReview(`your ${type.name}`))) return;
    setSaving(true);
    try {
      onAdded(
        await api.addKybEntry({
          documentTypeId: isOther ? undefined : typeId,
          customName: isOther ? customName.trim() : undefined,
          value: value.trim() || undefined,
          file,
        }),
      );
    } catch (e) {
      setError(errorText(e, "Couldn’t add the document."));
      setSaving(false);
    }
  }

  return (
    <div id={anchor} tabIndex={-1} className="relief rounded-[22px] p-4 outline-none sm:p-5">
      <div className="grid gap-3 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <div className="space-y-3">
          {lockType && type ? (
            <div>
              <p className="t-label text-fg-3">Document</p>
              <p className="t-headline mt-2 text-fg">{type.name}</p>
            </div>
          ) : (
            <Select
              label="Document"
              value={typeId}
              onChange={(e) => {
                setTypeId(e.target.value);
                setError(null);
              }}
              options={[...types.map((t) => ({ value: t.id, label: t.name })), { value: OTHER, label: "Other…" }]}
            />
          )}
          {isOther ? (
            <Input
              label="Document name"
              placeholder="e.g. Spices Board registration"
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              maxLength={150}
              hint="Aadhaar can’t be submitted."
            />
          ) : null}
        </div>
        <div className="space-y-3">
          {showValue ? (
            <Input
              label="Number"
              optional={!isOther && !type?.needsValue}
              placeholder={type?.valuePlaceholder ?? undefined}
              hint={type?.helpText ?? undefined}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              inputClassName="t-code"
            />
          ) : null}
          {showFile ? (
            <FilePick
              file={file}
              onFile={setFile}
              inputRef={fileRef}
              label="Copy of the document"
              optional={!isOther && !type?.needsFile}
              onError={setError}
            />
          ) : null}
        </div>
      </div>
      {error ? <p role="alert" className="t-sub mt-3 text-danger">{error}</p> : null}
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="quiet" onClick={onCancel}>
          Cancel
        </Button>
        <Button loading={saving} onClick={submit} icon="check">
          Add document
        </Button>
      </div>
      <p className="t-sub mt-3 flex items-center gap-1.5 text-fg-3">
        <Icon name="lock" size={13} /> Numbers are stored encrypted and shown only to you and Corridor ops.
      </p>
    </div>
  );
}

function FilePick({
  file,
  onFile,
  inputRef,
  label,
  optional,
  onError,
}: {
  file: File | null;
  onFile: (f: File | null) => void;
  inputRef: React.RefObject<HTMLInputElement>;
  label: string;
  optional?: boolean;
  onError: (msg: string | null) => void;
}) {
  return (
    <div>
      <p className="t-label mb-2 text-fg-3">
        {label}
        {optional ? <span className="ml-1.5 normal-case tracking-normal">optional</span> : null}
      </p>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="sr-only"
        onChange={(e) => {
          const f = e.target.files?.[0] ?? null;
          e.target.value = "";
          if (!f) return;
          const problem = fileProblem(f);
          if (problem) return onError(problem);
          onError(null);
          onFile(f);
        }}
      />
      <div className={cn("field flex h-12 items-center justify-between gap-2 px-4 text-[15px]", !file && "text-fg-3")}>
        <span className="flex min-w-0 items-center gap-2">
          <Icon name={file ? "file" : "upload"} size={16} className="shrink-0" />
          <span className="truncate">{file ? file.name : "PDF, JPG, PNG or WEBP · up to 10 MB"}</span>
        </span>
        {file ? (
          <button type="button" className="text-fg-3 hover:text-fg" onClick={() => onFile(null)} aria-label="Remove file">
            <Icon name="close" size={14} />
          </button>
        ) : (
          <button type="button" className="font-medium text-fg" onClick={() => inputRef.current?.click()}>
            Choose
          </button>
        )}
      </div>
    </div>
  );
}

/** In-page preview of an entry's file: images inline, PDFs in a frame. */
function FileViewer({ doc, open, onClose }: { doc: VerificationDoc; open: boolean; onClose: () => void }) {
  if (!doc.url) return null;
  const src = assetUrl(doc.url);
  const isPdf = doc.mimeType === "application/pdf";
  return (
    <Sheet
      open={open}
      onClose={onClose}
      size="lg"
      title={doc.certType}
      description={doc.filename ?? undefined}
      footer={
        <a href={src} target="_blank" rel="noreferrer" className="t-sub inline-flex items-center gap-1.5 font-medium text-fg hover:underline">
          <Icon name="external" size={14} /> Open in a new tab
        </a>
      }
    >
      {open ? (
        isPdf ? (
          <iframe src={src} title={doc.filename ?? doc.certType} className="h-[65vh] w-full rounded-[14px] bg-white" />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt={doc.certType} className="mx-auto max-h-[65vh] w-auto rounded-[14px] object-contain" />
        )
      ) : null}
    </Sheet>
  );
}
