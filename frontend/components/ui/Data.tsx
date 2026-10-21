import type { CSSProperties, KeyboardEvent, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Icon, type IconName } from "./Icon";
import { Skeleton } from "./Surface";

/* ───────────────────────────── Key / value ──────────────────────────
   Facts about a thing: mono uppercase keys, plain values. Real <dl>
   semantics. `rows` puts key and value side by side (stacked on phones);
   `grid` stacks each pair and flows them into columns. */

export interface KeyValueItem {
  label: ReactNode;
  value: ReactNode;
  /** Render the value in Fragment Mono (IDs, numbers, codes). */
  mono?: boolean;
  hint?: ReactNode;
}

export function KeyValueList({
  items,
  children,
  layout = "rows",
  columns = 2,
  dividers = true,
  className,
}: {
  items?: ReadonlyArray<KeyValueItem>;
  children?: ReactNode;
  layout?: "rows" | "grid";
  /** Columns for `grid` from the `sm` breakpoint up. */
  columns?: 2 | 3 | 4;
  /** Hairlines between rows (`rows` layout only). */
  dividers?: boolean;
  className?: string;
}) {
  return (
    <dl
      data-layout={layout}
      className={cn(
        "group/kv min-w-0",
        layout === "grid" && "grid grid-cols-1 gap-x-8 gap-y-5",
        layout === "grid" && columns === 2 && "sm:grid-cols-2",
        layout === "grid" && columns === 3 && "sm:grid-cols-2 lg:grid-cols-3",
        layout === "grid" && columns === 4 && "sm:grid-cols-2 lg:grid-cols-4",
        layout === "rows" && dividers && "divide-y divide-line",
        className,
      )}
    >
      {items?.map((it, i) => <KeyValue key={i} {...it} />)}
      {children}
    </dl>
  );
}

/** One key/value pair. Use inside <KeyValueList>. */
export function KeyValue({ label, value, mono, hint, className }: KeyValueItem & { className?: string }) {
  const empty = value === null || value === undefined || value === "";
  return (
    <div
      className={cn(
        "min-w-0",
        // rows: side by side from sm, stacked on phones
        "group-data-[layout=rows]/kv:flex group-data-[layout=rows]/kv:flex-col group-data-[layout=rows]/kv:gap-1 group-data-[layout=rows]/kv:py-3",
        "sm:group-data-[layout=rows]/kv:grid sm:group-data-[layout=rows]/kv:grid-cols-[minmax(0,34%)_minmax(0,1fr)] sm:group-data-[layout=rows]/kv:items-baseline sm:group-data-[layout=rows]/kv:gap-6",
        "group-data-[layout=rows]/kv:first:pt-0 group-data-[layout=rows]/kv:last:pb-0",
        className,
      )}
    >
      <dt className="t-label text-fg-3 group-data-[layout=grid]/kv:mb-1.5">{label}</dt>
      <dd className={cn("min-w-0 break-words text-[15px] text-fg", mono && "t-code text-[13.5px]")}>
        {empty ? <span className="text-fg-3">—</span> : value}
        {hint ? <span className="t-sub mt-0.5 block text-fg-3">{hint}</span> : null}
      </dd>
    </div>
  );
}

/* ───────────────────────────── Stat block ───────────────────────────
   A number with a mono label, as <dl>. Accepts any node as the value —
   pass `loading` for a well skeleton of the right size. */

const STAT_SIZE = {
  sm: { value: "t-title3", skeleton: "h-6 w-14" },
  md: { value: "t-title1", skeleton: "h-8 w-20" },
  lg: { value: "t-large", skeleton: "h-10 w-28" },
} as const;

export function StatBlock({
  label,
  value,
  sub,
  icon,
  loading,
  size = "md",
  align = "left",
  className,
  valueClassName,
}: {
  label: ReactNode;
  value?: ReactNode;
  sub?: ReactNode;
  icon?: IconName;
  loading?: boolean;
  size?: "sm" | "md" | "lg";
  align?: "left" | "right";
  className?: string;
  valueClassName?: string;
}) {
  const s = STAT_SIZE[size];
  return (
    <dl className={cn("min-w-0", align === "right" && "text-right", className)}>
      <dt className={cn("t-label flex items-center gap-1.5 text-fg-3", align === "right" && "justify-end")}>
        {icon ? <Icon name={icon} size={13} className="shrink-0" /> : null}
        {label}
      </dt>
      <dd className={cn("tabular mt-2 text-fg", s.value, valueClassName)} aria-busy={loading || undefined}>
        {loading ? <Skeleton className={cn(s.skeleton, "rounded-[10px]", align === "right" && "ml-auto")} /> : value}
      </dd>
      {sub ? <dd className="t-foot mt-1 text-fg-3">{sub}</dd> : null}
    </dl>
  );
}

/* ───────────────────────────── Data table ───────────────────────────
   Minimal and quiet: mono header labels, no zebra, rows lift (surface-3)
   on hover. Scrolls sideways inside its own wrapper on small screens.
   Give it `maxHeight` to scroll vertically with a sticky header. */

export interface DataColumn<T> {
  key: string;
  header: ReactNode;
  cell: (row: T, index: number) => ReactNode;
  align?: "left" | "right" | "center";
  /** CSS width for the column, e.g. "28%" or "160px". */
  width?: string;
  /** Hide the column below a breakpoint. */
  hideBelow?: "sm" | "md" | "lg";
  /** Render cells in Fragment Mono. */
  mono?: boolean;
  className?: string;
  headerClassName?: string;
}

const ALIGN = { left: "text-left", right: "text-right", center: "text-center" } as const;
const HIDE = { sm: "hidden sm:table-cell", md: "hidden md:table-cell", lg: "hidden lg:table-cell" } as const;

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  rowLabel,
  isRowActive,
  caption,
  empty,
  loading,
  loadingRows = 4,
  maxHeight,
  minWidth,
  dense,
  className,
}: {
  columns: ReadonlyArray<DataColumn<T>>;
  rows: ReadonlyArray<T>;
  rowKey: (row: T, index: number) => string;
  /** Makes rows clickable and keyboard-operable (Enter / Space). */
  onRowClick?: (row: T) => void;
  /** Accessible name for a clickable row. */
  rowLabel?: (row: T) => string;
  /** Highlight the current row (e.g. open in a side panel). */
  isRowActive?: (row: T) => boolean;
  /** Screen-reader caption for the table. */
  caption?: string;
  /** Shown in place of rows when there are none. */
  empty?: ReactNode;
  loading?: boolean;
  loadingRows?: number;
  /** Enables vertical scroll + sticky header. */
  maxHeight?: number | string;
  /** Minimum table width (px) before it scrolls sideways. */
  minWidth?: number;
  dense?: boolean;
  className?: string;
}) {
  const sticky = maxHeight !== undefined;
  const pad = dense ? "px-3 py-2.5" : "px-4 py-3.5";
  const wrapStyle: CSSProperties | undefined = sticky ? { maxHeight } : undefined;

  const onKey = (e: KeyboardEvent<HTMLTableRowElement>, row: T) => {
    if (!onRowClick) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onRowClick(row);
    }
  };

  return (
    <div
      className={cn("relative w-full overflow-x-auto overscroll-x-contain", sticky && "overflow-y-auto", className)}
      style={wrapStyle}
    >
      <table
        className="w-full border-separate border-spacing-0 text-[14px]"
        style={minWidth ? { minWidth } : undefined}
      >
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                style={c.width ? { width: c.width } : undefined}
                className={cn(
                  "t-label whitespace-nowrap font-normal text-fg-3 shadow-[inset_0_-1px_0_var(--c-line)]",
                  dense ? "px-3 pb-2.5 pt-1" : "px-4 pb-3 pt-1",
                  ALIGN[c.align ?? "left"],
                  c.hideBelow && HIDE[c.hideBelow],
                  sticky && "sticky top-0 z-[1] bg-surface",
                  c.headerClassName,
                )}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: loadingRows }).map((_, r) => (
              <tr key={`sk-${r}`} aria-hidden="true">
                {columns.map((c, i) => (
                  <td key={c.key} className={cn(pad, c.hideBelow && HIDE[c.hideBelow])}>
                    <Skeleton
                      className={cn("h-4 rounded-[8px]", i === 0 ? "w-[70%]" : "w-[50%]", c.align === "right" && "ml-auto")}
                    />
                  </td>
                ))}
              </tr>
            ))
          ) : rows.length === 0 ? (
            empty ? (
              <tr>
                <td colSpan={columns.length} className="p-0">
                  {empty}
                </td>
              </tr>
            ) : null
          ) : (
            rows.map((row, ri) => {
              const active = isRowActive?.(row) ?? false;
              const clickable = !!onRowClick;
              return (
                <tr
                  key={rowKey(row, ri)}
                  tabIndex={clickable ? 0 : undefined}
                  aria-label={clickable && rowLabel ? rowLabel(row) : undefined}
                  aria-current={active ? "true" : undefined}
                  onClick={clickable ? () => onRowClick(row) : undefined}
                  onKeyDown={clickable ? (e) => onKey(e, row) : undefined}
                  className={cn(
                    "group/row outline-none",
                    // the lifted row hides the hairline under it too
                    "[&:focus-visible+tr>td]:shadow-none [&:hover+tr>td]:shadow-none",
                    active && "[&+tr>td]:shadow-none",
                    clickable && "cursor-pointer",
                  )}
                >
                  {columns.map((c, ci) => (
                    <td
                      key={c.key}
                      className={cn(
                        pad,
                        "align-middle text-fg transition-[background-color,box-shadow] duration-300 ease-expo",
                        // Hairline between rows; corners round only while lifted
                        // (a rounded cell would bend the hairline).
                        ri > 0 && "shadow-[inset_0_1px_0_var(--c-line)]",
                        "group-hover/row:bg-surface-3 group-hover/row:shadow-none",
                        "group-hover/row:first:rounded-l-[14px] group-hover/row:last:rounded-r-[14px]",
                        "group-focus-visible/row:first:rounded-l-[14px] group-focus-visible/row:last:rounded-r-[14px]",
                        active && "bg-surface-3 shadow-none first:rounded-l-[14px] last:rounded-r-[14px]",
                        "group-focus-visible/row:bg-surface-3 group-focus-visible/row:shadow-[inset_0_2px_0_var(--focus),inset_0_-2px_0_var(--focus)]",
                        ci === 0 &&
                          "group-focus-visible/row:shadow-[inset_2px_0_0_var(--focus),inset_0_2px_0_var(--focus),inset_0_-2px_0_var(--focus)]",
                        ci === columns.length - 1 &&
                          "group-focus-visible/row:shadow-[inset_-2px_0_0_var(--focus),inset_0_2px_0_var(--focus),inset_0_-2px_0_var(--focus)]",
                        ALIGN[c.align ?? "left"],
                        c.mono && "t-code",
                        c.hideBelow && HIDE[c.hideBelow],
                        c.className,
                      )}
                    >
                      {c.cell(row, ri)}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
