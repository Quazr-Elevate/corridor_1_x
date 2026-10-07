"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, RefreshCw, Search } from "lucide-react";
import { adminApi, type UserRow } from "@/lib/adminApi";

export default function AdminUsersPage() {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<UserRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminApi.users({ q, limit: 100 });
      setItems(res.items);
      setTotal(res.total);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }, [q]);

  useEffect(() => {
    const t = setTimeout(load, 200);
    return () => clearTimeout(t);
  }, [load]);

  return (
    <div className="mx-auto max-w-[1240px] px-6 py-8">
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div>
          <p className="text-[12px]" style={{ color: "var(--sp-text-3)" }}>
            Admin console · Users
          </p>
          <h1
            className="mt-1 text-[34px] font-semibold tracking-[-0.025em]"
            style={{ color: "var(--sp-text)" }}
          >
            {total} user{total === 1 ? "" : "s"}
          </h1>
        </div>
        <Link
          href="/admin"
          className="sp-chip"
          style={{ paddingLeft: "0.75rem" }}
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> Dashboard
        </Link>
      </div>

      <div className="sp-airy mt-7 p-4">
        <div className="relative">
          <Search
            className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2"
            aria-hidden
            style={{ color: "var(--sp-text-3)" }}
          />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by email or business name…"
            className="w-full rounded-[14px] py-3 pl-11 pr-4 text-[14px] focus:outline-none"
            style={{
              background: "var(--sp-card-2)",
              color: "var(--sp-text)",
              border: "1px solid var(--sp-border)",
            }}
          />
        </div>
      </div>

      {err && (
        <div
          className="sp-airy mt-4 p-4 text-[13px]"
          style={{ color: "var(--sp-error)" }}
        >
          {err}
        </div>
      )}

      {loading ? (
        <div className="mt-6 flex justify-center py-12">
          <RefreshCw
            className="h-6 w-6 animate-spin"
            style={{ color: "var(--sp-lime)" }}
          />
        </div>
      ) : items.length === 0 ? (
        <p
          className="sp-airy mt-4 p-10 text-center text-[13px]"
          style={{ color: "var(--sp-text-3)" }}
        >
          No users match.
        </p>
      ) : (
        <div className="sp-airy mt-4 overflow-hidden">
          <table className="w-full text-[13px]">
            <thead>
              <tr
                className="text-left text-[11px] font-bold uppercase tracking-[0.12em]"
                style={{
                  color: "var(--sp-text-3)",
                  background: "var(--sp-card-2)",
                }}
              >
                <th className="px-5 py-4">Email</th>
                <th className="px-5 py-4">Business</th>
                <th className="px-5 py-4">Status</th>
                <th className="px-5 py-4 text-right">Joined</th>
              </tr>
            </thead>
            <tbody>
              {items.map((u, i) => (
                <tr
                  key={u.userId}
                  onClick={() => (window.location.href = `/admin/users/${u.userId}`)}
                  style={{
                    borderTop: "1px solid var(--sp-border)",
                    background: i % 2 === 1 ? "var(--sp-card-2)" : "transparent",
                    cursor: "pointer",
                  }}
                >
                  <td className="px-5 py-3" style={{ color: "var(--sp-text)" }}>
                    {u.email}
                  </td>
                  <td
                    className="px-5 py-3"
                    style={{ color: "var(--sp-text-2)" }}
                  >
                    {u.businessName || "—"}
                  </td>
                  <td className="px-5 py-3">
                    <StatusPill status={u.status} />
                  </td>
                  <td
                    className="px-5 py-3 text-right text-[12px]"
                    style={{ color: "var(--sp-text-3)" }}
                  >
                    {new Date(u.createdAt).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const label = status.replace(/_/g, " ");
  const tone =
    status === "verified"
      ? { bg: "var(--sp-lime-14)", fg: "var(--sp-lime)" }
      : status === "rejected"
      ? { bg: "rgba(229,107,111,0.12)", fg: "var(--sp-error)" }
      : status === "active"
      ? { bg: "rgba(126,159,255,0.12)", fg: "var(--sp-info)" }
      : status === "email_verified"
      ? { bg: "var(--sp-card-2)", fg: "var(--sp-text-2)" }
      : { bg: "var(--sp-card-2)", fg: "var(--sp-text-3)" };
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.08em]"
      style={{ background: tone.bg, color: tone.fg }}
    >
      {label}
    </span>
  );
}
