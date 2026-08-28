"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowUpRight, EyeOff } from "lucide-react";
import { adminApi, type RecentReveal } from "@/lib/adminApi";

/**
 * Compact recent-reveals feed for the admin dashboard. Reuses the
 * `/admin/dashboard/reveals` endpoint that already exists from Sprint 3;
 * this component is just presentation.
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
    <section className="rounded-card border border-line-soft bg-ink-soft/40">
      <header className="flex items-center justify-between border-b border-line-soft/60 px-4 py-3">
        <div>
          <h2 className="text-sm font-medium text-paper">Recent reveals</h2>
          <p className="mt-0.5 text-[11px] text-paper-muted">
            Verified buyers unlocking seller contacts.
          </p>
        </div>
      </header>

      {err ? (
        <p className="px-4 py-6 text-xs text-danger">{err}</p>
      ) : items === null ? (
        <p className="px-4 py-6 text-xs text-paper-muted">Loading…</p>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 px-4 py-8 text-center text-xs text-paper-muted">
          <EyeOff className="h-4 w-4 text-paper-muted/60" aria-hidden />
          No reveals yet.
        </div>
      ) : (
        <ul className="divide-y divide-line-soft/40">
          {items.map((r) => (
            <li
              key={r.revealId}
              className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-4 py-3"
            >
              <div className="min-w-0">
                <p className="truncate text-xs text-paper">
                  <Link
                    href={`/admin/users/${r.buyerId}`}
                    className="font-medium hover:text-accent"
                  >
                    {r.buyerName || "(unnamed)"}
                  </Link>{" "}
                  <span className="text-paper-muted">→</span>{" "}
                  <Link
                    href={`/admin/users/${r.sellerId}`}
                    className="font-medium hover:text-accent"
                  >
                    {r.sellerCompany || "(unknown seller)"}
                  </Link>
                </p>
                <p className="mt-0.5 truncate text-[11px] text-paper-muted">
                  {r.productName} · {new Date(r.revealedAt).toLocaleString()}
                </p>
              </div>
              <Link
                href={`/products/${r.productId}`}
                className="inline-flex items-center gap-1 text-[11px] text-paper-muted hover:text-accent"
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
