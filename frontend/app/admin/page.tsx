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
import { Rise } from "@/components/admin/spatial";
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
    return (
      <div className="sp-surface p-6">
        <p className="text-sm" style={{ color: "var(--sp-error)" }}>
          Could not load dashboard: {err}
        </p>
        <button
          type="button"
          onClick={() => location.reload()}
          className="mt-3 text-[13px] font-semibold"
          style={{ color: "var(--sp-lime)" }}
        >
          Try again
        </button>
      </div>
    );
  }
  if (!stats) return <DashboardSkeleton />;

  const wow =
    stats.signupsPrevWeek > 0
      ? Math.round(((stats.signupsThisWeek - stats.signupsPrevWeek) / stats.signupsPrevWeek) * 100)
      : null;

  return (
    <div className="mx-auto max-w-[1200px] space-y-8">
      {/* Header */}
      <Rise i={0} className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.16em]" style={{ color: "var(--sp-text-3)" }}>
            <span className="h-1 w-1 rounded-full" style={{ background: "var(--sp-lime)" }} />
            Admin console
          </p>
          <h1 className="mt-2 text-[30px] font-semibold tracking-[-0.02em]" style={{ color: "var(--sp-text)" }}>
            Dashboard
          </h1>
          <p className="mt-1.5 max-w-lg text-[13.5px]" style={{ color: "var(--sp-text-2)" }}>
            Onboarding health, verification funnel, and account moderation at a glance.
          </p>
        </div>
      </Rise>

      {/* KPI objects */}
      <Rise i={1} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi icon={<UserRound className="h-4 w-4" />} label="Total buyers" value={stats.totalBuyers} hint="Registered accounts" href="/admin/users?type=buyer" />
        <Kpi icon={<Users className="h-4 w-4" />} label="Total sellers" value={stats.totalSellers} hint="Users with a listing" href="/admin/users?type=seller" />
        <Kpi icon={<ShieldCheck className="h-4 w-4" />} label="Verified" value={stats.totalVerified} hint="All 3 sections complete" href="/admin/users?status=verified" />
        <Kpi
          icon={<TrendingUp className="h-4 w-4" />}
          label="Signups this week"
          value={stats.signupsThisWeek}
          hint={wow === null ? "vs prev week: —" : `${wow >= 0 ? "+" : ""}${wow}% vs prev week`}
          positive={wow !== null && wow >= 0}
        />
      </Rise>

      {/* Timeline */}
      <Rise i={2} className="sp-surface p-5 sm:p-6">
        <div className="flex items-baseline justify-between">
          <div>
            <p className="text-[15px] font-semibold" style={{ color: "var(--sp-text)" }}>Onboarding timeline</p>
            <p className="mt-0.5 text-[11.5px]" style={{ color: "var(--sp-text-3)" }}>Last 30 days · signups per day, split by role</p>
          </div>
          <div className="flex items-center gap-3 text-[10px] font-bold uppercase tracking-[0.12em]" style={{ color: "var(--sp-text-3)" }}>
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm" style={{ background: "var(--sp-lime)" }} />Buyer</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm" style={{ background: "var(--sp-seller)" }} />Seller</span>
          </div>
        </div>
        <OnboardingTimeline data={timeline} />
      </Rise>

      {/* Reveals */}
      <Rise i={3}><RevealsFeed /></Rise>

      {/* Quick filters */}
      <Rise i={4}>
        <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.16em]" style={{ color: "var(--sp-text-3)" }}>
          <span className="h-1 w-1 rounded-full" style={{ background: "var(--sp-lime)" }} />
          Jump into users
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <FilterChip href="/admin/users">All</FilterChip>
          <FilterChip href="/admin/users?type=buyer">Buyers</FilterChip>
          <FilterChip href="/admin/users?type=seller">Sellers</FilterChip>
          <FilterChip href="/admin/users?status=verified">Verified</FilterChip>
          <FilterChip href="/admin/users?status=signed_up">Signed up (incomplete)</FilterChip>
        </div>
      </Rise>

      {/* Funnel + recent */}
      <div className="grid gap-6 lg:grid-cols-5">
        <Rise i={5} className="sp-surface p-5 sm:p-6 lg:col-span-3">
          <p className="text-[15px] font-semibold" style={{ color: "var(--sp-text)" }}>Verification funnel</p>
          <p className="mt-0.5 text-[11.5px]" style={{ color: "var(--sp-text-3)" }}>
            Where users are stuck along the primary → business → bank path
          </p>
          <Funnel funnel={stats.funnel} />
        </Rise>

        <Rise i={6} className="sp-surface p-5 sm:p-6 lg:col-span-2">
          <div className="flex items-baseline justify-between">
            <p className="text-[15px] font-semibold" style={{ color: "var(--sp-text)" }}>Recent signups</p>
            <Link href="/admin/users" className="text-[10px] font-bold uppercase tracking-[0.12em] transition-colors hover:underline" style={{ color: "var(--sp-text-3)" }}>
              View all
            </Link>
          </div>
          <ul className="mt-4">
            {recent.map((r, i) => (
              <li key={r.userId} style={{ borderTop: i === 0 ? "none" : "1px solid var(--sp-border)" }}>
                <Link
                  href={`/admin/users/${r.userId}`}
                  className="group flex items-center gap-3 rounded-[10px] px-2 py-3 transition-colors"
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--sp-surface-elevated)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <span
                    aria-hidden
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold"
                    style={{ border: "1px solid var(--sp-border)", background: "var(--sp-surface-interactive)", color: "var(--sp-text)" }}
                  >
                    {(r.fullName || r.mobile || "?").slice(0, 2).toUpperCase()}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium" style={{ color: "var(--sp-text)" }}>
                      {r.fullName || r.mobile || "—"}
                      <span className="ml-1.5 align-middle text-[9px] font-bold uppercase tracking-[0.1em]" style={{ color: r.userType === "seller" ? "var(--sp-seller)" : "var(--sp-lime)" }}>
                        · {r.userType}
                      </span>
                    </p>
                    <p className="mt-0.5 truncate text-[11px]" style={{ color: "var(--sp-text-3)" }}>
                      <Clock aria-hidden className="mr-1 inline h-3 w-3" />
                      {timeAgo(r.createdAt)} · {r.status}
                    </p>
                  </div>
                  <ArrowUpRight aria-hidden className="h-4 w-4 shrink-0 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" style={{ color: "var(--sp-text-3)" }} />
                </Link>
              </li>
            ))}
            {recent.length === 0 && (
              <li className="py-6 text-center text-xs" style={{ color: "var(--sp-text-3)" }}>No signups yet.</li>
            )}
          </ul>
        </Rise>
      </div>

      {/* Geo + duplicates */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Rise i={7} className="sp-surface p-5 sm:p-6">
          <p className="text-[15px] font-semibold" style={{ color: "var(--sp-text)" }}>Top states</p>
          <p className="mt-0.5 text-[11.5px]" style={{ color: "var(--sp-text-3)" }}>Where your users are logging in from</p>
          <div className="mt-4 grid grid-cols-2 gap-6">
            <StateColumn title="Buyers" accent="var(--sp-lime)" rows={stats.topStates.buyer} />
            <StateColumn title="Sellers" accent="var(--sp-seller)" rows={stats.topStates.seller} />
          </div>
        </Rise>

        <Rise i={8} className="sp-surface p-5 sm:p-6">
          <p className="text-[15px] font-semibold" style={{ color: "var(--sp-text)" }}>Duplicate alerts</p>
          <p className="mt-0.5 text-[11.5px]" style={{ color: "var(--sp-text-3)" }}>Accounts sharing the same GSTIN or PAN</p>
          {stats.duplicateAlerts.length === 0 ? (
            <p className="mt-4 flex items-center gap-2 text-xs" style={{ color: "var(--sp-text-3)" }}>
              <ShieldCheck aria-hidden className="h-3.5 w-3.5" style={{ color: "var(--sp-lime)" }} />
              No duplicates flagged.
            </p>
          ) : (
            <ul className="mt-4 space-y-2">
              {stats.duplicateAlerts.map((a, i) => (
                <li key={`${a.kind}-${a.value}-${i}`} className="flex items-start gap-3 rounded-[10px] px-3 py-2.5" style={{ border: "1px solid var(--sp-border)", background: "var(--sp-surface-elevated)" }}>
                  <AlertTriangle aria-hidden className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--sp-error)" }} />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs" style={{ color: "var(--sp-text)" }}>
                      {a.kind} <span style={{ color: "var(--sp-text-3)" }}>·</span> <span className="sp-mono">{a.value}</span>
                    </p>
                    <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px]" style={{ color: "var(--sp-text-3)" }}>
                      {a.users.map((u) => (
                        <li key={u.user_id}>
                          <Link href={`/admin/users/${u.user_id}`} className="underline hover:no-underline" style={{ color: "var(--sp-text)" }}>
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
        </Rise>
      </div>
    </div>
  );
}

// ── UI ───────────────────────────────────────────────────────────────────────

function Kpi({
  icon,
  label,
  value,
  hint,
  href,
  positive,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  hint?: string;
  href?: string;
  positive?: boolean;
}) {
  const inner = (
    <div
      className="sp-surface flex h-full flex-col justify-between p-5 transition-[transform,border-color] duration-150"
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = "translateY(-1px)";
        e.currentTarget.style.borderColor = "var(--sp-border-strong)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "translateY(0)";
        e.currentTarget.style.borderColor = "var(--sp-border)";
      }}
    >
      <div className="flex items-center justify-between">
        <span className="flex h-8 w-8 items-center justify-center rounded-[10px]" style={{ background: "var(--sp-lime-10)", color: "var(--sp-lime)" }}>
          {icon}
        </span>
        {href && <ArrowUpRight aria-hidden className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" style={{ color: "var(--sp-text-3)" }} />}
      </div>
      <div className="mt-4">
        <p className="text-[30px] font-semibold leading-none tracking-tight" style={{ color: "var(--sp-text)" }}>{value}</p>
        <p className="mt-1.5 text-[12px]" style={{ color: "var(--sp-text-2)" }}>{label}</p>
      </div>
      {hint && (
        <p className="mt-2.5 text-[11px]" style={{ color: positive ? "var(--sp-lime)" : "var(--sp-text-3)" }}>{hint}</p>
      )}
    </div>
  );
  return href ? <Link href={href} className="group">{inner}</Link> : inner;
}

// Route-style funnel — a vertical progression with a lime connector, count
// per stage, share bar, and a highlighted bottleneck (the non-verified stage
// holding the most users).
function Funnel({ funnel }: { funnel: Record<string, number> }) {
  const stages = [
    { key: "signed_up", label: "Signed up", sub: "nothing filled" },
    { key: "primary_pending", label: "Primary details", sub: "pending" },
    { key: "business_pending", label: "Business details", sub: "pending" },
    { key: "bank_pending", label: "Bank details", sub: "pending" },
    { key: "verified", label: "Verified", sub: "complete" },
  ];
  const counts = stages.map((s) => funnel[s.key] ?? 0);
  const max = Math.max(1, ...counts);
  // Bottleneck = the non-verified stage with the most users.
  let bottleneckIdx = -1;
  let bottleneckN = -1;
  stages.forEach((s, i) => {
    if (s.key !== "verified" && counts[i] > bottleneckN) {
      bottleneckN = counts[i];
      bottleneckIdx = i;
    }
  });

  return (
    <ul className="relative mt-5">
      {stages.map((s, i) => {
        const n = counts[i];
        const pct = Math.round((n / max) * 100);
        const isBottleneck = i === bottleneckIdx && n > 0;
        const isVerified = s.key === "verified";
        const dot = isVerified ? "var(--sp-lime)" : isBottleneck ? "var(--sp-lime)" : "var(--sp-text-3)";
        return (
          <li key={s.key} className="relative grid grid-cols-[20px_minmax(0,1fr)] gap-3 pb-5 last:pb-0">
            {/* Node + connector rail */}
            <div className="relative flex justify-center">
              {i < stages.length - 1 && (
                <span
                  aria-hidden
                  className="absolute top-3 h-full w-px origin-top"
                  style={{ background: "var(--sp-border-strong)", animation: `spDraw 0.4s var(--sp-ease) ${0.2 + i * 0.08}s both` }}
                />
              )}
              <span
                aria-hidden
                className="relative z-10 mt-1.5 h-2.5 w-2.5 rounded-full"
                style={{
                  background: dot,
                  boxShadow: isBottleneck || isVerified ? "0 0 0 4px var(--sp-lime-10)" : "none",
                }}
              />
            </div>

            <div>
              <div className="flex items-baseline justify-between gap-3">
                <p className="text-[13px]" style={{ color: "var(--sp-text)" }}>
                  {s.label}{" "}
                  <span className="text-[11px]" style={{ color: "var(--sp-text-3)" }}>· {s.sub}</span>
                  {isBottleneck && (
                    <span className="ml-2 rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.1em]" style={{ background: "var(--sp-lime-14)", color: "var(--sp-lime)" }}>
                      Bottleneck
                    </span>
                  )}
                </p>
                <p className="text-[13px] font-semibold" style={{ color: "var(--sp-text)" }}>{n}</p>
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full" style={{ background: "var(--sp-surface-interactive)" }}>
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${pct}%`,
                    background: isVerified || isBottleneck ? "var(--sp-lime)" : "var(--sp-border-strong)",
                    transition: "width 0.6s var(--sp-ease)",
                  }}
                />
              </div>
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
      className="inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[12.5px] transition-colors"
      style={{ border: "1px solid var(--sp-border)", background: "var(--sp-surface)", color: "var(--sp-text-2)" }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = "var(--sp-lime-14)";
        e.currentTarget.style.color = "var(--sp-text)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "var(--sp-border)";
        e.currentTarget.style.color = "var(--sp-text-2)";
      }}
    >
      {children}
      <ArrowRight aria-hidden className="h-3 w-3" />
    </Link>
  );
}

function StateColumn({ title, accent, rows }: { title: string; accent: string; rows: { state: string; count: number }[] }) {
  return (
    <div>
      <p className="text-[10px] font-bold uppercase tracking-[0.12em]" style={{ color: accent }}>{title}</p>
      {rows.length === 0 ? (
        <p className="mt-2 text-xs" style={{ color: "var(--sp-text-3)" }}>No data yet.</p>
      ) : (
        <ul className="mt-2.5 space-y-2">
          {rows.map((r) => (
            <li key={r.state} className="flex items-center gap-2 text-xs">
              <MapPin aria-hidden className="h-3 w-3" style={{ color: "var(--sp-text-3)" }} />
              <span className="flex-1 truncate" style={{ color: "var(--sp-text)" }}>{r.state}</span>
              <span style={{ color: "var(--sp-text-3)" }}>{r.count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="mx-auto max-w-[1200px] space-y-8">
      <div className="h-16 w-64 rounded-[12px]" style={{ background: "var(--sp-surface)", animation: "spRise 0.4s var(--sp-ease) both" }} />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-32 rounded-[16px]" style={{ background: "var(--sp-surface)", opacity: 0.7 }} />
        ))}
      </div>
      <div className="h-56 rounded-[16px]" style={{ background: "var(--sp-surface)", opacity: 0.6 }} />
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
