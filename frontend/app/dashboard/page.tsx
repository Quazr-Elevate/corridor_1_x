"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api, type Me, type ProductRead, type VerificationDoc } from "@/lib/api";
import { cn } from "@/lib/cn";
import { MEDIA } from "@/lib/media";
import { publicApi, type CatalogFacets, type PublicProductList } from "@/lib/publicApi";
import { useMe } from "@/lib/useMe";
import {
  PASSPORT_PATH,
  canSubmit,
  fieldByKey,
  fieldHref,
  formatDay,
  statusMeta,
  verificationCounts,
} from "@/lib/verification";
import { ApproxPrice } from "@/components/fx/FxContext";
import { Stagger, StaggerItem } from "@/components/motion";
import { Button, LinkButton } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Progress } from "@/components/ui/Controls";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Skeleton, SolidPanel } from "@/components/ui/Surface";
import { Beacon } from "@/components/trader/Beacon";
import { dot, lotCode, memberCode, price, qty } from "@/components/trader/format";
import { LENS_LABEL, useLens, type Lens } from "@/components/trader/lens";
import { LotThumb } from "@/components/trader/LotThumb";

/**
 * Corridor — the trader's home (reference: portal /corridor). The date and
 * lens, a greeting, the moves that are yours right now (all derived from
 * `me`, your documents and your lots), the account journey as the corridor
 * rail, and a strip of lots: yours on the Selling lens, the live market on
 * the Buying lens.
 */

function greeting(d: Date): string {
  const h = d.getHours();
  if (h < 5) return "Good evening";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function firstName(me: Me): string {
  return me.primary.fullName?.trim().split(/\s+/)[0] ?? "";
}

/** Fetch something optional for the home page; failures stay quiet. */
interface QuietState<T> {
  data: T | null;
  loading: boolean;
  /** Error on the LAST attempt — null while loading or on success. */
  error: boolean;
  /** Re-run the fetch. Used by the error branch's Retry button. */
  reload: () => void;
}

function useQuiet<T>(load: () => Promise<T>, key: string | undefined): QuietState<T> {
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: boolean }>({
    data: null,
    loading: true,
    error: false,
  });
  // Tick increments each time the caller asks for a reload. Depending on
  // it from the fetch effect means we don't have to recreate the loader
  // in a useCallback or juggle refs.
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!key) return;
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: false }));
    load()
      .then((data) => !cancelled && setState({ data, loading: false, error: false }))
      .catch(() => !cancelled && setState({ data: null, loading: false, error: true }));
    return () => {
      cancelled = true;
    };
    // `load` is a stable module-level call; re-run only per user or tick.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tick]);
  return { ...state, reload: () => setTick((n) => n + 1) };
}

const loadOwn = () => api.listProducts();
const loadDocs = () => api.listVerificationDocs();
const loadMarket = () => publicApi.listProducts({ limit: 5 });
const loadFacets = () => publicApi.facets();

interface HomeData {
  own: QuietState<ProductRead[]>;
  docs: QuietState<VerificationDoc[]>;
  market: QuietState<PublicProductList>;
  facets: QuietState<CatalogFacets>;
}

export default function CorridorPage() {
  const { me } = useMe();
  const { lens } = useLens();
  const data: HomeData = {
    own: useQuiet(loadOwn, me?.userId),
    docs: useQuiet(loadDocs, me?.userId),
    market: useQuiet(loadMarket, me?.userId),
    facets: useQuiet(loadFacets, me?.userId),
  };
  const now = useMemo(() => new Date(), []);

  if (!me) return <CorridorSkeleton />;

  const moves = buildMoves(me, lens, data);
  const n = moves.filter((m) => m.isMove).length;
  const v = me.verification;
  const dateLine = now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
  const name = firstName(me);

  const rest =
    v.status === "verified"
      ? "Your passport is verified."
      : v.status === "pending_verification"
        ? "Corridor ops has your passport."
        : v.status === "rejected"
          ? "Ops asked for changes."
          : v.missing.length
            ? `${v.missing.length} field${v.missing.length === 1 ? "" : "s"} left to verify.`
            : "Your passport is ready to send.";

  return (
    <div className="space-y-12 pt-6 sm:pt-10">
      <header className="flex animate-rise flex-wrap items-end justify-between gap-x-10 gap-y-8">
        <div className="min-w-0">
          <p className="t-label text-fg-3">
            {dateLine} · {LENS_LABEL[lens]} lens
          </p>
          <h1 className="t-hero mt-3 text-fg">
            {greeting(now)}
            {name ? `, ${name}` : ""}.
          </h1>
          <p className="t-title3 mt-3 font-normal text-fg-2">
            <span className="font-semibold text-fg">
              {n === 0 ? "Nothing is waiting on you." : `${n} move${n === 1 ? " is" : "s are"} yours.`}
            </span>{" "}
            {rest}
          </p>
        </div>
        <HeroStats me={me} lens={lens} data={data} />
      </header>

      <section aria-labelledby="your-move">
        <div className="mb-4 flex items-center gap-3">
          {n ? <Beacon /> : <span aria-hidden="true" className="size-2 rounded-full bg-fg/25" />}
          <h2 id="your-move" className="t-headline text-fg">
            Your move
          </h2>
        </div>
        <Stagger
          as="ul"
          className="no-scrollbar -mx-4 flex snap-x snap-mandatory scroll-px-4 gap-4 overflow-x-auto px-4 pb-6 pt-1 sm:mx-0 sm:scroll-px-0 sm:grid sm:grid-cols-2 sm:overflow-visible sm:px-0 xl:grid-cols-3"
        >
          {moves.map((m) => (
            <StaggerItem as="li" key={m.key} className="w-[86vw] max-w-[380px] shrink-0 snap-start sm:w-auto sm:max-w-none">
              {m.node}
            </StaggerItem>
          ))}
        </Stagger>
      </section>

      <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-12">
          <CorridorRail me={me} own={data.own.data} />
          {lens === "selling" ? <YourLots me={me} own={data.own} /> : <MarketLots market={data.market} />}
        </div>
        <aside className="space-y-5" aria-label="At a glance">
          <PassportGlance me={me} docs={data.docs} />
          {lens === "selling" ? (
            <MarketGlance market={data.market} facets={data.facets} />
          ) : (
            <LotsGlance me={me} own={data.own} />
          )}
        </aside>
      </div>
    </div>
  );
}

// ─── Hero stats ──────────────────────────────────────────────────────

function HeroStats({ me, lens, data }: { me: Me; lens: Lens; data: HomeData }) {
  const v = me.verification;
  const { filled, total } = verificationCounts(v);
  const verified = v.status === "verified";
  const own = data.own.data?.length ?? null;
  const live = data.market.data?.total ?? null;
  const passportSub =
    v.status === "verified"
      ? "verified"
      : v.status === "pending_verification"
        ? "in review"
        : v.status === "rejected"
          ? "needs changes"
          : "fields to verify";

  const lensStat =
    lens === "selling" ? (
      <HeroStat
        label="Your lots"
        value={data.own.loading ? <Skeleton className="h-[34px] w-12" /> : own ?? "—"}
        sub={verified ? "live to verified buyers" : "hidden until verified"}
      />
    ) : (
      <HeroStat
        label="In the market"
        value={data.market.loading ? <Skeleton className="h-[34px] w-12" /> : live ?? "—"}
        sub="live lots, verified sellers"
      />
    );

  return (
    <dl className="flex gap-8 sm:gap-10">
      {lensStat}
      <HeroStat label="Passport" value={`${filled}/${total}`} sub={passportSub} />
    </dl>
  );
}

function HeroStat({ label, value, sub }: { label: string; value: ReactNode; sub: string }) {
  return (
    <div className="sm:text-right">
      <dt className="t-label text-fg-3">{label}</dt>
      <dd className="tabular mt-2 flex text-[34px] font-medium leading-none tracking-[-0.04em] text-fg sm:justify-end">
        {value}
      </dd>
      <dd className="t-foot mt-1.5 text-fg-3">{sub}</dd>
    </div>
  );
}

// ─── Moves ───────────────────────────────────────────────────────────

interface Move {
  key: string;
  isMove: boolean;
  node: ReactNode;
}

function buildMoves(me: Me, lens: Lens, data: HomeData): Move[] {
  const v = me.verification;
  const { filled, total } = verificationCounts(v);
  const code = memberCode(me.userId);
  const verified = v.status === "verified";
  const out: Move[] = [];

  if (v.status === "rejected") {
    const next = v.missing.length ? fieldByKey(v.missing[0]) : undefined;
    out.push({
      key: "rejected",
      isMove: true,
      node: (
        <MoveCard
          href={next ? fieldHref(next) : PASSPORT_PATH}
          thumb={<LotThumb media={MEDIA.inspector} />}
          code={code}
          kicker="Corridor Passport"
          chip={<Chip tone="frozen">Needs changes</Chip>}
          title="Corridor ops asked for changes"
          footLeft={`${filled} of ${total} fields`}
          footRight={canSubmit(v) ? "Review and resubmit" : `Fix ${next?.label.toLowerCase() ?? "your passport"}`}
          tone="frozen"
        >
          <span className="line-clamp-2 border-l-2 border-danger/40 pl-3 text-fg">
            {v.rejectedReason || "Check your details and resubmit."}
          </span>
        </MoveCard>
      ),
    });
  } else if (v.status !== "pending_verification" && !verified) {
    if (v.missing.length > 0) {
      const missing = v.missing.map(fieldByKey).filter((f): f is NonNullable<typeof f> => !!f);
      const next = missing[0];
      const after = missing.slice(1).map((f) => f.label.toLowerCase());
      out.push({
        key: "fields",
        isMove: true,
        node: (
          <MoveCard
            href={next ? fieldHref(next) : PASSPORT_PATH}
            thumb={<LotThumb media={MEDIA.inspector} />}
            code={code}
            kicker="Corridor Passport"
            chip={<StepPill n={`${filled}/${total}`} label="Fields" />}
            title={next ? `Add your ${next.label.toLowerCase()}` : "Finish your passport"}
            footLeft={`${v.missing.length} left to verify`}
            footRight="Fill it in"
            move
          >
            <Progress value={filled} max={total} label="Verification fields filled" className="mb-2.5 mt-1 h-1.5" />
            {after.length ? `Then ${joinList(after)}.` : "The last field before Corridor ops can verify you."}
          </MoveCard>
        ),
      });
    } else if (canSubmit(v)) {
      out.push({
        key: "send",
        isMove: true,
        node: (
          <MoveCard
            href={PASSPORT_PATH}
            thumb={<LotThumb media={MEDIA.inspector} />}
            code={code}
            kicker="Corridor Passport"
            chip={<StepPill n={`${total}/${total}`} label="Ready" />}
            title="Send your passport for review"
            footLeft="Checked by hand"
            footRight="Review and send"
            move
          >
            All seven fields are in. Hold to send it to Corridor ops.
          </MoveCard>
        ),
      });
    }
  }

  const rejectedDocs = (data.docs.data ?? []).filter((d) => d.status === "rejected");
  if (rejectedDocs.length) {
    const first = rejectedDocs[0];
    out.push({
      key: "docs",
      isMove: true,
      node: (
        <MoveCard
          href={`${PASSPORT_PATH}?tab=certifications&doc=${first.id}`}
          thumb={<GlyphThumb icon="doc-check" tone="frozen" />}
          code={`DOC-${first.id.replace(/-/g, "").slice(0, 4).toUpperCase()}`}
          kicker={first.certType}
          chip={<Chip tone="frozen">Rejected</Chip>}
          title={rejectedDocs.length === 1 ? "Replace a rejected document" : `Replace ${rejectedDocs.length} documents`}
          footLeft={rejectedDocs.length === 1 ? first.filename : `${first.certType} and more`}
          footRight="See the note"
          tone="frozen"
        >
          {first.rejectionReason ? (
            <span className="line-clamp-2">Ops: &ldquo;{first.rejectionReason}&rdquo;</span>
          ) : (
            "Corridor ops couldn’t accept it."
          )}
        </MoveCard>
      ),
    });
  }

  if (v.status === "pending_verification") {
    out.push({
      key: "review",
      isMove: false,
      node: (
        <MoveCard
          href={PASSPORT_PATH}
          thumb={<LotThumb media={MEDIA.inspector} />}
          code={code}
          kicker="Corridor Passport"
          chip={
            <Chip tone="move" icon="clock">
              In review
            </Chip>
          }
          title="Corridor ops has your passport"
          footLeft={v.submittedAt ? `Sent ${formatDay(v.submittedAt)}` : "Sent"}
          footRight="Open passport"
        >
          You&rsquo;ll get the decision by email. Editing stays open meanwhile.
        </MoveCard>
      ),
    });
  }

  if (verified) {
    out.push({
      key: "verified",
      isMove: false,
      node: (
        <Link href={PASSPORT_PATH} className="group block h-full rounded-[26px]">
          <SolidPanel className="flex h-full flex-col rounded-[26px] p-5 transition-transform duration-500 ease-expo group-hover:-translate-y-0.5">
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-center gap-3">
                <span className="grid size-11 shrink-0 place-items-center rounded-[14px] bg-lime text-ink">
                  <Icon name="shield" size={20} />
                </span>
                <div className="min-w-0">
                  <p className="t-code text-fg-3">{code}</p>
                  <p className="t-headline truncate text-fg">Corridor Passport</p>
                </div>
              </div>
              <Chip tone="verified">Verified</Chip>
            </div>
            <p className="t-title3 mt-5 break-words leading-snug text-fg">
              {me.businessName || me.business.legalName || "Your company"}
            </p>
            <p className="t-sub mt-2 text-fg-2">Buyers see the badge on every lot you list.</p>
            <div className="mt-auto pt-5">
              <div className="flex items-center justify-between gap-3 border-t border-line pt-4">
                <span className="t-sub text-fg-2">{v.verifiedAt ? `Since ${formatDay(v.verifiedAt)}` : "Verified"}</span>
                <span className="t-sub inline-flex items-center gap-1.5 font-medium text-fg">
                  Open passport <Icon name="arrow-right" size={15} />
                </span>
              </div>
            </div>
          </SolidPanel>
        </Link>
      ),
    });
  }

  // Lens: the side you lead with comes first.
  const own = data.own.data;
  const sellCard: Move = {
    key: "list",
    // A verified seller with nothing listed: that's a move.
    isMove: lens === "selling" && verified && own !== null && own.length === 0,
    node: (
      <MoveCard
        href="/dashboard/products/new"
        thumb={<LotThumb media={MEDIA.warehouse} />}
        code={own === null ? "LISTINGS" : `${own.length} LISTED`}
        kicker="Your lots"
        title={own && own.length > 0 ? "List another lot" : "List your first lot"}
        footLeft={verified ? "Live on publish" : "Hidden until verified"}
        footRight="New listing"
        move={lens === "selling" && verified && own !== null && own.length === 0}
      >
        {verified
          ? "Put a commodity lot in front of verified buyers."
          : "Draft it now — it goes live once Corridor ops verifies you."}
      </MoveCard>
    ),
  };
  const market = data.market.data;
  const cats = data.facets.data?.categories ?? [];
  const buyCard: Move = {
    key: "market",
    isMove: false,
    node: (
      <MoveCard
        href="/products"
        thumb={<LotThumb category={cats[0]?.value ?? "Rice"} />}
        code={market ? `${market.total} LIVE` : "MARKET"}
        kicker="Corridor market"
        title="Find your next lot"
        footLeft={cats.length ? cats.slice(0, 3).map((c) => c.value).join(" · ") : "By commodity and origin"}
        footRight="Open market"
      >
        {market && cats.length
          ? `${market.total} lot${market.total === 1 ? "" : "s"} across ${cats.length} commodit${cats.length === 1 ? "y" : "ies"}, all from verified sellers.`
          : "Lots by commodity and origin, all from verified sellers."}
      </MoveCard>
    ),
  };
  if (lens === "selling") out.push(sellCard, buyCard);
  else out.push(buyCard, sellCard);

  return out;
}

/** "a, b and c". */
function joinList(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

/** Step pill, e.g. "4/7 Fields" — mono count + word. */
function StepPill({ n, label }: { n: string; label: string }) {
  return (
    <span className="inline-flex h-6 shrink-0 items-center gap-1.5 rounded-full px-2.5 text-[12px] font-medium leading-none tracking-[-0.005em] text-fg-2 shadow-[inset_0_0_0_1px_var(--c-line-2)]">
      <span className="t-code text-[11px]">{n}</span>
      {label}
    </span>
  );
}

/** A glyph in the thumbnail's frame, for moves with no photograph. */
function GlyphThumb({ icon, tone }: { icon: IconName; tone?: "frozen" }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "grid size-11 shrink-0 place-items-center rounded-[14px]",
        tone === "frozen" ? "bg-danger-soft text-danger" : "well text-fg-2",
      )}
    >
      <Icon name={icon} size={20} />
    </span>
  );
}

function MoveCard({
  href,
  thumb,
  code,
  kicker,
  chip,
  title,
  children,
  footLeft,
  footRight,
  move,
  tone,
}: {
  href: string;
  thumb: ReactNode;
  code: string;
  kicker: string;
  chip?: ReactNode;
  title: string;
  children: ReactNode;
  footLeft: string;
  footRight: string;
  move?: boolean;
  tone?: "frozen";
}) {
  return (
    <Link
      href={href}
      className="relief relief-hover group flex h-full flex-col rounded-[26px] p-5 hover:-translate-y-0.5"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          {thumb}
          <div className="min-w-0">
            <p className="t-code truncate text-fg-3">{code}</p>
            <p className="t-headline truncate text-fg">{kicker}</p>
          </div>
        </div>
        {chip}
      </div>
      <h3 className="t-title3 mt-5 leading-snug text-fg">{title}</h3>
      <div className="t-sub mt-2 text-fg-2">{children}</div>
      <div className="mt-auto pt-5">
        <div className="flex items-center justify-between gap-3 border-t border-line pt-4">
          <span className="t-sub tabular min-w-0 truncate text-fg-2">{footLeft}</span>
          <span
            className={cn(
              "t-sub flex shrink-0 items-center gap-1.5 font-medium",
              move ? "text-amber" : tone === "frozen" ? "text-danger" : "text-fg",
            )}
          >
            {footRight}
            <Icon
              name="arrow-right"
              size={15}
              className="transition-transform duration-300 ease-expo group-hover:translate-x-0.5"
            />
          </span>
        </div>
      </div>
    </Link>
  );
}

// ─── Corridor rail ───────────────────────────────────────────────────

type StepState = "done" | "current" | "todo" | "blocked";

interface RailTile {
  key: string;
  label: string;
  sub: string;
  state: StepState;
  href: string;
}

function railTiles(me: Me, own: ProductRead[] | null): RailTile[] {
  const v = me.verification;
  const s = v.status;
  const inReview = s === "pending_verification";
  const verified = s === "verified";
  const rejected = s === "rejected";
  const { filled, total } = verificationCounts(v);
  const profileDone = v.missing.length === 0 || inReview || verified;
  const listed = (own?.length ?? 0) > 0;
  const next = v.missing.length ? fieldByKey(v.missing[0]) : undefined;

  return [
    {
      key: "signup",
      label: "Signed up",
      sub: me.emailVerifiedAt ? formatDay(me.emailVerifiedAt) : "Email to confirm",
      state: "done",
      href: "/dashboard/settings",
    },
    {
      key: "profile",
      label: "Passport",
      sub: `${filled} of ${total} fields`,
      state: profileDone ? "done" : "current",
      href: next ? fieldHref(next) : PASSPORT_PATH,
    },
    {
      key: "sent",
      label: rejected ? "Needs changes" : "Sent for review",
      sub: v.submittedAt ? formatDay(v.submittedAt) : profileDone ? "Hold to send" : "After the fields",
      state: inReview || verified ? "done" : rejected ? "blocked" : profileDone ? "current" : "todo",
      href: PASSPORT_PATH,
    },
    {
      key: "verified",
      label: "Verified",
      sub: v.verifiedAt ? formatDay(v.verifiedAt) : "By Corridor ops",
      state: verified ? "done" : inReview ? "current" : "todo",
      href: PASSPORT_PATH,
    },
    {
      key: "listing",
      label: "First lot live",
      sub: listed ? `${own!.length} listed` : "Not yet",
      state: listed && verified ? "done" : verified ? "current" : "todo",
      href: listed ? "/dashboard/products" : "/dashboard/products/new",
    },
  ];
}

function CorridorRail({ me, own }: { me: Me; own: ProductRead[] | null }) {
  const tiles = railTiles(me, own);
  const currentIndex = tiles.findIndex((t) => t.state === "current" || t.state === "blocked");
  const doneCount = tiles.filter((t) => t.state === "done").length;
  return (
    <section aria-labelledby="corridor-rail">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="t-label text-fg-3">The corridor</p>
          <h2 id="corridor-rail" className="t-title2 mt-1 text-fg">
            Your account · Sign-up <span aria-hidden="true">→</span>
            <span className="sr-only">to</span> first lot
          </h2>
        </div>
        <p className="t-sub text-fg-3">
          {currentIndex >= 0 ? `Step ${currentIndex + 1} of ${tiles.length}` : `${doneCount} of ${tiles.length} done`}
        </p>
      </div>
      <div className="well no-scrollbar overflow-x-auto rounded-[22px] p-1.5">
        <ol className="grid min-w-[640px] grid-cols-5 gap-1">
          {tiles.map((t, i) => (
            <li key={t.key} className="min-w-0">
              <Link
                href={t.href}
                aria-current={t.state === "current" ? "step" : undefined}
                className={cn(
                  "flex h-full flex-col items-start rounded-[16px] px-3 py-2.5 text-left transition-[background-color,box-shadow,opacity] duration-300 ease-expo",
                  t.state === "current" || t.state === "blocked"
                    ? "bg-surface shadow-[var(--relief-sm)]"
                    : t.state === "todo"
                      ? "opacity-55 hover:opacity-90"
                      : "hover:bg-surface hover:shadow-[var(--relief-sm)]",
                )}
              >
                <span className="flex w-full items-center justify-between gap-2">
                  <span className="t-code text-[11px] text-fg-3">{String(i + 1).padStart(2, "0")}</span>
                  <StepMark state={t.state} />
                </span>
                <span
                  className={cn(
                    "t-foot mt-1 w-full truncate font-medium",
                    t.state === "blocked" ? "text-danger" : t.state === "current" ? "text-fg" : "text-fg-2",
                  )}
                >
                  {t.label}
                </span>
                <span className="t-foot w-full truncate text-fg-3">{t.sub}</span>
              </Link>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function StepMark({ state }: { state: StepState }) {
  if (state === "done") {
    return (
      <span className="solid grid size-[18px] place-items-center rounded-full" aria-label="Done">
        <Icon name="check" size={11} strokeWidth={2.2} />
      </span>
    );
  }
  if (state === "current") {
    return (
      <span
        className="size-2.5 rounded-full bg-lime shadow-[0_0_0_4px_rgb(196_216_46/0.25)]"
        role="img"
        aria-label="You are here"
      />
    );
  }
  if (state === "blocked") {
    return <Icon name="alert" size={14} className="text-danger" label="Blocked" />;
  }
  return <span className="size-2 rounded-full shadow-[inset_0_0_0_1.5px_var(--c-line-2)]" aria-hidden="true" />;
}

// ─── Lot strips ──────────────────────────────────────────────────────

function StripHeader({ id, eyebrow, title, action }: { id: string; eyebrow: string; title: string; action: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <p className="t-label text-fg-3">{eyebrow}</p>
        <h2 id={id} className="t-title2 mt-1 text-fg">
          {title}
        </h2>
      </div>
      {action}
    </div>
  );
}

function StripLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="t-sub group inline-flex items-center gap-1.5 font-medium text-fg">
      {children}
      <Icon name="arrow-right" size={15} className="transition-transform duration-300 ease-expo group-hover:translate-x-0.5" />
    </Link>
  );
}

function LotRow({
  href,
  category,
  name,
  amount,
  code,
  meta,
  right,
  rightApprox,
  rightSub,
}: {
  href: string;
  category: string;
  name: string;
  amount: string | null;
  code: string;
  meta: ReactNode;
  right: string;
  /** Indicative conversion into the viewer's currency (" · ≈ ₹13,451"). */
  rightApprox?: ReactNode;
  rightSub: ReactNode;
}) {
  return (
    <Link
      href={href}
      className="relief-sm relief-hover group grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 rounded-[22px] p-4 sm:gap-x-6 sm:p-5"
    >
      <div className="flex min-w-0 items-center gap-3.5">
        <LotThumb category={category} size={46} />
        <div className="min-w-0">
          <p className="t-headline truncate text-fg">
            {name}
            {amount ? <span className="font-normal text-fg-3"> · {amount}</span> : null}
          </p>
          <div className="mt-1 flex min-w-0 items-center gap-2">
            <span className="t-code shrink-0 text-fg-3">{code}</span>
            <span className="t-sub min-w-0 truncate text-fg-2">{meta}</span>
          </div>
          {/* Phones: the status line moves under the name. */}
          <div className="t-foot mt-1 flex min-w-0 items-center gap-1.5 text-fg-3 sm:hidden">{rightSub}</div>
        </div>
      </div>
      <div className="flex items-center gap-3 self-start text-right sm:self-center">
        <div className="min-w-0">
          <p className="t-headline tabular whitespace-nowrap text-fg">
            {right}
            {rightApprox}
          </p>
          <div className="t-foot mt-1 hidden items-center justify-end gap-1.5 text-fg-3 sm:flex">{rightSub}</div>
        </div>
        <Icon
          name="chevron-right"
          size={16}
          className="hidden shrink-0 text-fg-3 transition-transform duration-300 ease-expo group-hover:translate-x-0.5 sm:block"
        />
      </div>
    </Link>
  );
}

function RowsSkeleton() {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading lots">
      <Skeleton className="h-[86px] rounded-[22px]" />
      <Skeleton className="h-[86px] rounded-[22px]" />
    </div>
  );
}

function YourLots({ me, own }: { me: Me; own: HomeData["own"] }) {
  const verified = me.verification.status === "verified";
  const lots = own.data ?? [];
  return (
    <section aria-labelledby="your-lots">
      <StripHeader
        id="your-lots"
        eyebrow="Selling"
        title="Your lots"
        action={lots.length ? <StripLink href="/dashboard/products">All listings</StripLink> : null}
      />
      {own.loading ? (
        <RowsSkeleton />
      ) : lots.length === 0 ? (
        <ListALot verified={verified} />
      ) : (
        <Stagger as="ul" className="space-y-3">
          {lots.slice(0, 4).map((p) => (
            <StaggerItem as="li" key={p.id}>
              <LotRow
                href="/dashboard/products"
                category={p.category}
                name={p.name}
                amount={qty(p.quantity, p.unit)}
                code={lotCode(p.id)}
                meta={dot(p.category, p.variety, p.originState)}
                right={price(p.pricePerUnit, p.unit, p.currency)}
                rightApprox={<ApproxPrice amount={p.pricePerUnit} currency={p.currency} />}
                rightSub={
                  verified ? (
                    <>
                      <span className="size-2 rounded-full bg-lime" aria-hidden="true" />
                      Live
                    </>
                  ) : (
                    <>
                      <span className="size-2 rounded-full bg-fg/25" aria-hidden="true" />
                      Hidden until verified
                    </>
                  )
                }
              />
            </StaggerItem>
          ))}
        </Stagger>
      )}
    </section>
  );
}

/** The reference's "List a lot" well: a solid disc with a lime plus. */
function ListALot({ verified }: { verified: boolean }) {
  return (
    <Link
      href="/dashboard/products/new"
      className="well group flex min-h-[220px] flex-col items-center justify-center rounded-[30px] p-8 text-center transition-[background-color,box-shadow] duration-500 ease-expo hover:bg-surface hover:shadow-[var(--relief)]"
    >
      <span className="solid grid size-14 place-items-center rounded-full text-lime">
        <Icon name="plus" size={22} />
      </span>
      <span className="t-title3 mt-5 text-fg">List a lot</span>
      <span className="t-sub mt-1.5 max-w-[300px] text-fg-3">
        {verified
          ? "Commodity, volume, origin and price. It goes live to verified buyers."
          : "Draft it now. Lots go live to buyers once Corridor ops verifies you."}
      </span>
    </Link>
  );
}

function MarketLots({ market }: { market: HomeData["market"] }) {
  const items = market.data?.items ?? [];
  return (
    <section aria-labelledby="market-lots">
      <StripHeader
        id="market-lots"
        eyebrow="Buying"
        title="In the market"
        action={<StripLink href="/products">Open market</StripLink>}
      />
      {market.loading ? (
        <RowsSkeleton />
      ) : market.error ? (
        // Error branch — distinguishable from "no lots live" so a flaky
        // network isn't mistaken for a quiet market. Retry button lets
        // the user re-run the fetch without a full page reload.
        <div className="well flex flex-col items-center rounded-[30px] px-6 py-12 text-center">
          <LotThumb media={MEDIA.warehouse} size={56} radius={18} />
          <p className="t-title3 mt-5 text-fg">Couldn’t load the market</p>
          <p className="t-sub mt-1.5 max-w-sm text-fg-3">
            Network looked grumpy. Give it another go or open the full market page.
          </p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
            <Button variant="secondary" icon="refund" onClick={market.reload}>
              Retry
            </Button>
            <LinkButton variant="quiet" icon="arrow-right" href="/products">
              Open market
            </LinkButton>
          </div>
        </div>
      ) : items.length === 0 ? (
        <div className="well flex flex-col items-center rounded-[30px] px-6 py-12 text-center">
          <LotThumb media={MEDIA.warehouse} size={56} radius={18} />
          <p className="t-title3 mt-5 text-fg">No lots live right now</p>
          <p className="t-sub mt-1.5 text-fg-3">Verified sellers list here first.</p>
        </div>
      ) : (
        <Stagger as="ul" className="space-y-3">
          {items.map((p) => (
            <StaggerItem as="li" key={p.id}>
              <LotRow
                href={`/products/${p.id}`}
                category={p.category}
                name={p.name}
                amount={qty(p.quantity, p.unit)}
                code={lotCode(p.id)}
                meta={dot(p.category, p.originState)}
                right={price(p.pricePerUnit, p.unit, p.currency)}
                rightApprox={<ApproxPrice amount={p.pricePerUnit} currency={p.currency} />}
                rightSub={
                  <>
                    <Icon name="shield" size={12} className="text-accent" />
                    {dot("Verified seller", p.seller.city)}
                  </>
                }
              />
            </StaggerItem>
          ))}
        </Stagger>
      )}
    </section>
  );
}

// ─── At a glance ─────────────────────────────────────────────────────

function PassportGlance({ me, docs }: { me: Me; docs: HomeData["docs"] }) {
  const v = me.verification;
  const { filled, total } = verificationCounts(v);
  const meta = statusMeta(v.status);
  const next = v.missing.length ? fieldByKey(v.missing[0]) : undefined;
  const list = docs.data ?? [];
  const approved = list.filter((d) => d.status === "approved").length;
  const sendable = canSubmit(v);
  return (
    <Link href={next ? fieldHref(next) : PASSPORT_PATH} className="relief relief-hover block rounded-[26px] p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="t-label text-fg-3">Passport</p>
        <Chip tone={meta.tone} icon={v.status === "pending_verification" ? "clock" : undefined}>
          {meta.label}
        </Chip>
      </div>
      <p className="t-title3 mt-4 text-fg">
        {filled} of {total} fields
      </p>
      <Progress value={filled} max={total} label="Verification fields filled" className="mt-3 h-1.5" />
      {next && v.status !== "pending_verification" && v.status !== "verified" ? (
        <div className="mt-3 flex items-start gap-2.5 rounded-[16px] bg-amber-soft p-3 text-amber">
          <Icon name="pen" size={15} className="mt-0.5 shrink-0" />
          <p className="t-sub">
            <span className="font-semibold">{next.label}</span> is next
            {v.missing.length > 1 ? `, then ${v.missing.length - 1} more.` : " — the last one."}
          </p>
        </div>
      ) : sendable ? (
        <div className="mt-3 flex items-start gap-2.5 rounded-[16px] bg-amber-soft p-3 text-amber">
          <Icon name="shield" size={15} className="mt-0.5 shrink-0" />
          <p className="t-sub">
            <span className="font-semibold">Ready to send.</span> Hold to send it from your passport.
          </p>
        </div>
      ) : null}
      <p className="t-foot mt-4 flex items-center gap-1.5 text-fg-3">
        <Icon name="doc-check" size={14} />
        {docs.loading
          ? "Documents…"
          : `${list.length} document${list.length === 1 ? "" : "s"} on file${list.length ? ` · ${approved} approved` : ""}`}
      </p>
    </Link>
  );
}

function MarketGlance({ market, facets }: { market: HomeData["market"]; facets: HomeData["facets"] }) {
  const cats = facets.data?.categories ?? [];
  return (
    <Link href="/products" className="relief relief-hover block rounded-[26px] p-5">
      <div className="flex items-center justify-between">
        <p className="t-label text-fg-3">In the market</p>
        <Icon name="arrow-up-right" size={16} className="text-fg-3" />
      </div>
      {market.loading ? (
        <Skeleton className="mt-4 h-8 w-32" />
      ) : (
        <p className="mt-3 text-fg">
          <span className="tabular text-[26px] font-medium tracking-[-0.03em]">{market.data?.total ?? "—"}</span>
          <span className="t-sub ml-2 text-fg-3">live lots</span>
        </p>
      )}
      {cats.length ? (
        <ul className="mt-4 space-y-2.5">
          {cats.slice(0, 4).map((c) => (
            <li key={c.value} className="flex items-center gap-3">
              <LotThumb category={c.value} size={28} radius={9} />
              <span className="t-callout min-w-0 flex-1 truncate text-fg-2">{c.value}</span>
              <span className="t-code text-fg-3">{c.count}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <p className="t-foot mt-4 flex items-center gap-1.5 text-fg-3">
        <Icon name="shield" size={14} />
        Every seller is verified by Corridor ops
      </p>
    </Link>
  );
}

function LotsGlance({ me, own }: { me: Me; own: HomeData["own"] }) {
  const verified = me.verification.status === "verified";
  const lots = own.data ?? [];
  return (
    <Link
      href={lots.length ? "/dashboard/products" : "/dashboard/products/new"}
      className="relief relief-hover block rounded-[26px] p-5"
    >
      <div className="flex items-center justify-between">
        <p className="t-label text-fg-3">Your lots</p>
        <Icon name="arrow-up-right" size={16} className="text-fg-3" />
      </div>
      {own.loading ? (
        <Skeleton className="mt-4 h-8 w-24" />
      ) : (
        <p className="mt-3 text-fg">
          <span className="tabular text-[26px] font-medium tracking-[-0.03em]">{lots.length}</span>
          <span className="t-sub ml-2 text-fg-3">listed</span>
        </p>
      )}
      {lots.length ? (
        <ul className="mt-4 space-y-2.5">
          {lots.slice(0, 3).map((p) => (
            <li key={p.id} className="flex items-center gap-3">
              <LotThumb category={p.category} size={28} radius={9} />
              <span className="t-callout min-w-0 flex-1 truncate text-fg-2">{p.name}</span>
              <span className="t-code text-fg-3">{lotCode(p.id)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="t-sub mt-2 text-fg-2">Selling too? List a lot in under a minute.</p>
      )}
      <p className="t-foot mt-4 text-fg-3">{verified ? "Live to verified buyers" : "Hidden until you’re verified"}</p>
    </Link>
  );
}

// ─── Loading ─────────────────────────────────────────────────────────

function CorridorSkeleton() {
  return (
    <div className="space-y-12 pt-6 sm:pt-10" aria-busy="true" aria-label="Loading your corridor">
      <div className="space-y-4">
        <Skeleton className="h-3 w-48" />
        <Skeleton className="h-14 w-[26rem] max-w-full" />
        <Skeleton className="h-5 w-72 max-w-full" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <Skeleton className="h-[230px] rounded-[26px]" />
        <Skeleton className="h-[230px] rounded-[26px]" />
        <Skeleton className="hidden h-[230px] rounded-[26px] xl:block" />
      </div>
    </div>
  );
}
