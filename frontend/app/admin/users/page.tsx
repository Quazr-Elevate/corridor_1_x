"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  adminApi,
  errorMessage,
  USER_STATUS_LABEL,
  USER_STATUSES,
  type UserRow,
  type UsersListOut,
} from "@/lib/adminApi";
import { cn } from "@/lib/cn";
import { Stagger, StaggerItem } from "@/components/motion";
import { Button } from "@/components/ui/Button";
import { Segmented, type SegmentOption } from "@/components/ui/Controls";
import { Icon } from "@/components/ui/Icon";
import { Card, EmptyState, Notice, Skeleton } from "@/components/ui/Surface";
import { LaneHeader } from "@/components/admin/tower";
import { StatusChip } from "@/components/admin/parts";
import { fmtAgo, fmtDate, refId } from "@/components/admin/format";

const LIMIT = 50;

type StatusFilter = "all" | (typeof USER_STATUSES)[number];

const STATUS_OPTIONS: ReadonlyArray<SegmentOption<StatusFilter>> = [
  { value: "all", label: "All" },
  ...USER_STATUSES.map((s) => ({ value: s, label: USER_STATUS_LABEL[s] })),
];

function useDebounced<T>(value: T, ms = 250) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** `?status=` / `?q=` — so tower tiles and charts can deep-link a filter. */
function initialParams(): { status: StatusFilter; q: string } {
  if (typeof window === "undefined") return { status: "all", q: "" };
  const sp = new URLSearchParams(window.location.search);
  const s = sp.get("status");
  return {
    status: s && (USER_STATUSES as readonly string[]).includes(s) ? (s as StatusFilter) : "all",
    q: sp.get("q") ?? "",
  };
}

export default function DirectoryPage() {
  const router = useRouter();
  const [initial] = useState(initialParams);
  const [q, setQ] = useState(initial.q);
  const query = useDebounced(q.trim());
  const [status, setStatus] = useState<StatusFilter>(initial.status);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<UsersListOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  // New filter → back to the first page.
  useEffect(() => setOffset(0), [query, status]);

  // Keep the address in step with the filter (shareable, survives reload).
  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    if (status === "all") sp.delete("status");
    else sp.set("status", status);
    if (query) sp.set("q", query);
    else sp.delete("q");
    const qs = sp.toString();
    const next = `${window.location.pathname}${qs ? `?${qs}` : ""}`;
    if (next !== `${window.location.pathname}${window.location.search}`) {
      window.history.replaceState(window.history.state, "", next);
    }
  }, [status, query]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    adminApi
      .users({ q: query || undefined, status: status === "all" ? undefined : status, limit: LIMIT, offset })
      .then((res) => {
        if (cancelled) return;
        setData(res);
        setErr(null);
      })
      .catch((e) => !cancelled && setErr(errorMessage(e, "Couldn't load the directory.")))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [query, status, offset, nonce]);

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const from = total ? offset + 1 : 0;
  const to = Math.min(offset + LIMIT, total);
  const filtered = query !== "" || status !== "all";

  return (
    <div className="pt-4">
      <LaneHeader
        eyebrow="Lane · Accounts"
        title="Directory"
        subtitle={
          data
            ? `${total.toLocaleString("en-GB")} ${filtered ? "matching " : ""}account${total === 1 ? "" : "s"}${
                status !== "all" ? ` · ${USER_STATUS_LABEL[status]}` : ""
              }.`
            : "Every account on the corridor."
        }
        actions={
          <label className="well flex h-10 w-full items-center gap-2 rounded-full px-4 text-fg-3 focus-within:shadow-[var(--well),0_0_0_1px_var(--c-fg),0_0_0_4px_rgb(196_216_46/0.25)] sm:w-[300px]">
            <Icon name="search" size={16} />
            <span className="sr-only">Search accounts</span>
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Email or business name"
              className="min-w-0 flex-1 bg-transparent text-[15px] text-fg outline-none placeholder:text-fg-3"
            />
            {loading && data ? (
              <svg width="14" height="14" viewBox="0 0 24 24" className="shrink-0 animate-spin" aria-hidden="true">
                <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity=".25" strokeWidth="2.5" />
                <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
              </svg>
            ) : null}
          </label>
        }
      />

      <div className="mt-6 max-w-full">
        <Segmented<StatusFilter> label="Filter by status" size="sm" value={status} onChange={setStatus} options={STATUS_OPTIONS} />
      </div>

      {err ? (
        <div className="mt-6">
          <Notice
            tone="frozen"
            title="Couldn't load the directory"
            action={
              <Button variant="secondary" size="sm" onClick={() => setNonce((n) => n + 1)}>
                Try again
              </Button>
            }
          >
            {err}
          </Notice>
        </div>
      ) : null}

      <div className="mt-6" aria-busy={loading}>
        {loading && !data ? (
          <div className="relief overflow-hidden rounded-[28px] p-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="mt-2 h-12 rounded-[14px] first:mt-0" />
            ))}
          </div>
        ) : items.length === 0 && !err ? (
          <Card className="rounded-[28px] p-2">
            <EmptyState icon="users" title={filtered ? "No matches" : "No accounts yet"}>
              {filtered ? "Try a shorter search or another status." : "Signups appear here as they arrive."}
            </EmptyState>
          </Card>
        ) : items.length ? (
          <div className={cn("transition-opacity duration-300", loading && "opacity-60")}>
            {/* Tablet & desktop: table */}
            <div className="relief hidden overflow-x-auto rounded-[28px] md:block">
              <table className="w-full min-w-[880px] border-collapse text-left">
                <caption className="sr-only">Accounts</caption>
                <thead>
                  <tr className="t-label border-b border-line text-fg-3">
                    <th scope="col" className="px-6 py-3.5 font-normal">Company</th>
                    <th scope="col" className="px-3 py-3.5 font-normal">Ref</th>
                    <th scope="col" className="px-3 py-3.5 font-normal">Status</th>
                    <th scope="col" className="px-3 py-3.5 font-normal">Email</th>
                    <th scope="col" className="px-6 py-3.5 text-right font-normal">Joined</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {items.map((u) => (
                    <tr
                      key={u.userId}
                      onClick={(e) => {
                        if ((e.target as HTMLElement).closest("a")) return;
                        router.push(`/admin/users/${u.userId}`);
                      }}
                      className="t-sub cursor-pointer transition-colors hover:bg-white/[0.03]"
                    >
                      <td className="max-w-[380px] px-6 py-3.5">
                        <Link href={`/admin/users/${u.userId}`} className="block min-w-0 rounded-[10px]">
                          <span className="block truncate font-medium text-fg">{u.businessName || "No business name"}</span>
                          <span className="block truncate text-fg-3">{u.email}</span>
                        </Link>
                      </td>
                      <td className="t-code whitespace-nowrap px-3 text-accent" title={u.userId}>
                        {refId("USR", u.userId)}
                      </td>
                      <td className="px-3">
                        <StatusChip status={u.status} className="h-5 gap-1 px-2 text-[11px]" />
                      </td>
                      <td className="px-3">
                        <YesNo yes={u.emailVerified} yesLabel="Confirmed" noLabel="Unconfirmed" />
                      </td>
                      <td className="whitespace-nowrap px-6 text-right">
                        <span className="block text-fg-2">{fmtDate(u.createdAt)}</span>
                        <span className="t-foot block text-fg-3">{fmtAgo(u.createdAt)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Phone: cards */}
            <Stagger as="ul" className="flex flex-col gap-2.5 md:hidden">
              {items.map((u) => (
                <MobileRow key={u.userId} u={u} />
              ))}
            </Stagger>
          </div>
        ) : null}
      </div>

      {total > LIMIT ? (
        <nav aria-label="Pages" className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <p className="t-code tabular text-fg-3">
            {from}–{to} of {total.toLocaleString("en-GB")}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              icon="arrow-left"
              disabled={offset === 0 || loading}
              onClick={() => setOffset((o) => Math.max(0, o - LIMIT))}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              size="sm"
              iconRight="arrow-right"
              disabled={offset + LIMIT >= total || loading}
              onClick={() => setOffset((o) => o + LIMIT)}
            >
              Next
            </Button>
          </div>
        </nav>
      ) : null}
    </div>
  );
}

function YesNo({ yes, yesLabel, noLabel }: { yes: boolean; yesLabel: string; noLabel: string }) {
  return yes ? (
    <span className="t-sub inline-flex items-center gap-1.5 whitespace-nowrap text-fg-2">
      <Icon name="check" size={14} strokeWidth={2} className="text-accent" />
      {yesLabel}
    </span>
  ) : (
    <span className="t-sub whitespace-nowrap text-fg-3">{noLabel}</span>
  );
}

function MobileRow({ u }: { u: UserRow }) {
  return (
    <StaggerItem as="li">
      <Link href={`/admin/users/${u.userId}`} className="relief-sm block rounded-[22px] p-4 transition-shadow duration-300 hover:shadow-[var(--relief)]">
        <div className="flex items-center justify-between gap-3">
          <span className="t-code text-accent">{refId("USR", u.userId)}</span>
          <StatusChip status={u.status} className="h-5 gap-1 px-2 text-[11px]" />
        </div>
        <p className="t-headline mt-1.5 truncate text-fg">{u.businessName || "No business name"}</p>
        <p className="t-sub mt-0.5 truncate text-fg-3">{u.email}</p>
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1">
          <YesNo yes={u.emailVerified} yesLabel="Email confirmed" noLabel="Email unconfirmed" />
          <span className="t-foot ml-auto text-fg-3">{fmtDate(u.createdAt)}</span>
        </div>
      </Link>
    </StaggerItem>
  );
}
