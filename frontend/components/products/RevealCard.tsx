"use client";

import { useState, type ReactNode } from "react";
import { Chip } from "@/components/ui/Chip";
import { Icon, type IconName } from "@/components/ui/Icon";
import { SolidPanel } from "@/components/ui/Surface";
import { entityTypeLabel, type RevealedContact } from "@/lib/api";

/**
 * The seller's identity once a verified buyer reveals it. Solid — this is
 * certain, verified identity. Reused later by a "My reveals" list.
 */
export function RevealCard({ contact }: { contact: RevealedContact }) {
  const revealedAt = formatWhen(contact.revealedAt);
  const address = [contact.addressLine, contact.city, contact.state, contact.pincode, contact.country]
    .filter(Boolean)
    .join(", ");
  const website = contact.websiteUrl
    ? /^https?:\/\//i.test(contact.websiteUrl)
      ? contact.websiteUrl
      : `https://${contact.websiteUrl}`
    : null;

  return (
    <SolidPanel className="p-6 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Chip tone="verified">Contact open</Chip>
        {revealedAt ? <span className="t-code text-fg-3">Opened {revealedAt}</span> : null}
      </div>

      <p className="t-label mt-6 text-fg-3">Seller</p>
      <h3 className="t-title2 mt-1.5 break-words text-fg">{contact.businessName || "Verified seller"}</h3>
      {contact.entityType ? <p className="t-sub mt-1 text-fg-2">{entityTypeLabel(contact.entityType)}</p> : null}

      <dl className="mt-6 space-y-1">
        {contact.fullName ? <Row icon="user" label="Contact person" value={contact.fullName} /> : null}
        {contact.email ? (
          <Row
            icon="mail"
            label="Email"
            value={contact.email}
            href={`mailto:${contact.email}`}
            copy={contact.email}
          />
        ) : null}
        {address ? <Row icon="pin" label="Address" value={address} copy={address} wrap /> : null}
        {website ? (
          <Row
            icon="globe"
            label="Website"
            value={contact.websiteUrl as string}
            href={website}
            external
          />
        ) : null}
      </dl>

      <p className="t-foot mt-6 text-fg-3">
        Saved to your account. Opening it again doesn&rsquo;t count toward your hourly limit.
      </p>
    </SolidPanel>
  );
}

function Row({
  icon,
  label,
  value,
  href,
  external,
  copy,
  wrap,
}: {
  icon: IconName;
  label: string;
  value: string;
  href?: string;
  external?: boolean;
  copy?: string;
  wrap?: boolean;
}) {
  const body: ReactNode = href ? (
    <a
      href={href}
      {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      className="inline-flex max-w-full items-center gap-1.5 text-fg underline decoration-[var(--c-line-2)] underline-offset-4 transition-colors hover:decoration-[var(--c-fg)]"
    >
      <span className={wrap ? "break-words" : "truncate"}>{value}</span>
      {external ? <Icon name="external" size={14} className="shrink-0 text-fg-3" /> : null}
    </a>
  ) : (
    <span className={wrap ? "break-words" : "block truncate"}>{value}</span>
  );

  return (
    <div className="flex items-start gap-3 rounded-[16px] px-1 py-2.5">
      <span className="relief-sm mt-0.5 grid size-9 shrink-0 place-items-center rounded-full text-fg-2">
        <Icon name={icon} size={16} />
      </span>
      <div className="min-w-0 flex-1">
        <dt className="t-label text-fg-3">{label}</dt>
        <dd className="mt-1 text-[15px] text-fg">{body}</dd>
      </div>
      {copy ? <CopyButton value={copy} label={label} /> : null}
    </div>
  );
}

function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1400);
        } catch {
          /* clipboard blocked — nothing to do */
        }
      }}
      aria-label={copied ? `${label} copied` : `Copy ${label.toLowerCase()}`}
      title={copied ? "Copied" : "Copy"}
      className="grid size-9 shrink-0 place-items-center rounded-full text-fg-3 transition-colors hover:bg-white/5 hover:text-fg"
    >
      <Icon name={copied ? "check" : "doc-check"} size={16} />
    </button>
  );
}

function formatWhen(iso: string): string | null {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}
