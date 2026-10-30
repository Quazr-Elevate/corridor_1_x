"use client";

import { useRef, useState } from "react";
import { api, ApiError, assetUrl } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";

const ACCEPT = "image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp";
const MAX_MB = 5;

type Slot = "logo" | "banner";

/**
 * Business image + banner. Both are public — they make the dashboard hero
 * (and later the company page) look like the business's own site.
 */
export function BrandingSection({
  logoUrl,
  bannerUrl,
  companyName,
  onChanged,
}: {
  logoUrl: string | null;
  bannerUrl: string | null;
  companyName: string;
  onChanged: () => void | Promise<void>;
}) {
  return (
    <div className="grid gap-4 md:grid-cols-[220px_minmax(0,1fr)]">
      <ImageSlot slot="logo" url={logoUrl} label="Business image" hint="Square logo · JPG, PNG or WEBP · 5 MB" onChanged={onChanged}>
        {(src) =>
          src ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={src} alt={`${companyName} logo`} className="size-full object-cover" />
          ) : (
            <span className="t-title1 text-fg-3">{initials(companyName)}</span>
          )
        }
      </ImageSlot>
      <ImageSlot slot="banner" url={bannerUrl} label="Banner" hint="Wide image, about 3:1 · JPG, PNG or WEBP · 5 MB" onChanged={onChanged} wide>
        {(src) =>
          src ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={src} alt={`${companyName} banner`} className="size-full object-cover" />
          ) : (
            <span className="t-sub flex items-center gap-2 text-fg-3">
              <Icon name="image" size={18} /> No banner yet
            </span>
          )
        }
      </ImageSlot>
    </div>
  );
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return (parts[0]?.[0] ?? "").concat(parts[1]?.[0] ?? "").toUpperCase() || "—";
}

function ImageSlot({
  slot,
  url,
  label,
  hint,
  wide,
  onChanged,
  children,
}: {
  slot: Slot;
  url: string | null;
  label: string;
  hint: string;
  wide?: boolean;
  onChanged: () => void | Promise<void>;
  children: (src: string | null) => React.ReactNode;
}) {
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"upload" | "remove" | null>(null);

  async function upload(file: File) {
    if (file.size > MAX_MB * 1024 * 1024) return toast(`Image must be under ${MAX_MB} MB.`, "frozen");
    setBusy("upload");
    try {
      await api.uploadBranding(slot, file);
      await onChanged();
      toast(`${label} updated`, "verified");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Upload failed. Try again.", "frozen");
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    setBusy("remove");
    try {
      await api.deleteBranding(slot);
      await onChanged();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Couldn’t remove it.", "frozen");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <p className="t-label mb-2 text-fg-3">
        {label} <span className="ml-1 normal-case tracking-normal">optional</span>
      </p>
      <button
        type="button"
        onClick={() => input.current?.click()}
        className={cn(
          "well group relative grid w-full place-items-center overflow-hidden rounded-[22px] transition-shadow",
          wide ? "aspect-[3/1]" : "aspect-square",
        )}
        aria-label={url ? `Replace ${label.toLowerCase()}` : `Upload ${label.toLowerCase()}`}
      >
        {children(url ? assetUrl(url) : null)}
        <span className="absolute inset-x-0 bottom-0 flex items-center justify-center gap-1.5 bg-ink/55 py-2 text-[13px] font-medium text-cream opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
          <Icon name="upload" size={14} /> {url ? "Replace" : "Upload"}
        </span>
      </button>
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        className="sr-only"
        onChange={(e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (f) void upload(f);
        }}
      />
      <div className="mt-2 flex items-center justify-between gap-2">
        <p className="t-sub text-fg-3">{hint}</p>
        {url ? (
          <Button size="sm" variant="quiet" loading={busy === "remove"} onClick={remove}>
            Remove
          </Button>
        ) : busy === "upload" ? (
          <span className="t-sub text-fg-3">Uploading…</span>
        ) : null}
      </div>
    </div>
  );
}
