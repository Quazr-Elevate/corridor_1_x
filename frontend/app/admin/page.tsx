"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  FileText,
  Mail,
  Package,
  RefreshCw,
  ShieldCheck,
  Users,
} from "lucide-react";
import {
  adminApi,
  type DashboardStats,
  type StuckUser,
  type TimelinePoint,
} from "@/lib/adminApi";

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [stuck, setStuck] = useState<StuckUser[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      const [s, t, k] = await Promise.all([
        adminApi.stats(),
        adminApi.timeline(30),
        adminApi.stuck(6),
      ]);
      setStats(s);
      setTimeline(t);
      setStuck(k);
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
      <div className="mx-auto max-w-[1240px] p-6">
        <p className="text-[13px]" style={{ color: "var(--sp-error)" }}>
          Could not load dashboard: {err}
        </p>
        <button
          type="button"
          onClick={load}
          className="mt-3 text-[13px] font-semibold"
          style={{ color: "var(--sp-lime)" }}
        >
          Try again
        </button>
      </div>
    );
  }

  if (!stats) {
    return <DashboardSkeleton />;
  }

  const verifiedPct = stats.totalUsers
    ? Math.round((stats.verifiedUsers / stats.totalUsers) * 100)
    : 0;

  return (
    <div className="mx-auto max-w-[1240px] px-6 py-8">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div>
          <p className="text-[12px]" style={{ color: "var(--sp-text-3)" }}>
            Admin console
          </p>
          <h1
            className="mt-1 text-[34px] font-semibold tracking-[-0.025em]"
            style={{ color: "var(--sp-text)" }}
          >
            Dashboard
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <HeaderMeta
            label="This 24h"
            value={`${stats.recentSignups24H}`}
            tone="lime"
          />
          <HeaderMeta label="Total" value={`${stats.totalUsers}`} />
          <button
            type="button"
            onClick={load}
            aria-label="Refresh"
            className="sp-icon-btn"
          >
            <RefreshCw
              className="h-4 w-4"
              aria-hidden
              style={
                refreshing
                  ? { animation: "slowSpin 0.8s linear infinite" }
                  : undefined
              }
            />
          </button>
        </div>
      </div>

      {/* KPI row — 5 tiles at lg+. On narrower screens they wrap: 2 on
          sm (so the first row shows the two highest-signal cards),
          then 3 below. */}
      <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Kpi
          icon={Users}
          label="Total users"
          value={stats.totalUsers}
          unit="accounts"
          sub={`${stats.recentSignups24H} new in 24h`}
          href="/admin/users"
        />
        <Kpi
          icon={ShieldCheck}
          label="Verified"
          value={stats.verifiedUsers}
          unit="users"
          sub={`${verifiedPct}% of total`}
          tone="lime"
          progress={verifiedPct}
          href="/admin/users?status=verified"
        />
        {/* New: users sitting in the Verified-badge review queue. Same
            tone as pending docs so admins read them as the two things
            that need attention today. */}
        <Kpi
          icon={ShieldCheck}
          label="User verifications pending"
          value={stats.pendingVerificationUsers}
          unit="to review"
          sub="Awaiting admin decision"
          href="/admin/verify"
          tone="warn"
        />
        <Kpi
          icon={FileText}
          label="Pending docs"
          value={stats.pendingDocs}
          unit="to review"
          sub="Awaiting admin decision"
          href="/admin/docs"
          tone="warn"
        />
        <Kpi
          icon={Package}
          label="Products"
          value={stats.totalProducts}
          unit="listings"
          sub="Live catalog"
        />
      </div>

      {/* Two columns: left stuck + funnel, right timeline chart */}
      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.55fr)]">
        <div className="flex flex-col gap-4">
          <StuckCard stuck={stuck} total={stats.stuckSignups} />
          <FunnelCard stats={stats} />
        </div>

        <div className="flex flex-col gap-4">
          <TimelineCard data={timeline} />
          <Link
            href="/admin/verify"
            className="sp-airy group flex items-center justify-between p-5"
          >
            <div>
              <p
                className="text-[11px] font-bold uppercase tracking-[0.12em]"
                style={{ color: "var(--sp-text-3)" }}
              >
                Verification queue
              </p>
              <p
                className="mt-1 text-[16px] font-semibold"
                style={{ color: "var(--sp-text)" }}
              >
                {stats.pendingVerificationUsers} user
                {stats.pendingVerificationUsers === 1 ? "" : "s"} awaiting the
                Verified badge
              </p>
              <p
                className="mt-0.5 text-[11.5px]"
                style={{ color: "var(--sp-text-3)" }}
              >
                + {stats.pendingDocs} document
                {stats.pendingDocs === 1 ? "" : "s"} to review
              </p>
            </div>
            <span
              className="sp-icon-btn transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
              aria-hidden
            >
              <ArrowUpRight className="h-4 w-4" />
            </span>
          </Link>
        </div>
      </div>
    </div>
  );
}

// ── Stuck card ─────────────────────────────────────────────────────

function StuckCard({ stuck, total }: { stuck: StuckUser[]; total: number }) {
  return (
    <section className="sp-airy p-5">
      <div className="flex items-baseline justify-between">
        <div className="flex items-center gap-2">
          <Clock
            className="h-4 w-4"
            aria-hidden
            style={{ color: "var(--sp-warning)" }}
          />
          <p
            className="text-[15px] font-semibold"
            style={{ color: "var(--sp-text)" }}
          >
            Stuck signups
          </p>
        </div>
        <span
          className="text-[18px] font-semibold leading-none"
          style={{ color: "var(--sp-warning)" }}
        >
          {total}
        </span>
      </div>
      <p
        className="mt-1 text-[11.5px]"
        style={{ color: "var(--sp-text-3)" }}
      >
        Signed up {">"}24 hours ago but never verified their email.
      </p>

      {stuck.length === 0 ? (
        <p
          className="mt-4 text-[12px]"
          style={{ color: "var(--sp-text-3)" }}
        >
          Nothing stuck right now ✓
        </p>
      ) : (
        <ul className="mt-4 space-y-1.5">
          {stuck.map((u) => (
            <li
              key={u.userId}
              className="flex items-center justify-between gap-2 rounded-[14px] px-3 py-2"
              style={{ background: "var(--sp-card-2)" }}
            >
              <div className="min-w-0 flex-1">
                <p
                  className="truncate text-[12.5px] font-medium"
                  style={{ color: "var(--sp-text)" }}
                >
                  {u.businessName || u.email}
                </p>
                {u.businessName && (
                  <p
                    className="truncate text-[11px]"
                    style={{ color: "var(--sp-text-3)" }}
                  >
                    {u.email}
                  </p>
                )}
              </div>
              <span
                className="shrink-0 text-[11px] font-semibold"
                style={{ color: "var(--sp-warning)" }}
              >
                {u.hoursWaiting}h
              </span>
            </li>
          ))}
        </ul>
      )}

      {total > stuck.length && (
        <Link
          href="/admin/users?status=signed_up"
          className="mt-3 inline-flex items-center gap-1 text-[12px] font-semibold"
          style={{ color: "var(--sp-text-2)" }}
        >
          View all {total}
          <ArrowUpRight className="h-3 w-3" />
        </Link>
      )}
    </section>
  );
}

// ── Funnel card ────────────────────────────────────────────────────

function FunnelCard({ stats }: { stats: DashboardStats }) {
  const steps = [
    { key: "signed_up", label: "Signed up", sub: "awaiting email", value: stats.signedUpUsers },
    { key: "email_verified", label: "Email verified", sub: "ready to log in", value: stats.emailVerifiedUsers },
    { key: "active", label: "Active", sub: "password set", value: stats.activeUsers },
    { key: "onboarded", label: "Onboarded", sub: "wizard complete", value: stats.onboardedUsers },
    { key: "verified", label: "Verified", sub: "admin approved", value: stats.verifiedUsers },
  ];
  const max = Math.max(1, ...steps.map((s) => s.value));

  return (
    <section className="sp-airy p-5">
      <p
        className="text-[15px] font-semibold"
        style={{ color: "var(--sp-text)" }}
      >
        Verification funnel
      </p>
      <p
        className="mt-0.5 text-[11.5px]"
        style={{ color: "var(--sp-text-3)" }}
      >
        Where accounts drop off along the way
      </p>
      <ul className="relative mt-4">
        {steps.map((s, i) => {
          const pct = Math.round((s.value / max) * 100);
          const isLast = i === steps.length - 1;
          return (
            <li
              key={s.key}
              className="relative grid grid-cols-[18px_minmax(0,1fr)] gap-3 pb-4 last:pb-0"
            >
              <div className="relative flex justify-center">
                {!isLast && (
                  <span
                    aria-hidden
                    className="absolute top-3 h-full w-px"
                    style={{ background: "var(--sp-border)" }}
                  />
                )}
                <span
                  aria-hidden
                  className="relative z-10 mt-1 h-2.5 w-2.5 rounded-full"
                  style={{
                    background: isLast
                      ? "var(--sp-lime)"
                      : "var(--sp-border-strong)",
                    boxShadow: isLast
                      ? "0 0 0 4px var(--sp-lime-14)"
                      : "none",
                  }}
                />
              </div>
              <div>
                <div className="flex items-baseline justify-between gap-3">
                  <p
                    className="text-[13px]"
                    style={{ color: "var(--sp-text)" }}
                  >
                    {s.label}{" "}
                    <span
                      className="text-[11px]"
                      style={{ color: "var(--sp-text-3)" }}
                    >
                      · {s.sub}
                    </span>
                  </p>
                  <p
                    className="text-[13px] font-semibold"
                    style={{ color: "var(--sp-text)" }}
                  >
                    {s.value}
                  </p>
                </div>
                <div
                  className="mt-1.5 h-1.5 overflow-hidden rounded-full"
                  style={{ background: "var(--sp-card-2)" }}
                >
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${pct}%`,
                      background: isLast
                        ? "var(--sp-lime)"
                        : "var(--sp-text-3)",
                      transition: "width 600ms var(--sp-ease)",
                    }}
                  />
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

// ── Timeline chart ─────────────────────────────────────────────────

function TimelineCard({ data }: { data: TimelinePoint[] }) {
  const max = useMemo(
    () => Math.max(1, ...data.map((d) => d.count)),
    [data],
  );
  const total = useMemo(
    () => data.reduce((a, d) => a + d.count, 0),
    [data],
  );

  const [hover, setHover] = useState<number | null>(null);

  return (
    <section className="sp-gradient p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p
            className="text-[11px] font-bold uppercase tracking-[0.14em]"
            style={{ color: "#4a5b2f" }}
          >
            Signups · last {data.length} days
          </p>
          <p
            className="mt-0.5 text-[22px] font-semibold"
            style={{ color: "#1c2415" }}
          >
            {total} total
          </p>
          <p className="text-[12px]" style={{ color: "#4a5b2f" }}>
            {hover !== null && data[hover]
              ? `${data[hover].date} · ${data[hover].count} signup${data[hover].count === 1 ? "" : "s"}`
              : "Hover a bar to see the day"}
          </p>
        </div>
      </div>

      <div className="mt-5 rounded-[18px] bg-white/70 p-5">
        <div className="flex h-36 items-end gap-[3px]">
          {data.map((d, i) => {
            const pct = (d.count / max) * 100;
            const empty = d.count === 0;
            const highlighted = hover === i;
            return (
              <button
                type="button"
                key={d.date}
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
                aria-label={`${d.date}: ${d.count} signups`}
                className="group relative flex flex-1 flex-col justify-end"
              >
                <div
                  className="rounded-t-[3px] transition-all"
                  style={{
                    height: empty ? "2px" : `${pct}%`,
                    background: empty
                      ? "rgba(28,36,21,0.14)"
                      : highlighted
                      ? "#1c2415"
                      : "#7d8b1f",
                  }}
                />
              </button>
            );
          })}
        </div>
        <div
          className="mt-2 flex justify-between text-[10px]"
          style={{ color: "#5a6650" }}
        >
          <span>{data[0]?.date ?? ""}</span>
          <span>{data[Math.floor(data.length / 2)]?.date ?? ""}</span>
          <span>{data[data.length - 1]?.date ?? ""}</span>
        </div>
      </div>
    </section>
  );
}

// ── Shared bits ────────────────────────────────────────────────────

function HeaderMeta({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "lime";
}) {
  return (
    <div className="hidden sm:block">
      <p
        className="text-[10px] font-bold uppercase tracking-[0.12em]"
        style={{ color: "var(--sp-text-3)" }}
      >
        {label}
      </p>
      <p
        className="mt-0.5 text-[18px] font-semibold leading-none"
        style={{ color: tone === "lime" ? "var(--sp-lime)" : "var(--sp-text)" }}
      >
        {value}
      </p>
    </div>
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  unit,
  sub,
  tone,
  progress,
  href,
}: {
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  label: string;
  value: number | string;
  unit?: string;
  sub?: string;
  tone?: "lime" | "warn";
  progress?: number;
  href?: string;
}) {
  const accent =
    tone === "lime"
      ? "var(--sp-lime)"
      : tone === "warn"
      ? "var(--sp-warning)"
      : "var(--sp-text-2)";
  const accentBg =
    tone === "lime"
      ? "var(--sp-lime-14)"
      : tone === "warn"
      ? "rgba(230,184,74,0.14)"
      : "var(--sp-card-2)";

  const inner = (
    <div
      className="sp-airy flex h-full flex-col p-6"
      style={{ transition: "transform 150ms var(--sp-ease)" }}
      onMouseEnter={(e) =>
        (e.currentTarget.style.transform = "translateY(-2px)")
      }
      onMouseLeave={(e) => (e.currentTarget.style.transform = "translateY(0)")}
    >
      <div className="flex items-start justify-between">
        <div
          className="flex h-9 w-9 items-center justify-center rounded-full"
          style={{ background: accentBg, color: accent }}
        >
          <Icon className="h-4 w-4" aria-hidden />
        </div>
        {href && (
          <ArrowUpRight
            className="h-4 w-4"
            aria-hidden
            style={{ color: "var(--sp-text-3)" }}
          />
        )}
      </div>
      <p
        className="mt-5 text-[12.5px]"
        style={{ color: "var(--sp-text-3)" }}
      >
        {label}
      </p>
      <p className="mt-1 flex items-baseline gap-1.5">
        <span
          className="text-[38px] font-semibold leading-none tracking-tight"
          style={{ color: "var(--sp-text)" }}
        >
          {value}
        </span>
        {unit && (
          <span className="text-[13px]" style={{ color: "var(--sp-text-3)" }}>
            {unit}
          </span>
        )}
      </p>
      {progress !== undefined && (
        <div
          className="mt-4 h-1 overflow-hidden rounded-full"
          style={{ background: "var(--sp-card-2)" }}
        >
          <div
            className="h-full rounded-full"
            style={{
              width: `${progress}%`,
              background: accent,
              transition: "width 500ms var(--sp-ease)",
            }}
          />
        </div>
      )}
      {sub && (
        <p
          className="mt-3 text-[11.5px]"
          style={{ color: tone ? accent : "var(--sp-text-3)" }}
        >
          {sub}
        </p>
      )}
    </div>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}

function DashboardSkeleton() {
  return (
    <div className="mx-auto max-w-[1240px] px-6 py-8">
      <div
        className="h-12 w-56 rounded-[16px]"
        style={{ background: "var(--sp-card)", opacity: 0.6 }}
      />
      <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-36 rounded-[22px]"
            style={{ background: "var(--sp-card)", opacity: 0.5 }}
          />
        ))}
      </div>
      <div
        className="mt-4 h-80 rounded-[24px]"
        style={{ background: "var(--sp-card)", opacity: 0.4 }}
      />
    </div>
  );
}
