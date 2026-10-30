"use client";

import { useEffect, useRef, useState, type HTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { adminApi, docFileUrl, USER_STATUS_LABEL, type DocStatus, type VerifyDoc } from "@/lib/adminApi";
import { buttonClass } from "@/components/ui/Button";
import { Chip, type ChipTone } from "@/components/ui/Chip";
import { Icon, type IconName } from "@/components/ui/Icon";
import { fmtBytes, fmtDate, fmtDateTime, refId } from "./format";

/* ───────────────────────────── Status chips ───────────────────────── */

const STATUS_TONE: Record<string, ChipTone> = {
  verified: "verified",
  rejected: "frozen",
  pending_verification: "move",
  draft: "quiet",
};

export function StatusChip({ status, className }: { status: string; className?: string }) {
  const tone = STATUS_TONE[status] ?? "quiet";
  return (
    <Chip tone={tone} icon={tone === "move" ? "clock" : undefined} className={className}>
      {USER_STATUS_LABEL[status] ?? status.replace(/_/g, " ")}
    </Chip>
  );
}

const DOC_TONE: Record<DocStatus, ChipTone> = {
  pending: "move",
  approved: "verified",
  rejected: "frozen",
};
const DOC_LABEL: Record<DocStatus, string> = {
  pending: "To check",
  approved: "Approved",
  rejected: "Rejected",
};

export function DocStatusChip({ status }: { status: DocStatus }) {
  return (
    <Chip tone={DOC_TONE[status] ?? "quiet"} icon={status === "pending" ? "clock" : undefined}>
      {DOC_LABEL[status] ?? status}
    </Chip>
  );
}

/* ───────────────────────────── Keyboard hints ─────────────────────── */

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="t-code inline-grid h-5 min-w-5 place-items-center rounded-[6px] px-1 text-[11px] text-fg-2 shadow-[inset_0_0_0_1px_var(--c-line-2)]">
      {children}
    </kbd>
  );
}

export function KbdHints() {
  return (
    <p className="t-foot hidden items-center gap-1.5 text-fg-3 lg:flex" aria-hidden="true">
      <Kbd>J</Kbd>
      <Kbd>K</Kbd>
      <span className="ml-0.5">move</span>
    </p>
  );
}

function isTyping(t: EventTarget | null) {
  const el = t as HTMLElement | null;
  if (!el) return false;
  return el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName);
}

/** J / K move through a queue. Ignored while typing or while a sheet is open. */
export function useQueueKeys(count: number, move: (delta: 1 | -1) => void, enabled = true) {
  const moveRef = useRef(move);
  moveRef.current = move;
  useEffect(() => {
    if (!enabled || count === 0) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isTyping(e.target)) return;
      if (document.querySelector('[role="dialog"]')) return;
      const k = e.key.toLowerCase();
      if (k === "j") {
        e.preventDefault();
        moveRef.current(1);
      } else if (k === "k") {
        e.preventDefault();
        moveRef.current(-1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [count, enabled]);
}

/** A clock that re-renders every `ms` (SLA labels stay honest). */
export function useNow(ms = 60_000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), ms);
    return () => window.clearInterval(id);
  }, [ms]);
  return now;
}

/* ───────────────────────────── Queue card ─────────────────────────── */

export interface QueueItem {
  id: string;
  code: string;
  title: string;
  sub?: ReactNode;
  due?: { over: boolean; label: string };
  tag?: ReactNode;
}

/**
 * The left pane of a two-pane lane (reference: portal /ops/kyb). The
 * selected card turns cream; the rest sit in relief. Keeps the selection
 * scrolled into view.
 */
export function QueueList({
  items,
  selectedId,
  onSelect,
  label,
}: {
  items: ReadonlyArray<QueueItem>;
  selectedId: string | null;
  onSelect: (id: string) => void;
  label: string;
}) {
  const refs = useRef(new Map<string, HTMLButtonElement>());
  useEffect(() => {
    if (!selectedId) return;
    refs.current.get(selectedId)?.scrollIntoView({ block: "nearest" });
  }, [selectedId]);

  return (
    <ul aria-label={label} className="flex flex-col gap-2.5">
      {items.map((it) => {
        const sel = it.id === selectedId;
        return (
          <li key={it.id}>
            <button
              ref={(el) => {
                if (el) refs.current.set(it.id, el);
                else refs.current.delete(it.id);
              }}
              type="button"
              aria-current={sel ? "true" : undefined}
              onClick={() => onSelect(it.id)}
              className={cn(
                "block w-full rounded-[22px] p-4 text-left transition-[box-shadow,background-color,color] duration-300 ease-expo",
                sel
                  ? "bg-cream text-ink shadow-[0_18px_40px_-20px_rgb(0_0_0/0.9),inset_0_1px_0_rgb(255_255_255/0.6)]"
                  : "relief-sm hover:shadow-[var(--relief)]",
              )}
            >
              <span className="flex items-center justify-between gap-2">
                <span className={cn("t-code", sel ? "text-ink/60" : "text-fg-3")}>{it.code}</span>
                {it.due ? (
                  <span
                    className={cn(
                      "t-foot tabular shrink-0 font-semibold",
                      it.due.over ? (sel ? "text-[#b3261e]" : "text-danger") : sel ? "text-ink/60" : "text-fg-3",
                    )}
                  >
                    {it.due.label}
                  </span>
                ) : (
                  <span className={cn("shrink-0", sel ? "text-ink/70" : "text-fg-3")}>{it.tag}</span>
                )}
              </span>
              <span className={cn("t-headline mt-1.5 block truncate", !sel && "text-fg")}>{it.title}</span>
              {it.sub ? (
                <span className={cn("t-sub mt-0.5 block truncate", sel ? "text-ink/60" : "text-fg-3")}>{it.sub}</span>
              ) : null}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/* ───────────────────────────── Pills (sections / documents) ───────── */

export type PillDot = "verified" | "move" | "frozen" | "none";

export interface PillTab<T extends string> {
  value: T;
  label: ReactNode;
  dot?: PillDot;
}

/**
 * A row of pill tabs over a cream "paper" (reference: the document pills
 * on /ops/kyb). The current one is cream; the rest sit in wells. A small
 * dot carries each item's state. Real tablist: arrows, Home / End.
 */
export function PillTabs<T extends string>({
  value,
  onChange,
  tabs,
  label,
  idPrefix,
}: {
  value: T;
  onChange: (v: T) => void;
  tabs: ReadonlyArray<PillTab<T>>;
  label: string;
  /** Prefix for tab / panel ids (`${idPrefix}-tab-${value}`, `${idPrefix}-panel`). */
  idPrefix: string;
}) {
  const refs = useRef(new Map<string, HTMLButtonElement>());
  const focusAt = (i: number) => {
    const t = tabs[(i + tabs.length) % tabs.length];
    onChange(t.value);
    refs.current.get(t.value)?.focus();
  };
  return (
    <div
      role="tablist"
      aria-label={label}
      className="no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1 pb-3 pt-1"
      onKeyDown={(e) => {
        const i = tabs.findIndex((t) => t.value === value);
        if (e.key === "ArrowRight") {
          e.preventDefault();
          focusAt(i + 1);
        } else if (e.key === "ArrowLeft") {
          e.preventDefault();
          focusAt(i - 1);
        } else if (e.key === "Home") {
          e.preventDefault();
          focusAt(0);
        } else if (e.key === "End") {
          e.preventDefault();
          focusAt(tabs.length - 1);
        }
      }}
    >
      {tabs.map((t) => {
        const on = t.value === value;
        return (
          <button
            key={t.value}
            ref={(el) => {
              if (el) refs.current.set(t.value, el);
              else refs.current.delete(t.value);
            }}
            type="button"
            role="tab"
            id={`${idPrefix}-tab-${t.value}`}
            aria-selected={on}
            aria-controls={`${idPrefix}-panel`}
            tabIndex={on ? 0 : -1}
            onClick={() => onChange(t.value)}
            className={cn(
              "t-sub flex h-9 shrink-0 items-center gap-2 rounded-full px-3.5 font-medium transition-[background-color,color,box-shadow] duration-300 ease-expo",
              on ? "bg-cream text-ink shadow-[0_10px_24px_-14px_rgb(0_0_0/0.9)]" : "well text-fg-2 hover:text-fg",
            )}
          >
            {t.dot && t.dot !== "none" ? (
              <span
                aria-hidden="true"
                className={cn(
                  "size-1.5 rounded-full",
                  t.dot === "verified" && "bg-lime",
                  t.dot === "move" && "bg-amber",
                  t.dot === "frozen" && "bg-danger",
                  on && t.dot === "move" && "bg-[#b8860b]",
                  on && t.dot === "frozen" && "bg-[#b3261e]",
                  on && t.dot === "verified" && "bg-[#8fa01f]",
                )}
              />
            ) : null}
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

/* ───────────────────────────── Paper ──────────────────────────────── */

/**
 * Cream "paper" — a submitted record rendered like the document it is
 * (reference: the trade-licence render on /ops/kyb). Ink type on cream,
 * mono eyebrow, a dashed stamp in the corner, key / value rows.
 */
export function Paper({
  eyebrow,
  title,
  stamp = "pending",
  stampIcon = "stamp",
  children,
  footer,
  className,
  ...rest
}: {
  eyebrow: ReactNode;
  title: ReactNode;
  stamp?: "pending" | "approved" | "rejected" | "none";
  stampIcon?: IconName;
  children?: ReactNode;
  footer?: ReactNode;
  className?: string;
} & Omit<HTMLAttributes<HTMLElement>, "title">) {
  return (
    <article
      className={cn(
        "relative overflow-hidden rounded-[22px] bg-[#f6f3ec] p-5 text-ink shadow-[0_30px_60px_-30px_rgb(0_0_0/0.9)] sm:p-6",
        className,
      )}
      {...rest}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="t-label text-ink/60">{eyebrow}</p>
          <h3 className="mt-1 break-words text-[18px] font-semibold leading-snug tracking-[-0.02em]">{title}</h3>
        </div>
        {stamp !== "none" ? (
          <span
            aria-hidden="true"
            className={cn(
              "grid size-14 shrink-0 place-items-center rounded-full border-2 border-dashed",
              stamp === "pending" && "border-ink/25 text-ink/45",
              stamp === "approved" && "-rotate-12 border-[#55620e] text-[#55620e]",
              stamp === "rejected" && "-rotate-6 border-[#b3261e] text-[#b3261e]",
            )}
          >
            <Icon name={stampIcon} size={20} />
          </span>
        ) : null}
      </div>
      {children}
      {footer ? (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-ink/10 pt-3">{footer}</div>
      ) : null}
    </article>
  );
}

/** Key / value rows on a paper: mono-free, ink 60% keys, ink values. */
export function PaperRows({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <dl className={cn("t-sub mt-6 grid grid-cols-[minmax(92px,120px)_minmax(0,1fr)] gap-x-4 gap-y-2.5", className)}>
      {children}
    </dl>
  );
}

export function PaperRow({ label, value, mono }: { label: ReactNode; value: ReactNode; mono?: boolean }) {
  const empty = value === null || value === undefined || value === "";
  return (
    <>
      <dt className="text-ink/60">{label}</dt>
      <dd className={cn("min-w-0 break-words font-medium", mono && "t-code font-normal")}>
        {empty ? <span className="font-normal text-ink/60">Not filled</span> : value}
      </dd>
    </>
  );
}

/** The ink "Open" pill used on paper footers. */
export function PaperOpenLink({ doc, label = "Open original" }: { doc: VerifyDoc; label?: string }) {
  if (!doc.url) return null;
  return (
    <a
      href={docFileUrl(doc.url)}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`Open ${doc.filename} in a new tab`}
      className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-full bg-ink px-3 text-[12.5px] font-medium text-cream transition-colors hover:bg-[#1f1f1f]"
    >
      <Icon name="external" size={14} />
      {label}
    </a>
  );
}

const DOC_STAMP: Record<DocStatus, "pending" | "approved" | "rejected"> = {
  pending: "pending",
  approved: "approved",
  rejected: "rejected",
};

function mimeLabel(mime: string | null) {
  if (!mime) return "Number";
  if (mime === "application/pdf") return "PDF";
  if (mime.startsWith("image/")) return mime.slice(6).toUpperCase().replace("JPEG", "JPG");
  return mime.split("/").pop()?.toUpperCase() ?? "File";
}

/**
 * One uploaded document as paper: certificate, file facts, status, the
 * rejection reason when there is one, and (for images) an inline preview.
 */
export function DocPaper({
  doc,
  owner,
  preview = false,
  className,
}: {
  doc: VerifyDoc;
  owner?: ReactNode;
  /** Show the image inline (images only). */
  preview?: boolean;
  className?: string;
}) {
  const [imgFailed, setImgFailed] = useState(false);
  useEffect(() => setImgFailed(false), [doc.id]);
  const src = docFileUrl(doc.url);
  return (
    <Paper
      eyebrow={`${mimeLabel(doc.mimeType)} · ${refId("DOC", doc.id)}`}
      title={doc.certType}
      stamp={DOC_STAMP[doc.status] ?? "pending"}
      stampIcon={doc.status === "approved" ? "check" : doc.status === "rejected" ? "close" : "stamp"}
      className={className}
      footer={
        doc.hasFile ? (
          <>
            <span className="t-label text-ink/60">Original opens in a new tab</span>
            <PaperOpenLink doc={doc} />
          </>
        ) : (
          <span className="t-label text-ink/60">Number only — no file attached</span>
        )
      }
    >
      <PaperRows>
        {owner ? <PaperRow label="Company" value={owner} /> : null}
        {doc.hasValue ? <PaperRow label="Number" value={<RevealValue doc={doc} />} /> : null}
        {doc.hasFile ? <PaperRow label="File" value={doc.filename} mono /> : null}
        {doc.hasFile ? (
          <PaperRow label="Type · size" value={`${mimeLabel(doc.mimeType)} · ${fmtBytes(doc.sizeBytes ?? 0)}`} />
        ) : null}
        <PaperRow label="Uploaded" value={fmtDateTime(doc.uploadedAt)} />
        <PaperRow
          label="Status"
          value={
            <span className="inline-flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className={cn(
                  "size-1.5 rounded-full",
                  doc.status === "approved" ? "bg-[#8fa01f]" : doc.status === "rejected" ? "bg-[#b3261e]" : "bg-[#b8860b]",
                )}
              />
              {DOC_LABEL[doc.status] ?? doc.status}
            </span>
          }
        />
        {doc.reviewedAt ? <PaperRow label="Reviewed" value={fmtDateTime(doc.reviewedAt)} /> : null}
        {doc.status === "rejected" && doc.rejectionReason ? (
          <PaperRow label="Reason" value={<span className="text-[#b3261e]">{doc.rejectionReason}</span>} />
        ) : null}
      </PaperRows>
      {preview && isImage(doc) ? (
        <div className="mt-5 overflow-hidden rounded-[14px] bg-ink/[0.05] shadow-[inset_0_0_0_1px_rgb(10_10_10/0.08)]">
          {imgFailed ? (
            <p className="t-sub px-4 py-10 text-center text-ink/60">Preview didn&apos;t load — open the original instead.</p>
          ) : (
            <a href={src} target="_blank" rel="noopener noreferrer" className="block" aria-label={`Open ${doc.filename ?? doc.certType} full size`}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={src}
                alt={`${doc.certType}${typeof owner === "string" ? ` uploaded by ${owner}` : ""}`}
                onError={() => setImgFailed(true)}
                className="mx-auto max-h-[440px] w-full object-contain"
              />
            </a>
          )}
        </div>
      ) : null}
    </Paper>
  );
}

/* ───────────────────────────── Key / value ────────────────────────── */

export function KeyValue({
  label,
  value,
  mono,
  wide,
}: {
  label: ReactNode;
  value: ReactNode;
  mono?: boolean;
  wide?: boolean;
}) {
  const empty = value === null || value === undefined || value === "";
  return (
    <div className={cn("min-w-0", wide && "sm:col-span-2")}>
      <dt className="t-label text-fg-3">{label}</dt>
      <dd className={cn("mt-1.5 break-words text-[14.5px] leading-snug text-fg", mono && "t-code text-[13px]")}>
        {empty ? <span className="text-fg-3">—</span> : value}
      </dd>
    </div>
  );
}

export function KeyValueGrid({ children, className }: { children: ReactNode; className?: string }) {
  return <dl className={cn("grid gap-x-8 gap-y-5 sm:grid-cols-2", className)}>{children}</dl>;
}

/* ───────────────────────────── Document card ──────────────────────── */

export function isImage(doc: Pick<VerifyDoc, "mimeType">) {
  return Boolean(doc.mimeType?.startsWith("image/"));
}

/**
 * Masked KYB number with a "Show" control. Revealing calls the API, which
 * writes `kyb.value_viewed` to the audit log — so it's never automatic.
 */
export function RevealValue({ doc, onDark }: { doc: Pick<VerifyDoc, "id" | "valueMasked">; onDark?: boolean }) {
  const [value, setValue] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setValue(null);
    setError(null);
  }, [doc.id]);
  async function toggle() {
    if (value) return setValue(null);
    setBusy(true);
    setError(null);
    try {
      setValue((await adminApi.revealDocValue(doc.id)).value);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn’t show it.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <span className="t-code select-all text-[13px]">{value ?? doc.valueMasked}</span>
      <button
        type="button"
        onClick={toggle}
        disabled={busy}
        title="Viewing the full number is logged"
        className={cn(
          "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-medium",
          onDark ? "bg-cream/10 text-cream hover:bg-cream/20" : "bg-ink/[0.06] text-ink/75 hover:bg-ink/10",
        )}
      >
        <Icon name={value ? "eye-off" : "eye"} size={13} />
        {busy ? "…" : value ? "Hide" : "Show"}
      </button>
      {error ? <span className="text-[12px] text-[#b3261e]">{error}</span> : null}
    </span>
  );
}

/** "Open" — authenticated file in a new tab (admin cookie rides along). */
export function OpenDocLink({ doc, size = "sm" }: { doc: VerifyDoc; size?: "sm" | "md" }) {
  if (!doc.url) return null;
  return (
    <a
      href={docFileUrl(doc.url)}
      target="_blank"
      rel="noopener noreferrer"
      className={buttonClass("secondary", size)}
      aria-label={`Open ${doc.filename} in a new tab`}
    >
      <Icon name="external" size={15} />
      Open
    </a>
  );
}

/**
 * A document as a passport stamp (reference: /passport stamps): dashed
 * seal, status chip, certificate, file, and the actions underneath.
 */
export function DocCard({ doc, actions }: { doc: VerifyDoc; actions?: ReactNode }) {
  const tone = DOC_TONE[doc.status] ?? "quiet";
  return (
    <article
      className={cn(
        "relief relative flex min-h-[188px] w-full flex-col overflow-hidden rounded-[26px] p-5",
        doc.status === "pending" && "shadow-[var(--relief),inset_0_0_0_1.5px_var(--c-amber)]",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <span
          aria-hidden="true"
          className={cn(
            "grid size-[60px] shrink-0 place-items-center rounded-full border-[2.5px] border-dashed",
            tone === "verified" && "-rotate-12 border-accent text-accent",
            tone === "move" && "border-amber text-amber",
            tone === "frozen" && "-rotate-6 border-danger text-danger",
          )}
        >
          <Icon name={isImage(doc) ? "image" : "doc-check"} size={22} />
        </span>
        <DocStatusChip status={doc.status} />
      </div>
      <p className="t-headline mt-5 break-words text-fg">{doc.certType}</p>
      {doc.hasValue ? (
        <p className="t-sub mt-1 text-fg-2">
          <RevealValue doc={doc} onDark />
        </p>
      ) : null}
      {doc.hasFile ? (
        <p className="t-sub mt-0.5 truncate text-fg-3" title={doc.filename ?? undefined}>
          {doc.filename}
        </p>
      ) : null}
      <p className="t-code mt-auto pt-4 text-fg-2">
        {doc.hasFile ? `${fmtBytes(doc.sizeBytes ?? 0)} · ` : ""}
        {fmtDate(doc.uploadedAt)}
      </p>
      {doc.status === "rejected" && doc.rejectionReason ? (
        <p className="t-sub mt-3 rounded-[14px] bg-danger-soft px-3 py-2 text-danger">
          <span className="font-medium">Reason · </span>
          {doc.rejectionReason}
        </p>
      ) : null}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <OpenDocLink doc={doc} />
        {actions}
      </div>
    </article>
  );
}
