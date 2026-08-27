"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Lock, Package, Plus } from "lucide-react";
import { api, type ProductRead } from "@/lib/api";
import { useMe } from "@/lib/useMe";

export default function ProductsListPage() {
  const { me } = useMe();
  const [items, setItems] = useState<ProductRead[]>([]);
  const [loading, setLoading] = useState(true);

  const unlocked = me?.status === "verified";

  useEffect(() => {
    if (!unlocked) {
      setLoading(false);
      return;
    }
    api
      .listProducts()
      .then((rows) => setItems(rows))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [unlocked]);

  if (!unlocked) {
    return (
      <div className="mx-auto max-w-2xl">
        <header className="mb-6">
          <p className="text-[10px] uppercase tracking-widest text-paper-muted">
            Products
          </p>
          <h1 className="mt-2 text-display text-paper">Add product</h1>
        </header>

        <div className="surface p-6 text-center">
          <span className="mx-auto inline-flex h-10 w-10 items-center justify-center rounded-full border border-line bg-ink-elevated text-paper-muted">
            <Lock className="h-4 w-4" aria-hidden />
          </span>
          <p className="mt-4 text-title text-paper">Verification pending</p>
          <p className="mt-2 text-sm text-paper-muted">
            Complete Primary, Business and Bank details to become a verified user.
            Product listings unlock the moment your status flips to verified.
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            <Link href="/dashboard/profile/primary" className="btn-inline">
              Primary
            </Link>
            <Link href="/dashboard/profile/business" className="btn-inline">
              Business
            </Link>
            <Link href="/dashboard/profile/bank" className="btn-inline">
              Bank
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <header className="mb-6 flex items-baseline justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-paper-muted">
            Products
          </p>
          <h1 className="mt-2 text-display text-paper">Your listings</h1>
        </div>
        <Link href="/dashboard/products/new" className="btn-primary">
          <Plus aria-hidden className="h-4 w-4" />
          Add product
        </Link>
      </header>

      {loading ? (
        <div className="surface p-6">
          <p className="text-sm text-paper-muted">Loading…</p>
        </div>
      ) : items.length === 0 ? (
        <div className="surface p-8 text-center">
          <span className="mx-auto inline-flex h-10 w-10 items-center justify-center rounded-full bg-accent/10 text-accent">
            <Package className="h-4 w-4" aria-hidden />
          </span>
          <p className="mt-4 text-title text-paper">No products yet</p>
          <p className="mt-2 text-sm text-paper-muted">
            Publish your first listing to start attracting verified buyers.
          </p>
          <Link
            href="/dashboard/products/new"
            className="btn-primary mt-5 inline-flex"
          >
            <Plus aria-hidden className="h-4 w-4" />
            Add your first product
          </Link>
        </div>
      ) : (
        <ul className="space-y-3">
          {items.map((p) => (
            <li key={p.id} className="surface p-4">
              <div className="flex items-baseline justify-between gap-4">
                <div>
                  <p className="text-title text-paper">{p.name}</p>
                  <p className="mt-0.5 text-xs text-paper-muted">
                    {p.category}
                    {p.variety ? ` · ${p.variety}` : ""}
                    {p.originState ? ` · ${p.originState}` : ""}
                  </p>
                </div>
                <p className="text-right text-xs text-paper-muted">
                  {p.quantity ? `${p.quantity} ${p.unit}` : "—"}
                  {p.pricePerUnit
                    ? ` · ₹${p.pricePerUnit}/${p.unit}`
                    : ""}
                </p>
              </div>
              {p.description ? (
                <p className="mt-2 line-clamp-2 text-sm text-paper-muted">
                  {p.description}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
