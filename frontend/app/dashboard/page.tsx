"use client";

import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  Eye,
  Handshake,
  Inbox,
  MessageSquare,
  Package,
  ShieldCheck,
  Sparkles,
  Wallet,
} from "lucide-react";
import { useMe } from "@/lib/useMe";
import { completionStats, nextIncompleteStep } from "@/lib/completion";

export default function DashboardPage() {
  const { me } = useMe();

  const { filled, total, pct } = completionStats(me);
  const nextStep = nextIncompleteStep(me);
  const allDone = !nextStep;
  const productsUnlocked = me?.status === "verified";

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <header>
        <p className="text-[10px] uppercase tracking-widest text-paper-muted">
          Welcome back
        </p>
        <h1 className="mt-2 text-display text-paper">
          Hey, <span className="text-gradient">{me?.fullName || "there"}</span>
        </h1>
        <p className="mt-2 text-sm text-paper-muted">
          Complete your profile to unlock listings, escrow, and buyer discovery.
        </p>
      </header>

      {/* Profile completion */}
      <section className="surface p-5 sm:p-6">
        <div className="flex items-baseline justify-between">
          <p className="text-title text-paper">Profile completion</p>
          <p className="text-sm">
            <span className="text-gradient text-lg font-semibold">{pct}%</span>
            <span className="ml-1.5 text-xs text-paper-muted">
              · {filled} / {total} fields
            </span>
          </p>
        </div>
        <div
          className="mt-3 h-1.5 overflow-hidden rounded-full bg-line-soft"
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="h-full rounded-full bg-accent transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>

        {allDone ? (
          <div className="mt-5 flex items-center gap-3 rounded-md border border-accent/30 bg-accent-soft px-4 py-3">
            <span
              aria-hidden
              className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent text-accent-fg"
            >
              <Check className="h-3.5 w-3.5" strokeWidth={3} />
            </span>
            <p className="flex-1 text-sm text-paper">
              Your profile is complete. You&apos;re a verified user.
            </p>
          </div>
        ) : (
          <div className="mt-5">
            <p className="text-xs text-paper-muted">
              Next up · <span className="text-paper capitalize">{nextStep.section} details</span>
            </p>
            <Link
              href={nextStep.href}
              className="btn-primary mt-3 inline-flex w-full items-center justify-center gap-1.5 sm:w-auto"
            >
              <span>Continue to complete profile</span>
              <ArrowRight aria-hidden className="h-4 w-4" />
            </Link>
          </div>
        )}
      </section>

      {/* Stats grid — preview */}
      <section>
        <SectionEyebrow label="At a glance" />
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            icon={<Eye className="h-4 w-4" />}
            label="Listing views"
            value="1,284"
            delta="+12% this week"
            positive
          />
          <StatCard
            icon={<MessageSquare className="h-4 w-4" />}
            label="Buyer inquiries"
            value="37"
            delta="+8 today"
            positive
          />
          <StatCard
            icon={<Handshake className="h-4 w-4" />}
            label="Deals in progress"
            value="4"
            delta="2 awaiting your action"
          />
          <StatCard
            icon={<Wallet className="h-4 w-4" />}
            label="Escrow held"
            value="₹6.2L"
            delta="Across 3 orders"
          />
        </div>
      </section>

      {/* Recent buyer inquiries + Deal pipeline */}
      <div className="grid gap-6 lg:grid-cols-5">
        <section className="surface p-5 sm:p-6 lg:col-span-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-title text-paper">Recent buyer inquiries</p>
              <p className="mt-0.5 text-xs text-paper-muted">
                Verified buyers who reached out this week
              </p>
            </div>
            <PreviewPill />
          </div>

          <ul className="mt-4 divide-y divide-line-soft">
            {DUMMY_INQUIRIES.map((q) => (
              <li
                key={q.id}
                className="group flex items-center gap-4 py-3.5 first:pt-2 last:pb-2"
              >
                <span
                  aria-hidden
                  className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line-soft bg-ink-elevated text-xs font-semibold text-paper"
                >
                  {q.buyer
                    .split(" ")
                    .map((s) => s[0])
                    .slice(0, 2)
                    .join("")}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-paper">
                    {q.buyer}
                    <span className="ml-1.5 align-middle text-[10px] uppercase tracking-widest text-paper-muted/70">
                      · {q.location}
                    </span>
                  </p>
                  <p className="mt-0.5 truncate text-xs text-paper-muted">
                    Wants <span className="text-paper">{q.qty}</span> of {q.product}
                  </p>
                </div>
                <span className="hidden shrink-0 text-[11px] text-paper-muted sm:inline">
                  {q.when}
                </span>
                <ArrowUpRight
                  aria-hidden
                  className="h-4 w-4 shrink-0 text-paper-muted transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-paper"
                />
              </li>
            ))}
          </ul>

          <button
            type="button"
            className="mt-4 inline-flex items-center gap-1 text-xs text-paper-muted transition-colors hover:text-paper"
          >
            View all inquiries
            <ArrowRight aria-hidden className="h-3.5 w-3.5" />
          </button>
        </section>

        <section className="surface p-5 sm:p-6 lg:col-span-2">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-title text-paper">Deal pipeline</p>
              <p className="mt-0.5 text-xs text-paper-muted">Snapshot by stage</p>
            </div>
            <PreviewPill />
          </div>

          <ul className="mt-5 space-y-4">
            {DUMMY_PIPELINE.map((s) => (
              <li key={s.stage}>
                <div className="flex items-baseline justify-between">
                  <p className="text-xs text-paper">{s.stage}</p>
                  <p className="text-xs text-paper-muted">
                    {s.count} <span className="text-paper-muted/60">·</span>{" "}
                    <span className="text-paper">{s.value}</span>
                  </p>
                </div>
                <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-line-soft">
                  <div
                    className="h-full rounded-full bg-accent"
                    style={{ width: `${s.pct}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>

          <div className="mt-5 flex items-center gap-1.5 rounded-md border border-dashed border-line px-3 py-2 text-[11px] text-paper-muted">
            <Sparkles aria-hidden className="h-3 w-3 text-accent" />
            Real deals flow in once you add your first listing.
          </div>
        </section>
      </div>

      {/* Products CTA */}
      <section className="surface p-5 sm:p-6">
        <div className="flex items-start gap-4">
          <span className="mt-1 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent/10 text-accent">
            <Package className="h-4 w-4" aria-hidden />
          </span>
          <div className="flex-1">
            <p className="text-title text-paper">
              {productsUnlocked ? "Add your first product" : "Get verified to list products"}
            </p>
            <p className="mt-1 text-sm text-paper-muted">
              {productsUnlocked
                ? "You're verified — publish a listing to start attracting buyers."
                : "Complete Primary, Business and Bank details to become a verified user."}
            </p>
          </div>
          <Link
            href={
              productsUnlocked
                ? "/dashboard/products"
                : nextStep?.href ?? "/dashboard/profile/primary"
            }
            className="btn-inline"
          >
            {productsUnlocked ? (
              <>
                Add product
                <ArrowRight aria-hidden className="ml-1 h-3.5 w-3.5" />
              </>
            ) : (
              "Continue setup"
            )}
          </Link>
        </div>
      </section>

      {/* Announcements */}
      <section className="surface flex items-center gap-3 p-4">
        <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/10 text-accent">
          <ShieldCheck aria-hidden className="h-4 w-4" />
        </span>
        <div className="flex-1">
          <p className="text-xs font-medium text-paper">
            Escrow launches next month
          </p>
          <p className="text-[11px] text-paper-muted">
            All deals will run through RBI-regulated escrow — full announcement soon.
          </p>
        </div>
        <Inbox aria-hidden className="h-4 w-4 text-paper-muted" />
      </section>
    </div>
  );
}

// ── UI bits ─────────────────────────────────────────────────────────────

function SectionEyebrow({ label }: { label: string }) {
  return (
    <p className="text-[10px] uppercase tracking-widest text-paper-muted">
      <span
        aria-hidden
        className="mr-1.5 inline-block h-1 w-1 -translate-y-[2px] rounded-full bg-accent align-middle"
      />
      {label}
    </p>
  );
}

function PreviewPill() {
  return (
    <span className="rounded-full border border-line-soft bg-ink-elevated px-2 py-0.5 text-[9px] uppercase tracking-widest text-paper-muted">
      Preview
    </span>
  );
}

function StatCard({
  icon,
  label,
  value,
  delta,
  positive,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  delta: string;
  positive?: boolean;
}) {
  return (
    <div className="surface p-4">
      <div className="flex items-center justify-between">
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-accent/10 text-accent">
          {icon}
        </span>
        <PreviewPill />
      </div>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-paper">
        {value}
      </p>
      <p className="mt-0.5 text-[11px] text-paper-muted">{label}</p>
      <p
        className={
          "mt-2 text-[11px] " +
          (positive ? "text-accent" : "text-paper-muted")
        }
      >
        {delta}
      </p>
    </div>
  );
}

// ── Dummy data ──────────────────────────────────────────────────────────

const DUMMY_INQUIRIES = [
  {
    id: "1",
    buyer: "Meera Krishnan",
    location: "Chennai",
    product: "Sona Masuri rice",
    qty: "20 MT",
    when: "2h ago",
  },
  {
    id: "2",
    buyer: "Global Foods FZE",
    location: "Dubai",
    product: "Turmeric — 5% curcumin",
    qty: "8 MT / month",
    when: "Yesterday",
  },
  {
    id: "3",
    buyer: "Rohit Agarwal",
    location: "Kolkata",
    product: "Toor dal — desi",
    qty: "12 MT",
    when: "2d ago",
  },
];

const DUMMY_PIPELINE = [
  { stage: "Inquiry", count: 12, value: "—", pct: 100 },
  { stage: "Quote sent", count: 6, value: "₹18L", pct: 62 },
  { stage: "Sample dispatched", count: 3, value: "₹9L", pct: 38 },
  { stage: "In escrow", count: 2, value: "₹6.2L", pct: 22 },
  { stage: "Delivered", count: 5, value: "₹14L", pct: 44 },
];
