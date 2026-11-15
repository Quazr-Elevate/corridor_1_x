"use client";

import { Icon } from "@/components/ui/Icon";
import { assetUrl } from "@/lib/api";
import type { PublicCertificate } from "@/lib/publicApi";
import { useMe } from "@/lib/useMe";

/**
 * Documents an admin approved for download. Everyone sees which documents
 * exist; only a signed-in, verified business can open one (the API refuses
 * anyone else, and logs each download).
 */
export function CertificateLinks({ certificates }: { certificates: PublicCertificate[] }) {
  const { me, loading } = useMe();
  const canOpen = me?.verification.status === "verified";
  return (
    <>
      <ul className="mt-4 space-y-2">
        {certificates.map((c) => (
          <li key={c.id}>
            {canOpen ? (
              <a
                href={assetUrl(c.url)}
                target="_blank"
                rel="noopener noreferrer"
                className="relief-sm t-body flex items-center justify-between gap-3 rounded-[16px] px-4 py-3 text-fg transition-shadow duration-300 ease-expo hover:shadow-[var(--relief)]"
              >
                <span className="flex min-w-0 items-center gap-2.5">
                  <Icon name="doc-check" size={16} className="shrink-0 text-accent" />
                  <span className="truncate">{c.name}</span>
                </span>
                <Icon name="external" size={15} className="shrink-0 text-fg-3" />
              </a>
            ) : (
              <span className="well t-body flex items-center gap-2.5 rounded-[16px] px-4 py-3 text-fg-2">
                <Icon name="doc-check" size={16} className="shrink-0 text-fg-3" />
                <span className="truncate">{c.name}</span>
              </span>
            )}
          </li>
        ))}
      </ul>
      {!loading && !canOpen ? (
        <p className="t-sub mt-3 text-fg-3">Verified businesses can open these documents. Each download is logged.</p>
      ) : null}
    </>
  );
}
