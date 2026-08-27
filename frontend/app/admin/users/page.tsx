"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, ArrowUpRight, Search } from "lucide-react";
import { AdminShell } from "@/components/admin/AdminShell";
import { adminApi, type UserRow, type UsersListOut } from "@/lib/adminApi";
import { cn } from "@/lib/cn";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "signed_up", label: "Signed up" },
  { value: "verified", label: "Verified" },
];

const STAGE_LABELS: Record<string, string> = {
  signed_up: "Signed up",
  primary_pending: "Primary pending",
  business_pending: "Business pending",
  bank_pending: "Bank pending",
  verified: "Verified",
};

export default function AdminUsersPage() {
  return (
    <AdminShell>
      <Suspense fallback={<p className="text-sm text-paper-muted">Loading…</p>}>
        <UsersBody />
      </Suspense>
    </AdminShell>
  );
}

function UsersBody() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const type = searchParams.get("type") ?? "";
  const status = searchParams.get("status") ?? "";
  const [q, setQ] = useState(searchParams.get("q") ?? "");
  const [data, setData] = useState<UsersListOut | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setErr(null);
    adminApi
      .users({
        type: type === "buyer" || type === "seller" ? type : undefined,
        status: status || undefined,
        q: q.trim() || undefined,
        limit: 100,
      })
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : "Load failed"));
  }, [type, status, q]);

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    router.replace(`/admin/users?${next.toString()}`);
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-paper-muted">
            <span
              aria-hidden
              className="mr-1.5 inline-block h-1 w-1 -translate-y-[2px] rounded-full bg-accent align-middle"
            />
            Admin
          </p>
          <h1 className="mt-2 text-display text-paper">Users</h1>
        </div>
        {data ? (
          <p className="text-xs text-paper-muted">
            {data.total} match{data.total === 1 ? "" : "es"}
          </p>
        ) : null}
      </header>

      {/* Filter row */}
      <div className="surface p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Chip
            label="All"
            active={!type}
            onClick={() => setFilter("type", "")}
          />
          <Chip
            label="Buyers"
            active={type === "buyer"}
            onClick={() => setFilter("type", "buyer")}
            accent="var(--accent)"
          />
          <Chip
            label="Sellers"
            active={type === "seller"}
            onClick={() => setFilter("type", "seller")}
            accent="var(--violet)"
          />

          <span className="mx-2 h-4 w-px bg-line-soft" aria-hidden />

          <select
            value={status}
            onChange={(e) => setFilter("status", e.target.value)}
            className="field h-8 px-2 text-xs"
            style={{ maxWidth: 180 }}
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>

          <div className="ml-auto flex items-center gap-2">
            <Search aria-hidden className="h-3.5 w-3.5 text-paper-muted" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Name, mobile, email, GSTIN, PAN"
              className="field h-8 min-w-[220px] px-2 text-xs"
            />
          </div>
        </div>
      </div>

      {err ? (
        <p className="text-sm text-danger">{err}</p>
      ) : !data ? (
        <p className="text-sm text-paper-muted">Loading…</p>
      ) : data.items.length === 0 ? (
        <p className="text-sm text-paper-muted">
          No users match this filter yet.
        </p>
      ) : (
        <ul className="surface divide-y divide-line-soft overflow-hidden p-0">
          {data.items.map((u) => (
            <UserListItem key={u.userId} u={u} />
          ))}
        </ul>
      )}
    </div>
  );
}

function UserListItem({ u }: { u: UserRow }) {
  return (
    <li>
      <Link
        href={`/admin/users/${u.userId}?view=${u.userType}`}
        className="group flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-ink-elevated"
      >
        <span
          aria-hidden
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line-soft bg-ink text-xs font-semibold text-paper"
        >
          {(u.fullName || u.mobile || "?").slice(0, 2).toUpperCase()}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-paper">
            {u.fullName || u.mobile || "—"}
            <span
              className="ml-1.5 align-middle text-[9px] uppercase tracking-widest"
              style={{
                color:
                  u.userType === "seller" ? "var(--violet)" : "var(--accent)",
              }}
            >
              · {u.userType}
            </span>
          </p>
          <p className="mt-0.5 truncate text-[11px] text-paper-muted">
            {u.mobile ? <>+91 {u.mobile}</> : null}
            {u.email ? <span className="mx-1.5">·</span> : null}
            {u.email ? u.email : null}
            {u.state ? <span className="mx-1.5">·</span> : null}
            {u.state ? u.state : null}
          </p>
        </div>
        <StagePill stage={u.stage} />
        <ArrowUpRight
          aria-hidden
          className="hidden h-4 w-4 shrink-0 text-paper-muted transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-paper sm:inline"
        />
      </Link>
    </li>
  );
}

function StagePill({ stage }: { stage: string }) {
  const verified = stage === "verified";
  return (
    <span
      className={cn(
        "hidden shrink-0 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-widest sm:inline",
        verified
          ? "border-accent/30 bg-accent-soft text-paper"
          : "border-line-soft bg-ink-elevated text-paper-muted",
      )}
    >
      {STAGE_LABELS[stage] ?? stage}
    </span>
  );
}

function Chip({
  label,
  active,
  onClick,
  accent,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  accent?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs transition-colors",
        active
          ? "border-line bg-ink-soft text-paper"
          : "border-line-soft bg-ink-elevated text-paper-muted hover:text-paper",
      )}
      style={
        active && accent
          ? { boxShadow: `inset 0 0 0 1px ${accent}` }
          : undefined
      }
    >
      {label}
      {active ? (
        <ArrowRight aria-hidden className="h-3 w-3" />
      ) : null}
    </button>
  );
}
