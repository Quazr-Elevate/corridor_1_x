"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowUpRight, Search } from "lucide-react";
import { Rise } from "@/components/admin/spatial";
import { adminApi, type UserRow, type UsersListOut } from "@/lib/adminApi";

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
    <Suspense fallback={<p className="text-sm" style={{ color: "var(--sp-text-3)" }}>Loading…</p>}>
      <UsersBody />
    </Suspense>
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
    <div className="mx-auto max-w-[1100px]">
      <Rise i={0} className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <p className="text-[12px]" style={{ color: "var(--sp-text-3)" }}>Admin console</p>
          <h1 className="mt-1 text-[34px] font-semibold tracking-[-0.025em]" style={{ color: "var(--sp-text)" }}>Users</h1>
        </div>
        {data && (
          <p className="text-[13px]" style={{ color: "var(--sp-text-3)" }}>
            {data.total} match{data.total === 1 ? "" : "es"}
          </p>
        )}
      </Rise>

      {/* Filter row */}
      <Rise i={1} className="sp-airy mt-6 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Chip label="All" active={!type} onClick={() => setFilter("type", "")} />
          <Chip label="Buyers" active={type === "buyer"} onClick={() => setFilter("type", "buyer")} />
          <Chip label="Sellers" active={type === "seller"} onClick={() => setFilter("type", "seller")} />

          <span className="mx-1.5 h-4 w-px" style={{ background: "var(--sp-border)" }} aria-hidden />

          <select
            value={status}
            onChange={(e) => setFilter("status", e.target.value)}
            className="h-9 rounded-full px-3 text-[12.5px] outline-none"
            style={{ background: "var(--sp-card)", border: "1px solid var(--sp-airy-border)", color: "var(--sp-text-2)", maxWidth: 180 }}
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>

          <div className="ml-auto flex items-center gap-2 rounded-full px-3.5 py-2" style={{ background: "var(--sp-card)", border: "1px solid var(--sp-airy-border)" }}>
            <Search aria-hidden className="h-3.5 w-3.5" style={{ color: "var(--sp-text-3)" }} />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Name, mobile, email, GSTIN, PAN"
              className="min-w-[200px] bg-transparent text-[12.5px] outline-none placeholder:opacity-60"
              style={{ color: "var(--sp-text)" }}
            />
          </div>
        </div>
      </Rise>

      {err ? (
        <p className="mt-6 text-sm" style={{ color: "var(--sp-error)" }}>{err}</p>
      ) : !data ? (
        <p className="mt-6 text-sm" style={{ color: "var(--sp-text-3)" }}>Loading…</p>
      ) : data.items.length === 0 ? (
        <div className="sp-airy mt-4 p-10 text-center">
          <p className="text-[13px]" style={{ color: "var(--sp-text-3)" }}>No users match this filter yet.</p>
        </div>
      ) : (
        <Rise i={2} className="sp-airy mt-4 overflow-hidden">
          <ul>
            {data.items.map((u, i) => (
              <UserListItem key={u.userId} u={u} first={i === 0} />
            ))}
          </ul>
        </Rise>
      )}
    </div>
  );
}

function UserListItem({ u, first }: { u: UserRow; first: boolean }) {
  return (
    <li style={{ borderTop: first ? "none" : "1px solid var(--sp-border)" }}>
      <Link
        href={`/admin/users/${u.userId}?view=${u.userType}`}
        className="group flex items-center gap-4 px-5 py-3.5 transition-colors"
        onMouseEnter={(e) => (e.currentTarget.style.background = "var(--sp-card-2)")}
        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold" style={{ background: "var(--sp-lime-10)", color: "var(--sp-lime)" }}>
          {(u.fullName || u.mobile || "?").slice(0, 2).toUpperCase()}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-medium" style={{ color: "var(--sp-text)" }}>
            {u.fullName || u.mobile || "—"}
            <span className="ml-1.5 align-middle text-[9px] font-bold uppercase tracking-[0.1em]" style={{ color: u.userType === "seller" ? "var(--sp-seller)" : "var(--sp-lime)" }}>
              · {u.userType}
            </span>
          </p>
          <p className="mt-0.5 truncate text-[11px]" style={{ color: "var(--sp-text-3)" }}>
            {u.mobile ? <>+91 {u.mobile}</> : null}
            {u.email ? <span className="mx-1.5">·</span> : null}
            {u.email ? u.email : null}
            {u.state ? <span className="mx-1.5">·</span> : null}
            {u.state ? u.state : null}
          </p>
        </div>
        <StagePill stage={u.stage} />
        <ArrowUpRight aria-hidden className="hidden h-4 w-4 shrink-0 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 sm:inline" style={{ color: "var(--sp-text-3)" }} />
      </Link>
    </li>
  );
}

function StagePill({ stage }: { stage: string }) {
  const verified = stage === "verified";
  return (
    <span
      className="hidden shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] sm:inline"
      style={
        verified
          ? { background: "var(--sp-lime-14)", color: "var(--sp-lime)" }
          : { background: "var(--sp-card-2)", color: "var(--sp-text-3)", border: "1px solid var(--sp-border)" }
      }
    >
      {STAGE_LABELS[stage] ?? stage}
    </span>
  );
}

function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="sp-chip" data-active={active || undefined}>
      {label}
    </button>
  );
}
