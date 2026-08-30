"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowUpRight, Radio } from "lucide-react";
import { adminApi, type RecentReveal } from "@/lib/adminApi";

/**
 * Recent-reveals feed — verified buyers unlocking seller contacts.
 * Spatial styling; the polished empty state reads as intentional, not broken.
 */
export function RevealsFeed({ limit = 8 }: { limit?: number }) {
  const [items, setItems] = useState<RecentReveal[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    adminApi
      .reveals(limit)
      .then(setItems)
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed"));
  }, [limit]);

  return (
    <section className="sp-surface overflow-hidden">
      <header className="flex items-center justify-between px-5 py-4" style={{ borderBottom: "1px solid var(--sp-border)" }}>
        <div>
          <h2 className="text-[15px] font-semibold" style={{ color: "var(--sp-text)" }}>
            Recent reveals
          </h2>
          <p className="mt-0.5 text-[11.5px]" style={{ color: "var(--sp-text-3)" }}>
            Verified buyers unlocking seller contacts.
          </p>
        </div>
        <span className="flex h-8 w-8 items-center justify-center rounded-[9px]" style={{ background: "var(--sp-lime-06)" }}>
          <Radio className="h-4 w-4" aria-hidden style={{ color: "var(--sp-lime)" }} />
        </span>
      </header>

      {err ? (
        <p className="px-5 py-6 text-xs" style={{ color: "var(--sp-error)" }}>{err}</p>
      ) : items === null ? (
        <p className="px-5 py-6 text-xs" style={{ color: "var(--sp-text-3)" }}>Loading…</p>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-2.5 px-5 py-10 text-center">
          <span className="flex h-9 w-9 items-center justify-center rounded-full" style={{ border: "1px solid var(--sp-border)" }}>
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--sp-text-3)" }} />
          </span>
          <p className="text-[13px] font-medium" style={{ color: "var(--sp-text-2)" }}>No reveals yet</p>
          <p className="max-w-[240px] text-[11.5px]" style={{ color: "var(--sp-text-3)" }}>
            Verified buyers unlocking seller contacts will appear here.
          </p>
        </div>
      ) : (
        <ul>
          {items.map((r, i) => (
            <li
              key={r.revealId}
              className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-5 py-3.5 transition-colors"
              style={{ borderTop: i === 0 ? "none" : "1px solid var(--sp-border)" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--sp-surface-elevated)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <div className="min-w-0">
                <p className="truncate text-[12.5px]" style={{ color: "var(--sp-text)" }}>
                  <Link href={`/admin/users/${r.buyerId}`} className="font-medium hover:underline">
                    {r.buyerName || "(unnamed)"}
                  </Link>{" "}
                  <span style={{ color: "var(--sp-lime)" }}>→</span>{" "}
                  <Link href={`/admin/users/${r.sellerId}`} className="font-medium hover:underline">
                    {r.sellerCompany || "(unknown seller)"}
                  </Link>
                </p>
                <p className="mt-0.5 truncate text-[11px]" style={{ color: "var(--sp-text-3)" }}>
                  {r.productName} · {new Date(r.revealedAt).toLocaleString()}
                </p>
              </div>
              <Link
                href={`/products/${r.productId}`}
                className="inline-flex items-center gap-1 text-[11px] transition-colors"
                style={{ color: "var(--sp-text-3)" }}
              >
                Listing
                <ArrowUpRight aria-hidden className="h-3 w-3" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
