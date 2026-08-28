"use client";

import { X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import type { CatalogFacets, CatalogFilters } from "@/lib/publicApi";
import {
  activeFilterCount,
  filtersFromSearchParams,
  searchParamsFromFilters,
} from "@/lib/productFilters";

/**
 * Filter bar for the /products catalog. All state lives in the URL so
 * links / back-button / share behave. The `facets` prop drives which
 * chips are shown — no filter for a category that has zero listings.
 */
export function ProductFilters({ facets }: { facets: CatalogFacets }) {
  const router = useRouter();
  const sp = useSearchParams();
  const [pending, startTransition] = useTransition();

  const current = useMemo(
    () => filtersFromSearchParams(new URLSearchParams(sp.toString())),
    [sp],
  );

  const push = (patch: Partial<CatalogFilters>) => {
    const next = { ...current, ...patch, offset: 0 };
    // Undefined patch values clear the key
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === "") {
        delete (next as Record<string, unknown>)[k];
      }
    }
    startTransition(() => {
      router.replace(`/products${searchParamsFromFilters(next)}`);
    });
  };

  const [q, setQ] = useState(current.q || "");
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    push({ q: q.trim() || undefined });
  };

  const active = activeFilterCount(current);

  return (
    <div className="space-y-3">
      <form onSubmit={submit} className="field-row" data-invalid={undefined}>
        <input
          className="field"
          type="search"
          placeholder="Search by name or description"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button
          type="submit"
          className="btn-inline"
          disabled={pending}
        >
          Search
        </button>
      </form>

      <div className="-mx-1 flex flex-wrap items-center gap-2 px-1">
        {facets.categories.map((c) => (
          <FilterChip
            key={`cat-${c.value}`}
            label={`${c.value} · ${c.count}`}
            active={current.category === c.value}
            onClick={() =>
              push({
                category: current.category === c.value ? undefined : c.value,
              })
            }
          />
        ))}
        {facets.originStates.slice(0, 6).map((s) => (
          <FilterChip
            key={`state-${s.value}`}
            label={`${s.value} · ${s.count}`}
            active={current.originState === s.value}
            onClick={() =>
              push({
                originState:
                  current.originState === s.value ? undefined : s.value,
              })
            }
          />
        ))}
        {active > 0 && (
          <button
            type="button"
            onClick={() => {
              setQ("");
              startTransition(() => router.replace("/products"));
            }}
            className="ml-1 inline-flex items-center gap-1 rounded-full border border-line px-2.5 py-1 text-[11px] text-paper-muted transition-colors hover:text-paper"
          >
            <X aria-hidden className="h-3 w-3" />
            Clear {active}
          </button>
        )}
      </div>
    </div>
  );
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "rounded-full px-2.5 py-1 text-[11px] font-medium uppercase tracking-widest transition-colors " +
        (active
          ? "bg-accent text-accent-fg"
          : "border border-line-soft text-paper-muted hover:border-line hover:text-paper")
      }
    >
      {label}
    </button>
  );
}
