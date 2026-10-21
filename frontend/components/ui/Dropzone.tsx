"use client";

import { useId, useRef, useState, type DragEvent, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { FieldShell } from "./Field";
import { Icon, type IconName } from "./Icon";

/**
 * Dropzone — a sunk well you drop files into, or press to browse. The
 * control is a real button (Enter / Space open the picker); the label,
 * hint and error come from FieldShell. Files are checked against
 * `accept`, `maxBytes` and `multiple`/`maxFiles` before `onFiles` runs;
 * anything refused goes to `onReject` and is explained under the well.
 *
 *   <Dropzone label="Trade licence" accept=".pdf,image/*"
 *             maxBytes={10 * 1024 * 1024} onFiles={upload} />
 */

export interface DropzoneRejection {
  file: File;
  reason: "type" | "size" | "count";
  message: string;
}

export interface DropzoneProps {
  onFiles: (files: File[]) => void;
  onReject?: (rejections: DropzoneRejection[]) => void;
  /** Same syntax as <input accept>: ".pdf,image/*,application/pdf". */
  accept?: string;
  /** Per-file limit in bytes. */
  maxBytes?: number;
  multiple?: boolean;
  /** With `multiple`: most files taken from one drop. */
  maxFiles?: number;
  disabled?: boolean;
  /** Uploading — shows a spinner and blocks new files. */
  busy?: boolean;
  label?: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  required?: boolean;
  optional?: boolean;
  /** Headline inside the well. */
  title?: ReactNode;
  /** Line under the headline. Default: accepted types · size limit. */
  description?: ReactNode;
  icon?: IconName;
  size?: "sm" | "md";
  id?: string;
  name?: string;
  className?: string;
}

export function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  const mb = n / (1024 * 1024);
  return `${mb >= 10 || Number.isInteger(mb) ? Math.round(mb) : mb.toFixed(1)} MB`;
}

function describeAccept(accept?: string) {
  if (!accept) return null;
  const parts = accept
    .split(",")
    .map((t) => t.trim().toLowerCase())
    .filter(Boolean)
    .map((t) => {
      if (t.startsWith(".")) return t.slice(1).toUpperCase();
      if (t === "image/*") return "Images";
      if (t === "application/pdf") return "PDF";
      if (t.endsWith("/*")) return t.slice(0, -2).replace(/^\w/, (c) => c.toUpperCase());
      const sub = t.split("/")[1];
      return sub ? sub.toUpperCase() : t;
    });
  return Array.from(new Set(parts.map((p) => (p === "JPEG" ? "JPG" : p)))).join(", ");
}

function matchesAccept(file: File, accept?: string) {
  if (!accept) return true;
  const name = file.name.toLowerCase();
  const type = (file.type || "").toLowerCase();
  return accept
    .split(",")
    .map((t) => t.trim().toLowerCase())
    .filter(Boolean)
    .some((t) => {
      if (t.startsWith(".")) return name.endsWith(t);
      if (t.endsWith("/*")) return type.startsWith(t.slice(0, -1));
      return type === t;
    });
}

export function Dropzone({
  onFiles,
  onReject,
  accept,
  maxBytes,
  multiple,
  maxFiles,
  disabled,
  busy,
  label,
  hint,
  error,
  required,
  optional,
  title,
  description,
  icon = "upload",
  size = "md",
  id,
  name,
  className,
}: DropzoneProps) {
  const auto = useId();
  const buttonId = id ?? `${auto}-drop`;
  const descId = `${auto}-desc`;
  const inputRef = useRef<HTMLInputElement>(null);
  const depth = useRef(0);
  const [dragging, setDragging] = useState(false);
  const [local, setLocal] = useState<string | null>(null);

  const blocked = disabled || busy;
  const types = describeAccept(accept);
  const limit = maxBytes ? `up to ${formatBytes(maxBytes)}` : null;
  const desc = description ?? ([types, limit].filter(Boolean).join(" · ") || "Any file");

  const take = (list: FileList | null) => {
    if (!list || !list.length || blocked) return;
    const files = Array.from(list);
    const ok: File[] = [];
    const bad: DropzoneRejection[] = [];
    const cap = multiple ? maxFiles ?? Infinity : 1;
    for (const f of files) {
      if (!matchesAccept(f, accept)) {
        bad.push({ file: f, reason: "type", message: `${f.name} isn't an accepted type${types ? ` (${types})` : ""}.` });
      } else if (maxBytes && f.size > maxBytes) {
        bad.push({ file: f, reason: "size", message: `${f.name} is ${formatBytes(f.size)} — the limit is ${formatBytes(maxBytes)}.` });
      } else if (ok.length >= cap) {
        bad.push({
          file: f,
          reason: "count",
          message: multiple ? `Only ${cap} files at a time.` : "One file at a time — the first was kept.",
        });
      } else {
        ok.push(f);
      }
    }
    setLocal(bad.length ? bad[0].message + (bad.length > 1 ? ` (+${bad.length - 1} more)` : "") : null);
    if (bad.length) onReject?.(bad);
    if (ok.length) onFiles(ok);
  };

  const hasFiles = (e: DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes("Files");

  const onDragEnter = (e: DragEvent<HTMLDivElement>) => {
    if (blocked || !hasFiles(e)) return;
    e.preventDefault();
    depth.current += 1;
    setDragging(true);
  };
  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    if (blocked || !hasFiles(e)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  };
  const onDragLeave = (e: DragEvent<HTMLDivElement>) => {
    if (blocked) return;
    depth.current = Math.max(0, depth.current - 1);
    if (depth.current === 0) setDragging(false);
    e.preventDefault();
  };
  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    if (blocked) return;
    e.preventDefault();
    depth.current = 0;
    setDragging(false);
    take(e.dataTransfer.files);
  };

  const shownError = error ?? local;
  const sm = size === "sm";

  return (
    <FieldShell
      label={label}
      hint={hint}
      error={shownError}
      optional={optional}
      required={required}
      htmlFor={buttonId}
      className={className}
    >
      <div
        onDragEnter={onDragEnter}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={cn(
          "well relative rounded-[22px] transition-[box-shadow,background-color] duration-300 ease-expo",
          dragging && "bg-surface-3 shadow-[var(--well),0_0_0_1px_var(--c-fg),0_0_0_5px_rgb(196_216_46/0.35)]",
          shownError && !dragging && "shadow-[var(--well),0_0_0_1px_var(--c-danger)]",
          blocked && "opacity-60",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          name={name}
          accept={accept}
          multiple={multiple}
          disabled={blocked}
          tabIndex={-1}
          aria-hidden="true"
          className="sr-only"
          onChange={(e) => {
            take(e.target.files);
            // Allow picking the same file again.
            e.target.value = "";
          }}
        />
        <button
          id={buttonId}
          type="button"
          disabled={blocked}
          aria-describedby={descId}
          aria-busy={busy || undefined}
          onClick={() => inputRef.current?.click()}
          className={cn(
            "group/drop relative flex w-full rounded-[22px] text-left disabled:cursor-not-allowed",
            sm ? "items-center gap-4 px-4 py-4" : "flex-col items-center gap-3 px-6 py-8 text-center sm:py-10",
          )}
        >
          {/* dashed inner edge */}
          <span
            aria-hidden="true"
            className={cn(
              "pointer-events-none absolute inset-2 rounded-[16px] border-[1.5px] border-dashed transition-colors duration-300 ease-expo",
              dragging ? "border-transparent" : "border-line-2 group-hover/drop:border-fg-3",
            )}
          />
          <span
            className={cn(
              "relative grid shrink-0 place-items-center rounded-full transition-[background-color,box-shadow,color] duration-300 ease-expo",
              sm ? "size-10" : "size-12",
              dragging ? "solid" : "relief-sm text-fg-2 group-hover/drop:text-fg",
            )}
          >
            {busy ? (
              <svg width={18} height={18} viewBox="0 0 24 24" className="animate-spin" aria-hidden="true">
                <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity=".25" strokeWidth="2" />
                <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            ) : (
              <Icon name={icon} size={sm ? 18 : 20} />
            )}
          </span>
          <span className="relative min-w-0">
            <span className="t-headline block text-fg">
              {busy ? (
                "Uploading…"
              ) : dragging ? (
                "Release to add"
              ) : (
                title ?? (
                  <>
                    Drop {multiple ? "files" : "a file"} here or{" "}
                    <span className="underline decoration-line-2 underline-offset-4 group-hover/drop:decoration-fg">browse</span>
                  </>
                )
              )}
            </span>
            <span id={descId} className="t-sub mt-1 block text-fg-3">
              {desc}
            </span>
          </span>
        </button>
      </div>
    </FieldShell>
  );
}
