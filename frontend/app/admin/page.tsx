"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowUpRight,
  Bell,
  Clock,
  MapPin,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
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
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      const [s, t, r] = await Promise.all([adminApi.stats(), adminApi.timeline(30), adminApi.recent(8)]);
      setStats(s);
      setTimeline(t);
      setRecent(r);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Load failed");
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (err) {
    return (
      <div className="sp-airy p-6">
        <p className="text-sm" style={{ color: "var(--sp-error)" }}>Could not load dashboard: {err}</p>
        <button type="button" onClick={load} className="mt-3 text-[13px] font-semibold" style={{ color: "var(--sp-lime)" }}>
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
    <div className="mx-auto max-w-[1240px]">
      {/* ── Header: breadcrumb · title · meta · circular actions ── */}
      <Rise i={0} className="flex flex-wrap items-start justify-between gap-5">
        <div>
          <p className="text-[12px]" style={{ color: "var(--sp-text-3)" }}>Admin console</p>
          <h1 className="mt-1 text-[34px] font-semibold tracking-[-0.025em]" style={{ color: "var(--sp-text)" }}>
            Dashboard
          </h1>
        </div>
        <div className="flex items-center gap-5">
          <Meta label="This week" value={`${stats.signupsThisWeek}`} sub={wow === null ? "new" : `${wow >= 0 ? "+" : ""}${wow}%`} positive={wow !== null && wow >= 0} />
          <Meta label="Verified" value={`${stats.totalVerified}`} sub="users" />
          <div className="flex items-center gap-2">
            <button type="button" onClick={load} aria-label="Refresh" className="sp-icon-btn">
              <RefreshCw className="h-4 w-4" aria-hidden style={refreshing ? { animation: "slowSpin 0.8s linear infinite" } : undefined} />
            </button>
            <Link href="/admin/verify" aria-label="Verify queue" className="sp-icon-btn">
              <Bell className="h-4 w-4" aria-hidden />
            </Link>
            <span className="sp-icon-btn" aria-hidden>
              <Settings className="h-4 w-4" />
            </span>
          </div>
        </div>
      </Rise>

      {/* ── KPI row — big airy cards ── */}
      <Rise i={1} className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Total buyers" value={stats.totalBuyers} unit="accounts" sub="Registered buyers" href="/admin/users?type=buyer" />
        <Kpi label="Total sellers" value={stats.totalSellers} unit="sellers" sub="Users with a listing" href="/admin/users?type=seller" />
        <Kpi label="Verified" value={stats.totalVerified} unit="users" sub="All 3 sections complete" href="/admin/users?status=verified" />
        <Kpi label="Signups this week" value={stats.signupsThisWeek} unit="new" sub={wow === null ? "vs prev week —" : `${wow >= 0 ? "+" : ""}${wow}% vs prev week`} positive={wow !== null && wow >= 0} />
      </Rise>

      {/* ── Two columns: lists (left) · gradient insight panel (right) ── */}
      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.55fr)]">
        {/* Left — pill filters + recent signups + geo */}
        <Rise i={2} className="flex flex-col gap-4">
          <section className="sp-airy p-5">
            <p className="text-[11px] font-bold uppercase tracking-[0.12em]" style={{ color: "var(--sp-text-3)" }}>Jump into users</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <FilterChip href="/admin/users">All</FilterChip>
              <FilterChip href="/admin/users?type=buyer">Buyers</FilterChip>
              <FilterChip href="/admin/users?type=seller">Sellers</FilterChip>
              <FilterChip href="/admin/users?status=verified">Verified</FilterChip>
              <FilterChip href="/admin/users?status=signed_up">Incomplete</FilterChip>
            </div>
          </section>

          <section className="sp-airy p-5">
            <div className="flex items-baseline justify-between">
              <p className="text-[15px] font-semibold" style={{ color: "var(--sp-text)" }}>Recent signups</p>
              <Link href="/admin/users" className="text-[11px] font-semibold transition-colors hover:underline" style={{ color: "var(--sp-text-3)" }}>
                View all
              </Link>
            </div>
            <ul className="mt-3 space-y-1.5">
              {recent.map((r) => (
                <li key={r.userId}>
                  <Link
                    href={`/admin/users/${r.userId}`}
                    className="group flex items-center gap-3 rounded-[14px] px-2.5 py-2.5 transition-colors"
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--sp-card-2)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold" style={{ background: "var(--sp-lime-10)", color: "var(--sp-lime)" }}>
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
              {recent.length === 0 && <li className="py-6 text-center text-xs" style={{ color: "var(--sp-text-3)" }}>No signups yet.</li>}
            </ul>
          </section>

          <section className="sp-airy p-5">
            <p className="text-[15px] font-semibold" style={{ color: "var(--sp-text)" }}>Top states</p>
            <div className="mt-3.5 grid grid-cols-2 gap-6">
              <StateColumn title="Buyers" accent="var(--sp-lime)" rows={stats.topStates.buyer} />
              <StateColumn title="Sellers" accent="var(--sp-seller)" rows={stats.topStates.seller} />
            </div>
          </section>
        </Rise>

        {/* Right — signature gradient insight panel */}
        <Rise i={3} className="flex flex-col gap-4">
          <section className="sp-gradient p-6">
            {/* Panel header + faux search (matches the reference) */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.14em]" style={{ color: "#4a5b2f" }}>Onboarding insights</p>
                <p className="mt-0.5 text-[19px] font-semibold" style={{ color: "#1c2415" }}>Last 30 days</p>
              </div>
              <div className="flex items-center gap-2.5 rounded-full bg-white/80 px-4 py-2.5 text-[13px] shadow-sm" style={{ color: "#5a6650", minWidth: "180px" }}>
                <Search className="h-4 w-4" aria-hidden />
                <span>Signups per day, by role</span>
              </div>
            </div>

            {/* Legend */}
            <div className="mt-5 flex items-center gap-4 text-[11px] font-semibold uppercase tracking-[0.1em]" style={{ color: "#3f4d2c" }}>
              <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: "#7d8b1f" }} />Buyer</span>
              <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: "#5f6b3c" }} />Seller</span>
            </div>

            {/* Timeline (hero visual) on a white inset card */}
            <div className="mt-3 rounded-[18px] bg-white/70 p-4">
              <TimelineTinted data={timeline} />
            </div>

            {/* Verification funnel — progression inside the panel */}
            <div className="mt-4 rounded-[18px] bg-white/70 p-5">
              <p className="text-[14px] font-semibold" style={{ color: "#1c2415" }}>Verification funnel</p>
              <p className="mt-0.5 text-[11.5px]" style={{ color: "#5a6650" }}>Where users are stuck · primary → business → bank</p>
              <Funnel funnel={stats.funnel} />
            </div>
          </section>

          {/* Reveals + duplicates below the panel */}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sp-airy overflow-hidden">
              <RevealsFeed />
            </div>
            <section className="sp-airy p-5">
              <p className="text-[15px] font-semibold" style={{ color: "var(--sp-text)" }}>Duplicate alerts</p>
              <p className="mt-0.5 text-[11.5px]" style={{ color: "var(--sp-text-3)" }}>Same GSTIN or PAN</p>
              {stats.duplicateAlerts.length === 0 ? (
                <p className="mt-4 flex items-center gap-2 text-xs" style={{ color: "var(--sp-text-3)" }}>
                  <ShieldCheck aria-hidden className="h-3.5 w-3.5" style={{ color: "var(--sp-lime)" }} />
                  No duplicates flagged.
                </p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {stats.duplicateAlerts.map((a, i) => (
                    <li key={`${a.kind}-${a.value}-${i}`} className="flex items-start gap-3 rounded-[14px] px-3 py-2.5" style={{ background: "var(--sp-card-2)" }}>
                      <AlertTriangle aria-hidden className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--sp-error)" }} />
                      <div className="min-w-0 flex-1">
                        <p className="text-xs" style={{ color: "var(--sp-text)" }}>
                          {a.kind} <span style={{ color: "var(--sp-text-3)" }}>·</span> <span className="sp-mono">{a.value}</span>
                        </p>
                        <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px]" style={{ color: "var(--sp-text-3)" }}>
                          {a.users.map((u) => (
                            <li key={u.user_id}>
                              <Link href={`/admin/users/${u.user_id}`} className="underline hover:no-underline" style={{ color: "var(--sp-text)" }}>{u.label}</Link>
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
        </Rise>
      </div>
    </div>
  );
}

// ── UI ───────────────────────────────────────────────────────────────────────

function Meta({ label, value, sub, positive }: { label: string; value: string; sub?: string; positive?: boolean }) {
  return (
    <div className="hidden sm:block">
      <p className="text-[10px] font-bold uppercase tracking-[0.12em]" style={{ color: "var(--sp-text-3)" }}>{label}</p>
      <p className="mt-0.5 text-[18px] font-semibold leading-none" style={{ color: "var(--sp-text)" }}>
        {value} {sub && <span className="text-[11px] font-medium" style={{ color: positive ? "var(--sp-lime)" : "var(--sp-text-3)" }}>{sub}</span>}
      </p>
    </div>
  );
}

function Kpi({ label, value, unit, sub, href, positive }: { label: string; value: number | string; unit?: string; sub?: string; href?: string; positive?: boolean }) {
  const inner = (
    <div
      className="sp-airy flex h-full flex-col p-6 transition-transform duration-150"
      onMouseEnter={(e) => (e.currentTarget.style.transform = "translateY(-2px)")}
      onMouseLeave={(e) => (e.currentTarget.style.transform = "translateY(0)")}
    >
      <div className="flex items-start justify-between">
        <p className="text-[12.5px]" style={{ color: "var(--sp-text-3)" }}>{label}</p>
        {href && <ArrowUpRight aria-hidden className="h-4 w-4" style={{ color: "var(--sp-text-3)" }} />}
      </div>
      <p className="mt-5 flex items-baseline gap-1.5">
        <span className="text-[38px] font-semibold leading-none tracking-tight" style={{ color: "var(--sp-text)" }}>{value}</span>
        {unit && <span className="text-[13px]" style={{ color: "var(--sp-text-3)" }}>{unit}</span>}
      </p>
      {sub && <p className="mt-3 text-[11.5px]" style={{ color: positive ? "var(--sp-lime)" : "var(--sp-text-3)" }}>{sub}</p>}
    </div>
  );
  return href ? <Link href={href} className="group">{inner}</Link> : inner;
}

// Funnel — vertical route progression with a highlighted bottleneck.
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
  let bnIdx = -1, bnN = -1;
  stages.forEach((s, i) => { if (s.key !== "verified" && counts[i] > bnN) { bnN = counts[i]; bnIdx = i; } });

  const ink = "#1c2415", ink2 = "#5a6650", lime = "#8a9a1f";

  return (
    <ul className="relative mt-4">
      {stages.map((s, i) => {
        const n = counts[i];
        const pct = Math.round((n / max) * 100);
        const isBn = i === bnIdx && n > 0;
        const isVer = s.key === "verified";
        const hot = isBn || isVer;
        return (
          <li key={s.key} className="relative grid grid-cols-[18px_minmax(0,1fr)] gap-3 pb-4 last:pb-0">
            <div className="relative flex justify-center">
              {i < stages.length - 1 && (
                <span aria-hidden className="absolute top-3 h-full w-px origin-top" style={{ background: "rgba(28,36,21,0.15)", animation: `spDraw 0.4s var(--sp-ease) ${0.2 + i * 0.08}s both` }} />
              )}
              <span aria-hidden className="relative z-10 mt-1 h-2.5 w-2.5 rounded-full" style={{ background: hot ? lime : "rgba(28,36,21,0.3)", boxShadow: hot ? "0 0 0 4px rgba(138,154,31,0.15)" : "none" }} />
            </div>
            <div>
              <div className="flex items-baseline justify-between gap-3">
                <p className="text-[13px]" style={{ color: ink }}>
                  {s.label} <span className="text-[11px]" style={{ color: ink2 }}>· {s.sub}</span>
                  {isBn && <span className="ml-2 rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.1em]" style={{ background: "rgba(138,154,31,0.2)", color: lime }}>Bottleneck</span>}
                </p>
                <p className="text-[13px] font-semibold" style={{ color: ink }}>{n}</p>
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full" style={{ background: "rgba(28,36,21,0.1)" }}>
                <div className="h-full rounded-full" style={{ width: `${pct}%`, background: hot ? lime : "rgba(28,36,21,0.28)", transition: "width 0.6s var(--sp-ease)" }} />
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

// Timeline variant tinted for the gradient panel (dark-on-light bars).
function TimelineTinted({ data }: { data: TimelinePoint[] }) {
  const max = Math.max(1, ...data.map((d) => d.buyer + d.seller));
  return (
    <div>
      <div className="flex h-32 items-end gap-[3px]">
        {data.map((d, idx) => {
          const b = (d.buyer / max) * 100, s = (d.seller / max) * 100;
          const empty = b === 0 && s === 0;
          return (
            <div key={d.date} className="group relative flex flex-1 flex-col justify-end" title={`${d.date}: ${d.buyer} buyer + ${d.seller} seller`}>
              <div className="flex flex-col justify-end" style={{ transformOrigin: "bottom", animation: `spBarGrow 0.5s var(--sp-ease) ${0.15 + idx * 0.012}s both` }}>
                {s > 0 && <div className="rounded-t-[3px]" style={{ height: `${s * 1.15}px`, background: "#5f6b3c" }} />}
                {b > 0 && <div className={s > 0 ? "" : "rounded-t-[3px]"} style={{ height: `${b * 1.15}px`, background: "#7d8b1f" }} />}
                {empty && <div className="h-[2px] rounded-t-[3px]" style={{ background: "rgba(28,36,21,0.15)" }} />}
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex justify-between text-[10px]" style={{ color: "#5a6650" }}>
        <span>{data[0]?.date ?? ""}</span>
        <span>{data[Math.floor(data.length / 2)]?.date ?? ""}</span>
        <span>{data[data.length - 1]?.date ?? ""}</span>
      </div>
    </div>
  );
}

function FilterChip({ href, children }: { href: string; children: React.ReactNode }) {
  return <Link href={href} className="sp-chip">{children}</Link>;
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
    <div className="mx-auto max-w-[1240px]">
      <div className="h-12 w-56 rounded-[16px]" style={{ background: "var(--sp-card)", opacity: 0.7 }} />
      <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <div key={i} className="h-36 rounded-[22px]" style={{ background: "var(--sp-card)", opacity: 0.6 }} />)}
      </div>
      <div className="mt-4 h-80 rounded-[24px]" style={{ background: "var(--sp-card)", opacity: 0.5 }} />
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
