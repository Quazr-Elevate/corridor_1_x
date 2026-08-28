"use client";

import { useState } from "react";
import {
  Building2,
  Check,
  CheckCircle2,
  Copy,
  Globe,
  Mail,
  MapPin,
  Phone,
} from "lucide-react";
import type { RevealedContact } from "@/lib/api";

/**
 * Shown after a verified buyer clicks Reveal. Reused by:
 *   - ContactGate (product detail today)
 *   - Dashboard "My reveals" tab (Sprint 4+)
 *
 * Every actionable field (phone, email, address) has a copy button so
 * the buyer can paste into their CRM without manual selection.
 */
export function RevealCard({ contact }: { contact: RevealedContact }) {
  const revealedAt = new Date(contact.revealedAt).toLocaleString();
  const fullAddress = [
    contact.addressLine,
    contact.city,
    contact.state,
    contact.pincode,
    contact.country,
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <div
      className="rounded-card border border-line-soft bg-ink-soft/60 p-5 backdrop-blur-sm"
      style={{
        boxShadow:
          "0 0 0 1px rgba(211,236,75,0.28), 0 12px 32px -12px rgba(211,236,75,0.35), 0 0 40px -12px rgba(139,92,246,0.25)",
      }}
    >
      <header className="flex items-start gap-3">
        <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/15 ring-1 ring-inset ring-accent/40">
          <CheckCircle2 aria-hidden className="h-4 w-4 text-accent" />
        </span>
        <div className="flex-1">
          <h3 className="text-sm font-medium text-paper">Contact revealed</h3>
          <p className="mt-1 text-[11px] text-paper-muted">
            First revealed {revealedAt} · saved to your account, no need to
            unlock again.
          </p>
        </div>
      </header>

      <div className="mt-4 space-y-3">
        {contact.companyName && (
          <Line
            icon={<Building2 className="h-3.5 w-3.5 text-accent" />}
            label="Company"
            value={
              contact.businessType
                ? `${contact.companyName} · ${contact.businessType}`
                : contact.companyName
            }
          />
        )}
        {contact.fullName && (
          <Line
            icon={<span className="text-[10px] text-accent">👤</span>}
            label="Contact"
            value={contact.fullName}
          />
        )}
        {contact.mobile && (
          <Line
            icon={<Phone className="h-3.5 w-3.5 text-accent" />}
            label="Phone"
            value={contact.mobile}
            copyable
            href={`tel:+91${contact.mobile}`}
          />
        )}
        {contact.email && (
          <Line
            icon={<Mail className="h-3.5 w-3.5 text-accent" />}
            label="Email"
            value={contact.email}
            copyable
            href={`mailto:${contact.email}`}
          />
        )}
        {contact.businessEmail && contact.businessEmail !== contact.email && (
          <Line
            icon={<Mail className="h-3.5 w-3.5 text-accent" />}
            label="Business email"
            value={contact.businessEmail}
            copyable
            href={`mailto:${contact.businessEmail}`}
          />
        )}
        {fullAddress && (
          <Line
            icon={<MapPin className="h-3.5 w-3.5 text-accent" />}
            label="Address"
            value={fullAddress}
            copyable
          />
        )}
        {contact.websiteUrl && (
          <Line
            icon={<Globe className="h-3.5 w-3.5 text-accent" />}
            label="Website"
            value={contact.websiteUrl}
            href={
              contact.websiteUrl.startsWith("http")
                ? contact.websiteUrl
                : `https://${contact.websiteUrl}`
            }
          />
        )}
      </div>

      <p className="mt-4 text-[10px] uppercase tracking-widest text-paper-muted/70">
        Reveal your side to the seller? Not yet — that&apos;s a Sprint-4
        feature. For now they don&apos;t see who unlocked them.
      </p>
    </div>
  );
}

function Line({
  icon,
  label,
  value,
  copyable,
  href,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  copyable?: boolean;
  href?: string;
}) {
  const [copied, setCopied] = useState(false);
  const doCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* clipboard blocked (e.g. insecure origin) — no-op */
    }
  };

  const body = (
    <span className="truncate text-sm text-paper">{value}</span>
  );

  return (
    <div className="flex items-center gap-3 rounded-lg border border-line-soft/60 bg-ink/40 px-3 py-2">
      <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-ink-elevated">
        {icon}
      </span>
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="text-[10px] uppercase tracking-widest text-paper-muted">
          {label}
        </span>
        {href ? (
          <a
            href={href}
            className="truncate text-sm text-paper underline-offset-4 hover:underline"
          >
            {value}
          </a>
        ) : (
          body
        )}
      </div>
      {copyable && (
        <button
          type="button"
          onClick={doCopy}
          className="shrink-0 rounded-md p-1.5 text-paper-muted transition-colors hover:bg-ink-elevated hover:text-paper"
          aria-label={`Copy ${label}`}
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-accent" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </button>
      )}
    </div>
  );
}
