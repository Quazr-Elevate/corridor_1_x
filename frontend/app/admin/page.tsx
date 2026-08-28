"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  Clock,
  MapPin,
  ShieldCheck,
  TrendingUp,
  UserRound,
  Users,
} from "lucide-react";
import { AdminShell } from "@/components/admin/AdminShell";
import { OnboardingTimeline } from "@/components/admin/OnboardingTimeline";
import { RevealsFeed } from "@/components/admin/RevealsFeed";
import {
  adminApi,
  type DashboardStats,
  type RecentSignup,
  type TimelinePoint,
} from "@/lib/adminApi";

export default function AdminDashboardPage() {
  return (
    <AdminShell>
      <DashboardBody />
    </AdminShell>
  );
}

function DashboardBody() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [recent, setRecent] = useState<RecentSignup[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([adminApi.stats(), adminApi.timeline(30), adminApi.recent(8)])
      .then(([s, t, r]) => {
        setStats(s);
        setTimeline(t);
        setRecent(r);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Load failed"));
  }, []);

  if (err) {
    return <p className="text-sm text-danger">Could not load dashboard: {err}</p>;
  }
  if (!stats) {
    return <p className="text-sm text-paper-muted">Loading…</p>;
  }

  const wow =
    stats.signupsPrevWeek > 0
      ? Math.round(
          ((stats.signupsThisWeek - stats.signupsPrevWeek) /
            stats.signupsPrevWeek) *
            100,
        )
      : null;

  return (
    <div className="space-y-8">
      <header>
        <p className="text-[10px] uppercase tracking-widest text-paper-muted">
          <span
            aria-hidden
            className="mr-1.5 inline-block h-1 w-1 -translate-y-[2px] rounded-full bg-accent align-middle"
          />
          Admin console
        </p>
        <h1 className="mt-2 text-display text-paper">Dashboard</h1>
        <p className="mt-2 text-sm text-paper-muted">
          Onboarding health, verification funnel, and account moderation at a glance.
        </p>
      </header>

      {/* KPI tiles */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi
          icon={<UserRound className="h-4 w-4" />}
          label="Total buyers"
          value={stats.totalBuyers}
          hint="Registered accounts"
          href="/admin/users?type=buyer"
        />
        <Kpi
          icon={<Users className="h-4 w-4" />}
          label="Total sellers"
          value={stats.totalSellers}
          hint="Users with a listing"
          href="/admin/users?type=seller"
        />
        <Kpi
          icon={<ShieldCheck className="h-4 w-4" />}
          label="Verified"
          value={stats.totalVerified}
          hint="All 3 sections complete"
          href="/admin/users?status=verified"
        />
        <Kpi
          icon={<TrendingUp className="h-4 w-4" />}
          label="Signups this week"
          value={stats.signupsThisWeek}
          hint={
            wow === null
              ? "vs prev week: —"
              : `${wow >= 0 ? "+" : ""}${wow}% vs prev week`
          }
          positiveHint={wow !== null && wow >= 0}
        />
      </div>

      {/* Timeline */}
      <section className="surface p-5 sm:p-6">
        <div className="flex items-baseline justify-between">
          <div>
            <p className="text-title text-paper">Onboarding timeline</p>
            <p className="mt-0.5 text-xs text-paper-muted">
              Last 30 days · signups per day, split by role
            </p>
          </div>
          <div className="flex items-center gap-3 text-[10px] uppercase tracking-widest text-paper-muted">
            <span className="inline-flex items-center gap-1.5">
              <span
                aria-hidden
                className="inline-block h-2 w-2 rounded-sm bg-accent"
              />
              Buyer
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span
                aria-hidden
                className="inline-block h-2 w-2 rounded-sm"
                style={{ background: "var(--violet)" }}
              />
              Seller
            </span>
          </div>
        </div>
        <OnboardingTimeline data={timeline} />
      </section>

      {/* Recent contact reveals — signals conversion */}
      <RevealsFeed />

      {/* Quick filter chips → user list */}
      <section>
        <p className="text-[10px] uppercase tracking-widest text-paper-muted">
          <span
            aria-hidden
            className="mr-1.5 inline-block h-1 w-1 -translate-y-[2px] rounded-full bg-accent align-middle"
          />
          Jump into users
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <FilterChip href="/admin/users">All</FilterChip>
          <FilterChip href="/admin/users?type=buyer">Buyers</FilterChip>
          <FilterChip href="/admin/users?type=seller">Sellers</FilterChip>
          <FilterChip href="/admin/users?status=verified">Verified</FilterChip>
          <FilterChip href="/admin/users?status=signed_up">
            Signed up (incomplete)
          </FilterChip>
        </div>
      </section>

      {/* Two-column: funnel + recent */}
      <div className="grid gap-6 lg:grid-cols-5">
        <section className="surface p-5 sm:p-6 lg:col-span-3">
          <p className="text-title text-paper">Verification funnel</p>
          <p className="mt-0.5 text-xs text-paper-muted">
            Where users are stuck along the primary → business → bank path
          </p>
          <FunnelBars funnel={stats.funnel} />
        </section>

        <section className="surface p-5 sm:p-6 lg:col-span-2">
          <div className="flex items-baseline justify-between">
            <p className="text-title text-paper">Recent signups</p>
            <Link
              href="/admin/users"
              className="text-[11px] uppercase tracking-widest text-paper-muted hover:text-paper"
            >
              View all
            </Link>
          </div>
          <ul className="mt-4 divide-y divide-line-soft">
            {recent.map((r) => (
              <li key={r.userId}>
                <Link
                  href={`/admin/users/${r.userId}`}
                  className="group flex items-center gap-3 py-3 first:pt-2 last:pb-2"
                >
                  <span
                    aria-hidden
                    className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-line-soft bg-ink-elevated text-[11px] font-semibold text-paper"
                  >
                    {(r.fullName || r.mobile || "?").slice(0, 2).toUpperCase()}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-paper">
                      {r.fullName || r.mobile || "—"}
                      <span
                        className="ml-1.5 align-middle text-[9px] uppercase tracking-widest"
                        style={{
                          color:
                            r.userType === "seller"
                              ? "var(--violet)"
                              : "var(--accent)",
                        }}
                      >
                        · {r.userType}
                      </span>
                    </p>
                    <p className="mt-0.5 truncate text-[11px] text-paper-muted">
                      <Clock aria-hidden className="mr-1 inline h-3 w-3" />
                      {timeAgo(r.createdAt)} · {r.status}
                    </p>
                  </div>
                  <ArrowUpRight
                    aria-hidden
                    className="h-4 w-4 shrink-0 text-paper-muted transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-paper"
                  />
                </Link>
              </li>
            ))}
            {recent.length === 0 ? (
              <li className="py-6 text-center text-xs text-paper-muted">
                No signups yet.
              </li>
            ) : null}
          </ul>
        </section>
      </div>

      {/* Bottom row — geo + duplicates */}
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="surface p-5 sm:p-6">
          <p className="text-title text-paper">Top states</p>
          <p className="mt-0.5 text-xs text-paper-muted">
            Where your users are logging in from
          </p>
          <div className="mt-4 grid grid-cols-2 gap-6">
            <StateColumn
              title="Buyers"
              accent="var(--accent)"
              rows={stats.topStates.buyer}
            />
            <StateColumn
              title="Sellers"
              accent="var(--violet)"
              rows={stats.topStates.seller}
            />
          </div>
        </section>

        <section className="surface p-5 sm:p-6">
          <p className="text-title text-paper">Duplicate alerts</p>
          <p className="mt-0.5 text-xs text-paper-muted">
            Accounts sharing the same GSTIN or PAN
          </p>
          {stats.duplicateAlerts.length === 0 ? (
            <p className="mt-4 flex items-center gap-2 text-xs text-paper-muted">
              <ShieldCheck aria-hidden className="h-3.5 w-3.5 text-accent" />
              No duplicates flagged.
            </p>
          ) : (
            <ul className="mt-4 space-y-2">
              {stats.duplicateAlerts.map((a, i) => (
                <li
                  key={`${a.kind}-${a.value}-${i}`}
                  className="flex items-start gap-3 rounded-md border border-line-soft bg-ink-elevated px-3 py-2.5"
                >
                  <AlertTriangle
                    aria-hidden
                    className="mt-0.5 h-4 w-4 shrink-0"
                    style={{ color: "var(--danger)" }}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-paper">
                      {a.kind}{" "}
                      <span className="text-paper-muted">·</span>{" "}
                      <span className="font-mono">{a.value}</span>
                    </p>
                    <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-paper-muted">
                      {a.users.map((u) => (
                        <li key={u.user_id}>
                          <Link
                            href={`/admin/users/${u.user_id}`}
                            className="text-paper underline decoration-line hover:decoration-paper"
                          >
                            {u.label}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

// ── UI ─────────────────────────────────────────────────────────────────────

function Kpi({
  icon,
  label,
  value,
  hint,
  href,
  positiveHint,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  hint?: string;
  href?: string;
  positiveHint?: boolean;
}) {
  const inner = (
    <div className="surface flex h-full flex-col justify-between p-4">
      <div className="flex items-center justify-between">
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-accent/10 text-accent">
          {icon}
        </span>
        {href ? (
          <ArrowUpRight
            aria-hidden
            className="h-3.5 w-3.5 text-paper-muted transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-paper"
          />
        ) : null}
      </div>
      <div className="mt-3">
        <p className="text-2xl font-semibold tracking-tight text-paper">{value}</p>
        <p className="mt-0.5 text-[11px] text-paper-muted">{label}</p>
      </div>
      {hint ? (
        <p
          className={
            "mt-2 text-[11px] " +
            (positiveHint ? "text-accent" : "text-paper-muted")
          }
        >
          {hint}
        </p>
      ) : null}
    </div>
  );
  return href ? (
    <Link href={href} className="group">
      {inner}
    </Link>
  ) : (
    inner
  );
}

function FunnelBars({ funnel }: { funnel: Record<string, number> }) {
  const stages: { key: string; label: string }[] = [
    { key: "signed_up", label: "Signed up · nothing filled" },
    { key: "primary_pending", label: "Primary details pending" },
    { key: "business_pending", label: "Business details pending" },
    { key: "bank_pending", label: "Bank details pending" },
    { key: "verified", label: "Verified" },
  ];
  const max = Math.max(1, ...stages.map((s) => funnel[s.key] ?? 0));
  return (
    <ul className="mt-5 space-y-4">
      {stages.map((s) => {
        const n = funnel[s.key] ?? 0;
        const pct = Math.round((n / max) * 100);
        return (
          <li key={s.key}>
            <div className="flex items-baseline justify-between">
              <p className="text-xs text-paper">{s.label}</p>
              <p className="text-xs text-paper-muted">{n}</p>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-line-soft">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${pct}%`,
                  background:
                    s.key === "verified" ? "var(--accent)" : "var(--violet)",
                }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function FilterChip({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="inline-flex items-center gap-1.5 rounded-full border border-line-soft bg-ink-elevated px-3 py-1.5 text-xs text-paper transition-colors hover:border-line hover:bg-ink-soft"
    >
      {children}
      <ArrowRight aria-hidden className="h-3 w-3" />
    </Link>
  );
}

function StateColumn({
  title,
  accent,
  rows,
}: {
  title: string;
  accent: string;
  rows: { state: string; count: number }[];
}) {
  return (
    <div>
      <p
        className="text-[10px] uppercase tracking-widest"
        style={{ color: accent }}
      >
        {title}
      </p>
      {rows.length === 0 ? (
        <p className="mt-2 text-xs text-paper-muted">No data yet.</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {rows.map((r) => (
            <li key={r.state} className="flex items-center gap-2 text-xs">
              <MapPin aria-hidden className="h-3 w-3 text-paper-muted" />
              <span className="flex-1 truncate text-paper">{r.state}</span>
              <span className="text-paper-muted">{r.count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function timeAgo(iso: string): string {
  const d = new Date(iso);
  const s = Math.max(0, (Date.now() - d.getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
