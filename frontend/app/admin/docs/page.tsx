"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Check,
  Download,
  FileText,
  Image as ImageIcon,
  Loader2,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";
import { adminApi, type PendingDocRow, type VerifyDoc } from "@/lib/adminApi";
import { RejectReasonModal } from "@/components/admin/RejectReasonModal";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

export default function PendingDocsPage() {
  const [rows, setRows] = useState<PendingDocRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [preview, setPreview] = useState<VerifyDoc | null>(null);
  const [rejectTarget, setRejectTarget] = useState<PendingDocRow | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const q = await adminApi.pendingDocs();
      setRows(q);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function approve(docId: string) {
    setBusyId(docId);
    try {
      await adminApi.approveDoc(docId);
      setRows((r) => r.filter((x) => x.doc.id !== docId));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setBusyId(null);
    }
  }

  async function reject(docId: string, reason: string) {
    setBusyId(docId);
    try {
      await adminApi.rejectDoc(docId, reason);
      setRows((r) => r.filter((x) => x.doc.id !== docId));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="mx-auto max-w-[1240px] px-6 py-8">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div>
          <p className="text-[12px]" style={{ color: "var(--sp-text-3)" }}>
            Admin console · Pending documents
          </p>
          <h1
            className="mt-1 text-[34px] font-semibold tracking-[-0.025em]"
            style={{ color: "var(--sp-text)" }}
          >
            {rows.length} document{rows.length === 1 ? "" : "s"} awaiting review
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/admin"
            className="sp-chip"
            style={{ paddingLeft: "0.75rem" }}
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> Dashboard
          </Link>
          <button
            type="button"
            onClick={load}
            aria-label="Refresh"
            className="sp-icon-btn"
          >
            <RefreshCw className="h-4 w-4" aria-hidden />
          </button>
        </div>
      </div>

      {err && (
        <div
          className="sp-airy mt-6 p-4 text-[13px]"
          style={{ color: "var(--sp-error)" }}
        >
          {err}
        </div>
      )}

      {loading ? (
        <div className="mt-6 flex justify-center py-12">
          <Loader2
            className="h-6 w-6 animate-spin"
            style={{ color: "var(--sp-lime)" }}
          />
        </div>
      ) : rows.length === 0 ? (
        <section className="sp-airy mt-6 p-10 text-center">
          <div
            className="mx-auto flex h-12 w-12 items-center justify-center rounded-full"
            style={{
              background: "var(--sp-lime-14)",
              color: "var(--sp-lime)",
            }}
          >
            <ShieldCheck className="h-6 w-6" aria-hidden />
          </div>
          <p
            className="mt-4 text-[15px] font-semibold"
            style={{ color: "var(--sp-text)" }}
          >
            No pending documents
          </p>
          <p
            className="mt-1 text-[12.5px]"
            style={{ color: "var(--sp-text-3)" }}
          >
            Everything users uploaded has been reviewed.
          </p>
        </section>
      ) : (
        <ul className="mt-6 space-y-3">
          {rows.map((row) => (
            <li key={row.doc.id} className="sp-airy p-4">
              <div className="flex flex-wrap items-center gap-4">
                <DocIcon doc={row.doc} />
                <div className="min-w-0 flex-1">
                  <p
                    className="text-[14px] font-semibold"
                    style={{ color: "var(--sp-text)" }}
                  >
                    {row.doc.certType}
                  </p>
                  <button
                    type="button"
                    onClick={() => setPreview(row.doc)}
                    className="truncate text-[12px] hover:underline"
                    style={{ color: "var(--sp-text-2)" }}
                  >
                    {row.doc.filename} · {Math.round(row.doc.sizeBytes / 1024)}{" "}
                    KB
                  </button>
                  <div
                    className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px]"
                    style={{ color: "var(--sp-text-3)" }}
                  >
                    <Link
                      href={`/admin/users/${row.userId}`}
                      className="hover:underline"
                      style={{ color: "var(--sp-text-2)" }}
                    >
                      {row.userBusinessName ||
                        row.userFullName ||
                        row.userEmail}
                    </Link>
                    {row.userCountry && <span>· {row.userCountry}</span>}
                    <span>
                      · Uploaded{" "}
                      {new Date(row.doc.uploadedAt).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href={`${API_BASE}${row.doc.url}`}
                    download={row.doc.filename}
                    className="sp-icon-btn"
                    aria-label={`Download ${row.doc.filename}`}
                  >
                    <Download className="h-4 w-4" aria-hidden />
                  </a>
                  <button
                    type="button"
                    onClick={() => setRejectTarget(row)}
                    disabled={busyId === row.doc.id}
                    className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-semibold transition disabled:opacity-50"
                    style={{
                      borderColor: "var(--sp-border)",
                      color: "var(--sp-error)",
                    }}
                  >
                    <X className="h-3.5 w-3.5" aria-hidden /> Reject
                  </button>
                  <button
                    type="button"
                    onClick={() => approve(row.doc.id)}
                    disabled={busyId === row.doc.id}
                    className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-semibold transition disabled:opacity-50"
                    style={{
                      background: "var(--sp-lime)",
                      color: "var(--sp-lime-fg)",
                    }}
                  >
                    {busyId === row.doc.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                    ) : (
                      <Check className="h-3.5 w-3.5" aria-hidden />
                    )}
                    Approve
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {preview && (
        <PreviewModal doc={preview} onClose={() => setPreview(null)} />
      )}

      <RejectReasonModal
        open={rejectTarget !== null}
        title={rejectTarget ? `Reject ${rejectTarget.doc.certType}?` : ""}
        subtitle={
          rejectTarget
            ? `Shown to ${rejectTarget.userBusinessName || rejectTarget.userEmail} on their next login.`
            : undefined
        }
        onClose={() => setRejectTarget(null)}
        onSubmit={async (reason) => {
          if (!rejectTarget) return;
          await reject(rejectTarget.doc.id, reason);
        }}
      />
    </div>
  );
}

function DocIcon({ doc }: { doc: VerifyDoc }) {
  const Icon = doc.mimeType.startsWith("image/") ? ImageIcon : FileText;
  return (
    <div
      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
      style={{ background: "var(--sp-card-2)", color: "var(--sp-text-2)" }}
    >
      <Icon className="h-4 w-4" aria-hidden />
    </div>
  );
}

function PreviewModal({
  doc,
  onClose,
}: {
  doc: VerifyDoc;
  onClose: () => void;
}) {
  const src = `${API_BASE}${doc.url}`;
  const isImage = doc.mimeType.startsWith("image/");
  const isPdf = doc.mimeType === "application/pdf";
  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-3xl rounded-[22px] overflow-hidden"
        style={{
          background: "var(--sp-card)",
          border: "1px solid var(--sp-border)",
        }}
      >
        <div
          className="flex items-center justify-between p-4"
          style={{ borderBottom: "1px solid var(--sp-border)" }}
        >
          <p
            className="truncate text-[14px] font-semibold"
            style={{ color: "var(--sp-text)" }}
          >
            {doc.certType} · {doc.filename}
          </p>
          <div className="flex items-center gap-2">
            <a
              href={src}
              download={doc.filename}
              className="sp-icon-btn"
              aria-label="Download"
            >
              <Download className="h-4 w-4" aria-hidden />
            </a>
            <button
              type="button"
              onClick={onClose}
              className="sp-icon-btn"
              aria-label="Close preview"
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>
        <div style={{ background: "var(--sp-canvas)", height: "70vh" }}>
          {isImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={src}
              alt={doc.filename}
              className="h-full w-full object-contain"
            />
          ) : isPdf ? (
            <iframe
              src={src}
              title={doc.filename}
              className="h-full w-full"
              style={{ border: 0 }}
            />
          ) : (
            <div
              className="flex h-full flex-col items-center justify-center gap-3 text-[13px]"
              style={{ color: "var(--sp-text-2)" }}
            >
              <FileText className="h-10 w-10" aria-hidden />
              Preview not available. Use the download button above.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
