"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  adminApi,
  errorMessage,
  type DashboardStats,
  type PendingDocRow,
  type StuckUser,
  type TimelinePoint,
  type VerifyQueueRow,
} from "@/lib/adminApi";
import { useTower } from "@/components/shell/TowerShell";
import { CorridorMap } from "@/components/art/CorridorMap";
import { Reveal, Stagger, StaggerItem } from "@/components/motion";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Icon } from "@/components/ui/Icon";
import { EmptyState, Notice, Skeleton } from "@/components/ui/Surface";
import { SignupChart } from "@/components/admin/SignupChart";
import { AttentionRow, QueueTile, StationChart, type StationBar } from "@/components/admin/tower";
import { dueState, fmtAgo, greeting, nameFromEmail, plural, refId } from "@/components/admin/format";

/** Queue rows are fetched only to know what is past its 24h target. */
interface Queues {
  kyb: VerifyQueueRow[] | null;
  docs: PendingDocRow[] | null;
}

export default function TowerHomePage() {
  const { email, refreshStats } = useTower();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [timeline, setTimeline] = useState<TimelinePoint[] | null>(null);
  const [stuck, setStuck] = useState<StuckUser[] | null>(null);
  const [queues, setQueues] = useState<Queues>({ kyb: null, docs: null });
  const [err, setErr] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setRefreshing(true);
    // Queue detail only sharpens the counts — never block the tower on it.
    const extras = Promise.allSettled([adminApi.verifyQueue(), adminApi.pendingDocs()]).then(([k, d]) =>
      setQueues({
        kyb: k.status === "fulfilled" ? k.value : null,
        docs: d.status === "fulfilled" ? d.value : null,
      }),
    );
    try {
      const [s, t, k] = await Promise.all([adminApi.stats(), adminApi.timeline(30), adminApi.stuck(10)]);
      setStats(s);
      setTimeline(t);
      setStuck(k);
      setErr(null);
    } catch (e) {
      setErr(errorMessage(e, "Couldn't load the tower."));
    } finally {
      await extras;
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const now = Date.now();
  const overdueKyb = useMemo(
    () => (queues.kyb ?? []).filter((r) => dueState(r.submittedAt ?? r.createdAt, now).over),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [queues.kyb],
  );
  const overdueDocs = useMemo(
    () => (queues.docs ?? []).filter((r) => dueState(r.doc.uploadedAt, now).over),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [queues.docs],
  );
  const queuesKnown = queues.kyb !== null && queues.docs !== null;

  const today = new Date();
  const dateLabel = today.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });

  const stations: StationBar[] = stats
    ? [
        { key: "draft", label: "Draft", count: stats.draftBusinesses, href: "/admin/users?status=draft" },
        { key: "pending_verification", label: "In review", count: stats.pendingVerificationBusinesses, href: "/admin/users?status=pending_verification" },
        { key: "verified", label: "Verified", count: stats.verifiedBusinesses, href: "/admin/users?status=verified" },
        { key: "rejected", label: "Rejected", count: stats.rejectedBusinesses, href: "/admin/users?status=rejected", muted: true },
      ]
    : [];

  return (
    <div className="pt-4">
      {/* ── Greeting ── */}
      <header className="flex animate-rise flex-wrap items-end justify-between gap-6">
        <div className="min-w-0 max-w-3xl">
          <p className="t-label text-fg-3">{dateLabel}</p>
          <h1 className="t-hero mt-3 text-fg">
            {greeting(today)}, {nameFromEmail(email)}.
          </h1>
          <div className="t-title3 mt-3 font-normal text-fg-2" aria-live="polite">
            {stats ? (
              <p>
                <Summary stats={stats} overdue={queuesKnown ? overdueKyb.length + overdueDocs.length : null} />
              </p>
            ) : err ? (
              <p>Counts unavailable.</p>
            ) : (
              <Skeleton className="h-6 w-[26rem] max-w-full" />
            )}
          </div>
        </div>
        <Button
          variant="secondary"
          size="sm"
          icon="refresh"
          loading={refreshing}
          onClick={() => {
            void load();
            void refreshStats();
          }}
        >
          Refresh
        </Button>
      </header>

      {err ? (
        <div className="mt-8">
          <Notice
            tone="frozen"
            title="Couldn't load the tower"
            action={
              <Button variant="secondary" size="sm" onClick={() => void load()}>
                Try again
              </Button>
            }
          >
            {err}
          </Notice>
        </div>
      ) : null}

      {/* ── Corridor + queues ── */}
      <section aria-label="Corridor and queues" className="mt-10 grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
        <Reveal className="relief relative overflow-hidden rounded-[34px] p-5 sm:p-6">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -left-24 -top-24 size-80 rounded-full bg-lime/[0.06] blur-3xl"
          />
          <div className="relative flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="t-label text-fg-3">Corridor live</p>
              <h2 className="t-title2 mt-1 text-fg">India ⇄ UAE</h2>
            </div>
            <Chip tone="verified" noIcon>
              Active · India, Middle East
            </Chip>
          </div>
          <div className="relative mx-auto mt-3 max-w-[600px]">
            <CorridorMap surface="tower" aspect={4 / 3} title="India ⇄ UAE corridor, live ports" />
          </div>
          <dl className="relative mt-3 grid grid-cols-3 gap-4 border-t border-line pt-5">
            <MapStat label="Accounts" value={stats?.totalUsers} />
            <MapStat label="Verified companies" value={stats?.verifiedBusinesses} />
            <MapStat label="Products listed" value={stats?.totalProducts} />
          </dl>
        </Reveal>

        <Stagger className="grid grid-cols-2 gap-3 self-start sm:gap-4">
          <StaggerItem>
            <QueueTile
              href="/admin/verify"
              icon="passport"
              count={stats?.pendingVerificationBusinesses}
              title="KYB reviews"
              alert={overdueKyb.length > 0}
              sub={
                overdueKyb.length
                  ? `${overdueKyb.length} past the 24h target`
                  : stats?.pendingVerificationBusinesses
                    ? "Target 24h"
                    : "Clear · target 24h"
              }
            />
          </StaggerItem>
          <StaggerItem>
            <QueueTile
              href="/admin/docs"
              icon="doc-check"
              count={stats?.pendingDocs}
              title="Docs to verify"
              alert={overdueDocs.length > 0}
              sub={
                overdueDocs.length
                  ? `${overdueDocs.length} past the 24h target`
                  : stats?.pendingDocs
                    ? "Target 24h"
                    : "Clear · target 24h"
              }
            />
          </StaggerItem>
          <StaggerItem>
            <QueueTile
              href="#attention"
              icon="clock"
              count={stats?.stuckSignups}
              title="Stuck signups"
              sub="Still in draft 24h+"
            />
          </StaggerItem>
          <StaggerItem>
            <QueueTile
              href="/admin/users?status=rejected"
              icon="alert"
              count={stats?.rejectedBusinesses}
              title="Asked to fix"
              sub="Rejected, waiting on them"
            />
          </StaggerItem>
          <StaggerItem>
            <QueueTile
              href="/admin/users"
              icon="user"
              count={stats?.recentSignups24H}
              title="New in 24 hours"
              sub={stats ? `${plural(stats.draftBusinesses, "business", "businesses")} in draft` : "…"}
            />
          </StaggerItem>
          <StaggerItem>
            <QueueTile
              href="/admin/users"
              icon="building"
              count={stats?.totalBusinesses}
              title="Businesses"
              sub={stats ? `${plural(stats.totalUsers, "account")} in total` : "…"}
            />
          </StaggerItem>
        </Stagger>
      </section>

      {/* ── Where businesses are sitting ── */}
      <Reveal as="section" aria-labelledby="sitting-h" className="mt-12">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="t-label text-fg-3">All businesses</p>
            <h2 id="sitting-h" className="t-title2 mt-1 text-fg">
              Where businesses are sitting
            </h2>
          </div>
          <Link
            href="/admin/users"
            className="t-sub inline-flex shrink-0 items-center gap-1.5 font-medium text-fg-2 transition-colors hover:text-fg"
          >
            Directory
            <Icon name="arrow-right" size={15} />
          </Link>
        </div>
        <div className="relief mt-5 rounded-[28px] p-5 sm:p-6">
          {stats ? (
            <StationChart bars={stations} label="Businesses by status" />
          ) : (
            <Skeleton className="h-[212px]" />
          )}
        </div>
      </Reveal>

      {/* ── Needs attention + signups ── */}
      <section className="mt-12 grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] lg:items-start">
        <Reveal as="div" id="attention" className="scroll-mt-24">
          <div className="flex items-end justify-between gap-4">
            <h2 className="t-title2 text-fg">Needs attention</h2>
            {stats ? (
              <span className="t-code text-fg-3">
                {stats.stuckSignups} stuck{queuesKnown ? ` · ${overdueKyb.length + overdueDocs.length} overdue` : ""}
              </span>
            ) : null}
          </div>
          <div className="relief mt-5 rounded-[28px] px-5">
            {stuck === null && !err ? (
              <div className="space-y-3 py-5" aria-busy="true">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-12" />
                ))}
              </div>
            ) : (
              <AttentionList stuck={stuck ?? []} overdueKyb={overdueKyb} overdueDocs={overdueDocs} now={now} />
            )}
          </div>
        </Reveal>

        <Reveal delay={0.08}>
          <section
            data-surface="trader"
            aria-labelledby="signups-h"
            className="rounded-[30px] bg-cream p-6 text-ink shadow-[0_30px_60px_-30px_rgb(0_0_0/0.9),inset_0_1px_0_rgb(255_255_255/0.6)]"
          >
            <p className="t-label text-accent">Last 30 days</p>
            <div className="mt-3 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 id="signups-h" className="t-title3 text-fg">
                  Signups
                </h2>
                {timeline ? (
                  <p className="t-sub mt-0.5 text-fg-2">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="size-2 rounded-full bg-lime shadow-[0_0_0_1px_rgb(10_10_10/0.15)]" aria-hidden="true" />
                      today · <span className="tabular text-fg">{timeline[timeline.length - 1]?.count ?? 0}</span>
                    </span>
                  </p>
                ) : null}
              </div>
              {timeline ? (
                <p className="tabular text-[34px] font-medium leading-none tracking-[-0.04em] text-fg">
                  {timeline.reduce((a, d) => a + d.count, 0)}
                  <span className="sr-only"> signups in the window</span>
                </p>
              ) : null}
            </div>
            <div className="mt-7">
              {timeline ? (
                timeline.length ? (
                  <SignupChart data={timeline} />
                ) : (
                  <EmptyState icon="chart" title="No signups yet" className="py-8" />
                )
              ) : (
                <Skeleton className="h-[184px]" />
              )}
            </div>
          </section>
        </Reveal>
      </section>
    </div>
  );
}

function Summary({ stats, overdue }: { stats: DashboardStats; overdue: number | null }) {
  const queued = stats.pendingVerificationBusinesses + stats.pendingDocs;
  const rest = [
    queued ? `${plural(queued, "item")} across the queues` : "the queues are clear",
    `${stats.verifiedBusinesses} verified so far`,
  ];
  if (overdue === null) {
    return <>{rest.join(", ").replace(/^./, (c) => c.toUpperCase())}.</>;
  }
  return (
    <>
      <span className="font-semibold text-fg">{overdue ? `${overdue} past deadline` : "Nothing past deadline"}</span>, {rest.join(", ")}.
    </>
  );
}

function MapStat({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="min-w-0">
      <dt className="t-label text-fg-3">{label}</dt>
      <dd className="tabular mt-1.5 text-[22px] font-medium tracking-[-0.03em] text-fg">
        {value === undefined ? <span className="text-fg-3">—</span> : value.toLocaleString("en-GB")}
      </dd>
    </div>
  );
}

function AttentionList({
  stuck,
  overdueKyb,
  overdueDocs,
  now,
}: {
  stuck: StuckUser[];
  overdueKyb: VerifyQueueRow[];
  overdueDocs: PendingDocRow[];
  now: number;
}) {
  if (!stuck.length && !overdueKyb.length && !overdueDocs.length) {
    return (
      <EmptyState icon="check" title="Nothing needs attention" className="py-10">
        No reviews past their target and no business has been sitting in draft for a day.
      </EmptyState>
    );
  }
  return (
    <ul className="divide-y divide-line">
      {overdueKyb.slice(0, 3).map((r) => (
        <AttentionRow
          key={`kyb-${r.userId}`}
          href="/admin/verify"
          icon="passport"
          tone="move"
          title={`${refId("KYB", r.userId)} is past its review deadline`}
          sub={`${r.businessName || r.fullName || r.email} · submitted ${fmtAgo(r.submittedAt ?? r.createdAt, now)}`}
        />
      ))}
      {overdueDocs.slice(0, 3).map((r) => (
        <AttentionRow
          key={`doc-${r.doc.id}`}
          href="/admin/docs"
          icon="doc-check"
          tone="move"
          title={`${refId("DOC", r.doc.id)} · ${r.doc.certType} is waiting past 24h`}
          sub={`${r.userBusinessName || r.userFullName || r.userEmail} · uploaded ${fmtAgo(r.doc.uploadedAt, now)}`}
        />
      ))}
      {stuck.map((s) => (
        <AttentionRow
          key={s.userId}
          href={`/admin/users/${s.userId}`}
          icon="passport"
          tone={s.hoursWaiting >= 72 ? "frozen" : "quiet"}
          title={`${s.email} hasn't sent for verification`}
          sub={s.businessName || "No business name yet"}
          meta={
            <Chip tone={s.hoursWaiting >= 72 ? "frozen" : "move"} icon="clock" size="sm" className="tabular">
              {s.hoursWaiting >= 48 ? `${Math.floor(s.hoursWaiting / 24)}d` : `${s.hoursWaiting}h`}
            </Chip>
          }
        />
      ))}
    </ul>
  );
}
