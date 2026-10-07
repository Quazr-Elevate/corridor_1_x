"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2,
  Clock,
  FileText,
  Image as ImageIcon,
  Loader2,
  Search,
  Trash2,
  Upload,
  XCircle,
} from "lucide-react";
import { api, type VerificationDoc } from "@/lib/api";
import { CERTIFICATION_CATALOGUE } from "@/lib/certifications";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
const MAX_MB = 10;

export function CertificationsBlock() {
  const [docs, setDocs] = useState<VerificationDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const d = await api.listVerificationDocs();
      setDocs(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onUploaded(doc: VerificationDoc) {
    setDocs((d) => [doc, ...d]);
  }

  async function onDelete(id: string) {
    if (!window.confirm("Remove this certificate?")) return;
    try {
      await api.deleteVerificationDoc(id);
      setDocs((d) => d.filter((x) => x.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  // The outer card renders its own heading (see dashboard/account/page.tsx),
  // so this component is just the picker + the uploaded-doc list.
  return (
    <div>
      <p className="text-sm text-paper-muted leading-relaxed">
        Add one certificate at a time. Search for the type, pick it, then
        attach your file. Our team reviews each certificate individually.
      </p>

      <CertificationPicker onUploaded={onUploaded} onError={setError} />

      {error && (
        <div className="mt-3 rounded-field border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
          {error}
        </div>
      )}

      {loading ? (
        <div className="mt-4 flex justify-center py-4">
          <Loader2 className="h-5 w-5 animate-spin text-paper-muted" />
        </div>
      ) : docs.length === 0 ? (
        <p className="mt-4 text-xs text-paper-muted/70">
          No certificates uploaded yet.
        </p>
      ) : (
        <ul className="mt-4 space-y-2">
          {docs.map((d) => (
            <DocRow
              key={d.id}
              doc={d}
              onDelete={() => onDelete(d.id)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Searchable picker + file attach ──────────────────────────────────

function CertificationPicker({
  onUploaded,
  onError,
}: {
  onUploaded: (doc: VerificationDoc) => void;
  onError: (msg: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Close dropdown on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Only compute matches once the user has started typing — the dropdown
  // stays empty on an unfocused or blank input. This keeps the UI clean
  // and nudges people to search by name instead of scrolling.
  const needle = query.trim().toLowerCase();
  const filtered = useMemo(() => {
    if (!needle) return [];
    return CERTIFICATION_CATALOGUE.filter((c) =>
      c.toLowerCase().includes(needle),
    );
  }, [needle]);

  async function onFile(files: FileList | null) {
    if (!files || files.length === 0 || !selected) return;
    const file = files[0];
    if (file.size > MAX_MB * 1024 * 1024) {
      onError(`${file.name} is larger than ${MAX_MB} MB.`);
      return;
    }
    setUploading(true);
    try {
      const doc = await api.uploadVerificationDoc(selected, file);
      onUploaded(doc);
      setSelected(null);
      setQuery("");
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (e) {
      onError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto]">
      <div ref={ref} className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-paper-muted" />
        <input
          type="text"
          value={selected ?? query}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setSelected(null);
            setOpen(true);
          }}
          placeholder="Start typing — e.g. GST, FSSAI, phytosanitary…"
          className="w-full rounded-field border border-line-soft bg-ink pl-9 pr-9 py-3 text-sm text-paper placeholder-mute-soft/60 focus:outline-none focus:border-accent/60 focus:shadow-focus transition"
        />
        {selected && (
          <button
            type="button"
            onClick={() => {
              setSelected(null);
              setQuery("");
            }}
            aria-label="Clear selection"
            className="absolute right-3 top-1/2 -translate-y-1/2 text-paper-muted hover:text-paper"
          >
            <XCircle className="h-4 w-4" />
          </button>
        )}

        {open && !selected && needle && (
          <div className="absolute z-20 mt-1 w-full rounded-field border border-line-soft bg-ink-elevated shadow-card max-h-72 overflow-y-auto">
            {filtered.length === 0 ? (
              <p className="px-3 py-3 text-xs text-paper-muted">
                No match in our catalogue. Use{" "}
                <button
                  type="button"
                  onClick={() => {
                    setSelected(query.trim());
                    setOpen(false);
                  }}
                  className="text-accent hover:underline"
                >
                  &ldquo;{query.trim()}&rdquo;
                </button>{" "}
                as a custom entry.
              </p>
            ) : (
              <ul>
                {filtered.map((c) => (
                  <li key={c}>
                    <button
                      type="button"
                      onClick={() => {
                        setSelected(c);
                        setOpen(false);
                      }}
                      className="w-full px-3 py-2 text-left text-sm text-paper-soft hover:bg-ink hover:text-paper transition"
                    >
                      {c}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <label
        className={`inline-flex items-center justify-center gap-2 rounded-field px-4 py-3 text-sm font-semibold transition ${
          selected
            ? "bg-accent text-accent-fg cursor-pointer hover:bg-accent-hover"
            : "bg-line-soft/40 text-paper-muted cursor-not-allowed"
        }`}
        aria-disabled={!selected || uploading}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,image/*"
          onChange={(e) => onFile(e.target.files)}
          disabled={!selected || uploading}
          className="sr-only"
        />
        {uploading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" /> Uploading
          </>
        ) : (
          <>
            <Upload className="h-4 w-4" /> Attach file
          </>
        )}
      </label>
    </div>
  );
}

// ── Doc row ──────────────────────────────────────────────────────────

function DocRow({
  doc,
  onDelete,
}: {
  doc: VerificationDoc;
  onDelete: () => void;
}) {
  const Icon = doc.mimeType.startsWith("image/") ? ImageIcon : FileText;
  const sizeKb = Math.round(doc.sizeBytes / 1024);
  const rejected = doc.status === "rejected";
  return (
    <li
      id={`doc-${doc.id}`}
      className={`rounded-field border bg-ink px-4 py-3 ${
        rejected ? "border-danger/40" : "border-line-soft"
      }`}
    >
      <div className="flex items-center gap-3">
        <Icon className="h-4 w-4 shrink-0 text-paper-muted" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-paper truncate">
            {doc.certType}
          </p>
          <a
            href={`${API_BASE}${doc.url}`}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-paper-muted hover:underline truncate block"
          >
            {doc.filename} · {sizeKb} KB
          </a>
        </div>
        <StatusPill status={doc.status} />
        {doc.status !== "approved" && (
          <button
            type="button"
            onClick={onDelete}
            aria-label="Remove document"
            className="rounded-full p-1 text-paper-muted hover:bg-ink-elevated hover:text-danger transition"
          >
            <Trash2 className="h-3.5 w-3.5" aria-hidden />
          </button>
        )}
      </div>
      {rejected && doc.rejectionReason && (
        <div className="mt-2 rounded-field border border-danger/30 bg-danger/5 px-3 py-2">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-danger">
            Rejected — reason
          </p>
          <p className="mt-1 text-xs text-paper leading-relaxed">
            {doc.rejectionReason}
          </p>
          <p className="mt-1 text-[11px] text-paper-muted">
            Delete this entry and upload a replacement to re-submit.
          </p>
        </div>
      )}
    </li>
  );
}

function StatusPill({ status }: { status: VerificationDoc["status"] }) {
  if (status === "approved") {
    return (
      <span className="inline-flex items-center gap-1 rounded-pill border border-accent/30 bg-accent/15 text-accent px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest">
        <CheckCircle2 className="h-3 w-3" aria-hidden /> Approved
      </span>
    );
  }
  if (status === "rejected") {
    return (
      <span className="inline-flex items-center gap-1 rounded-pill border border-danger/30 bg-danger/15 text-danger px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest">
        <XCircle className="h-3 w-3" aria-hidden /> Rejected
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-pill border border-violet/30 bg-violet/15 text-violet px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest">
      <Clock className="h-3 w-3" aria-hidden /> Pending
    </span>
  );
}
