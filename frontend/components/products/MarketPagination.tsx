import Link from "next/link";
import { Icon } from "@/components/ui/Icon";
import { cn } from "@/lib/cn";
import type { CatalogFilters } from "@/lib/publicApi";
import { searchParamsFromFilters } from "@/lib/productFilters";

/** Numbered pages for the market grid. Plain links, so it works without JS. */
export function MarketPagination({
  filters,
  total,
  pageSize,
}: {
  filters: CatalogFilters;
  total: number;
  pageSize: number;
}) {
  const pages = Math.ceil(total / pageSize);
  if (pages <= 1) return null;
  const current = Math.min(pages, Math.floor((filters.offset ?? 0) / pageSize) + 1);
  const href = (page: number) =>
    `/products${searchParamsFromFilters({ ...filters, offset: (page - 1) * pageSize })}`;

  // 1 … 4 5 6 … 12
  const nums: Array<number | "gap"> = [];
  for (let p = 1; p <= pages; p++) {
    if (p === 1 || p === pages || Math.abs(p - current) <= 1) nums.push(p);
    else if (nums[nums.length - 1] !== "gap") nums.push("gap");
  }

  const from = (current - 1) * pageSize + 1;
  const to = Math.min(total, current * pageSize);

  return (
    <nav aria-label="Market pages" className="mt-10 flex flex-col items-center gap-4">
      <div className="flex items-center gap-2">
        <PageArrow dir="prev" href={current > 1 ? href(current - 1) : null} />
        <ol className="well flex items-center gap-1 rounded-full p-1">
          {nums.map((n, k) =>
            n === "gap" ? (
              <li key={`gap-${k}`} className="t-code px-1.5 text-fg-3" aria-hidden="true">
                …
              </li>
            ) : (
              <li key={n}>
                <Link
                  href={href(n)}
                  aria-current={n === current ? "page" : undefined}
                  aria-label={`Page ${n}`}
                  className={cn(
                    "t-code grid h-9 min-w-9 place-items-center rounded-full px-2.5 transition-colors duration-300",
                    n === current ? "relief-sm text-fg" : "text-fg-3 hover:text-fg",
                  )}
                >
                  {n}
                </Link>
              </li>
            ),
          )}
        </ol>
        <PageArrow dir="next" href={current < pages ? href(current + 1) : null} />
      </div>
      <p className="t-code text-fg-3">
        {from}–{to} of {total}
      </p>
    </nav>
  );
}

function PageArrow({ dir, href }: { dir: "prev" | "next"; href: string | null }) {
  const label = dir === "prev" ? "Previous page" : "Next page";
  const icon = <Icon name={dir === "prev" ? "arrow-left" : "arrow-right"} size={16} />;
  // Server component: Button.tsx is a client module, so mirror the
  // secondary button's relief here rather than calling buttonClass().
  const cls =
    "relief-sm grid size-10 place-items-center rounded-full text-fg transition-shadow duration-300 ease-expo hover:shadow-[var(--relief)] aria-disabled:pointer-events-none aria-disabled:opacity-45";
  if (!href) {
    return (
      <span aria-disabled="true" aria-label={label} className={cls}>
        {icon}
      </span>
    );
  }
  return (
    <Link href={href} aria-label={label} className={cls}>
      {icon}
    </Link>
  );
}
