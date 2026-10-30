"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useSearchParams } from "next/navigation";
import {
  Suspense,
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, ApiError, ENTITY_TYPE_SHORT, entityTypeShort, type EntityType, type Me, type VerificationDoc } from "@/lib/api";
import { INDIA_STATES, normalizeState } from "@/lib/indiaStates";
import { cn } from "@/lib/cn";
import { useMe } from "@/lib/useMe";
import { useFocusField } from "@/lib/useFocusField";
import { useDirtyFlag } from "@/lib/useUnsavedGuard";
import { sectionProgress, statusMeta, verificationCounts, type AccountSection } from "@/lib/verification";
import { CertificationsBlock, useVerificationDocs } from "@/components/account/CertificationsBlock";
import { Combobox } from "@/components/account/Combobox";
import { COUNTRIES, DIAL_OPTIONS, countryName, parsePhone, toCountryCodes } from "@/components/account/countries";
import { SendForVerificationBar } from "@/components/account/SendForVerificationBar";
import { VerificationBadge } from "@/components/account/VerificationBadge";
import { EASE } from "@/components/motion/tokens";
import { Button } from "@/components/ui/Button";
import { Chip, CountPill } from "@/components/ui/Chip";
import { ChoiceChips, Segmented } from "@/components/ui/Controls";
import { FieldShell, Input, ReadField, Select, Textarea } from "@/components/ui/Field";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { PassportIdentityCard, type PassportView } from "@/components/account/PassportIdentityCard";

// ─── Sections ────────────────────────────────────────────────────────
// Ids (`section-<key>`) are deep-link targets (`?tab=<key>`) and drive
// the scroll-spy. Field ids (#full-name, #phone, …) live on the inputs.

const SECTIONS: ReadonlyArray<{ key: AccountSection; label: string; short: string }> = [
  { key: "primary", label: "Primary info", short: "Primary" },
  { key: "company", label: "Company info", short: "Company" },
  { key: "business", label: "Business profile", short: "Business" },
  { key: "certifications", label: "Documents", short: "Documents" },
];

type FormKey = Exclude<AccountSection, "certifications">;
const FORM_KEYS: readonly FormKey[] = ["primary", "company", "business"];

/** Each editable section exposes `save()`; validation/API failures throw. */
export interface SectionHandle {
  save(): Promise<void>;
}

interface SectionProps {
  onDirtyChange(dirty: boolean): void;
}

// ─── Option lists (unchanged from the previous account page) ──────────

const INDUSTRIES = [
  "Agri commodities · rice / grains",
  "Agri commodities · pulses / lentils",
  "Agri commodities · oilseeds / oils",
  "Agri commodities · spices / condiments",
  "Agri commodities · tea / coffee",
  "Fresh produce · fruits / vegetables",
  "Dairy / animal proteins",
  "Processed foods / packaged goods",
  "Ingredients / additives",
  "Other",
];

const TRADE_POSITIONS: ReadonlyArray<{ value: "seller" | "buyer" | "both"; title: string; body: string; icon: IconName }> = [
  { value: "seller", title: "I want to sell", body: "I have supply to list.", icon: "sack" },
  { value: "buyer", title: "I want to buy", body: "I need supply for my market.", icon: "inbox" },
  { value: "both", title: "Both", body: "I trade in both directions.", icon: "route" },
];

const SELLER_TYPES = [
  "Manufacturer / Producer",
  "Farm / Cooperative",
  "Processor / Miller",
  "Trader / Exporter",
  "Distributor / Wholesaler",
];

const BUYER_TYPES = [
  "Importer",
  "Wholesaler",
  "Retail chain",
  "Food processor",
  "HoReCa",
  "Private label",
  "Government / Institutional",
];

const EXPORT_STATUSES = [
  "Currently exporting",
  "Ready to export — not started",
  "Preparing to export",
  "Domestic only (for now)",
];

// ─── Error helpers ───────────────────────────────────────────────────

type FieldErrors = Partial<Record<string, string>>;

const snakeToCamel = (s: string) => s.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());

/**
 * Route an API failure to the field it belongs to. 409s are the
 * duplicate checks (phone / legal name / website); 422s arrive as
 * "field_name: message".
 */
function routeError(e: unknown, fields: readonly string[]): { field?: string; message: string } {
  if (e instanceof ApiError) {
    if (e.status === 409) {
      const m = e.message.toLowerCase();
      const field = m.includes("phone")
        ? "phone"
        : m.includes("legal company name")
          ? "legalName"
          : m.includes("website")
            ? "websiteUrl"
            : undefined;
      return { field: field && fields.includes(field) ? field : undefined, message: e.message };
    }
    if (e.status === 429) return { message: "Too many saves. Wait a moment and try again." };
    const match = /^([A-Za-z_]+): (.+)$/.exec(e.message);
    if (match) {
      const field = snakeToCamel(match[1]);
      if (fields.includes(field)) return { field, message: match[2] };
    }
    return { message: e.message };
  }
  return { message: e instanceof Error ? e.message : "Could not save." };
}

// ─── Page ────────────────────────────────────────────────────────────

export default function PassportPage() {
  return (
    <Suspense fallback={<PassportSkeleton />}>
      <Passport />
    </Suspense>
  );
}

function Passport() {
  const { me, refetch } = useMe();
  const params = useSearchParams();
  const toast = useToast();
  const docsState = useVerificationDocs();
  const [active, setActive] = useState<AccountSection>("primary");
  const [view, setView] = useState<PassportView>("self");
  const reduce = useReducedMotion();

  useFocusField();

  const refs = {
    primary: useRef<SectionHandle>(null),
    company: useRef<SectionHandle>(null),
    business: useRef<SectionHandle>(null),
  };

  const [dirty, setDirty] = useState<Record<FormKey, boolean>>({ primary: false, company: false, business: false });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [justSaved, setJustSaved] = useState(false);

  // Stable per-section callbacks so the sections' effects don't churn.
  const onDirty = useMemo(
    () =>
      Object.fromEntries(
        FORM_KEYS.map((k) => [k, (d: boolean) => setDirty((s) => (s[k] === d ? s : { ...s, [k]: d }))]),
      ) as Record<FormKey, (d: boolean) => void>,
    [],
  );

  const dirtyLabels = SECTIONS.filter((s) => s.key !== "certifications" && dirty[s.key as FormKey]).map((s) => s.label);
  const anyDirty = dirtyLabels.length > 0;

  // Feeds the shell's unsaved-changes guard (dock, menu, back, tab close).
  useDirtyFlag(anyDirty);

  useEffect(() => {
    if (anyDirty) setJustSaved(false);
  }, [anyDirty]);

  useEffect(() => {
    if (!justSaved) return;
    const t = window.setTimeout(() => setJustSaved(false), 3000);
    return () => window.clearTimeout(t);
  }, [justSaved]);

  async function saveAll() {
    if (!anyDirty || saving) return;
    setSaving(true);
    setSaveError(null);
    const jobs = FORM_KEYS.filter((k) => dirty[k] && refs[k].current).map((k) => refs[k].current!.save());
    const results = await Promise.allSettled(jobs);
    const failures = results.filter((r): r is PromiseRejectedResult => r.status === "rejected");
    if (failures.length < results.length) {
      // One refetch for everything that landed — updates the badges,
      // progress and passport card.
      await refetch().catch(() => undefined);
    }
    setSaving(false);
    if (failures.length === 0) {
      setJustSaved(true);
      toast("Saved", "verified");
    } else {
      setSaveError(failures.map((f) => (f.reason instanceof Error ? f.reason.message : "Save failed")).join(" · "));
    }
  }

  const jumpTo = useCallback((key: AccountSection) => {
    document.getElementById(`section-${key}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  // Deep links: ?tab= jumps to a section, ?doc= to one uploaded document.
  useEffect(() => {
    const tab = params.get("tab");
    if (tab && SECTIONS.some((s) => s.key === tab) && !window.location.hash) {
      const t = window.setTimeout(() => jumpTo(tab as AccountSection), 120);
      return () => window.clearTimeout(t);
    }
  }, [params, jumpTo]);

  const docParam = params.get("doc");
  useEffect(() => {
    if (!docParam || docsState.loading) return;
    const t = window.setTimeout(() => {
      document.getElementById(`doc-${docParam}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 150);
    return () => window.clearTimeout(t);
  }, [docParam, docsState.loading]);

  // Scroll-spy: the last section whose top has crossed the line under the
  // top cluster is current; at the very bottom, the last section wins.
  useEffect(() => {
    let raf = 0;
    const update = () => {
      raf = 0;
      const atBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
      let current: AccountSection = "primary";
      for (const s of SECTIONS) {
        const el = document.getElementById(`section-${s.key}`);
        if (el && el.getBoundingClientRect().top <= 180) current = s.key;
      }
      setActive(atBottom ? "certifications" : current);
    };
    const onScroll = () => {
      if (!raf) raf = window.requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) window.cancelAnimationFrame(raf);
    };
  }, []);

  if (!me) return <PassportSkeleton />;

  return (
    <div className="pt-6 sm:pt-10">
      <header className="flex animate-rise flex-wrap items-end justify-between gap-6">
        <div className="min-w-0">
          <p className="t-label text-fg-3">Company</p>
          <h1 className="t-large mt-2 text-fg">Passport</h1>
          <p className="t-callout mt-2 max-w-xl text-fg-2">
            Verified once, checked continuously. Seven fields and your documents — Corridor ops does the rest.
          </p>
        </div>
        <Segmented<PassportView>
          label="Passport view"
          value={view}
          onChange={setView}
          options={[
            { value: "self", label: "As you see it", icon: "eye" },
            { value: "counterparty", label: "As counterparties see it", icon: "eye-off" },
          ]}
        />
      </header>

      {/* Phones: identity card, then the verification panel, then the
          sections. Wide: card and sections on the left, the panel sticks
          on the right. */}
      <div className="mt-8 grid items-start gap-8 sm:mt-10 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-5 lg:col-start-1 lg:row-start-1">
          <PassportIdentityCard me={me} docs={docsState.docs} docsLoading={docsState.loading} view={view} />
          <AnimatePresence initial={false}>
            {view === "counterparty" ? (
              <motion.div
                key="counterparty"
                initial={reduce ? { opacity: 0 } : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.45, ease: EASE }}
              >
                <CounterpartyView me={me} />
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>

        <aside className="space-y-5 lg:sticky lg:top-24 lg:col-start-2 lg:row-span-2 lg:row-start-1">
          <SendForVerificationBar dirty={anyDirty} />
          <SectionIndex me={me} active={active} onJump={jumpTo} docsCount={docsState.docs.length} />
        </aside>

        <div className="min-w-0 space-y-6 lg:col-start-1 lg:row-start-2">
          <SectionStrip active={active} onJump={jumpTo} />

          <SectionCard id="primary" index="01" title="Primary info" subtitle="You, and how buyers reach you." me={me}>
            <PrimarySection ref={refs.primary} onDirtyChange={onDirty.primary} />
          </SectionCard>

          <SectionCard id="company" index="02" title="Company info" subtitle="The identity on your passport." me={me}>
            <CompanySection ref={refs.company} onDirtyChange={onDirty.company} />
          </SectionCard>

          <SectionCard
            id="business"
            index="03"
            title="Business profile"
            subtitle="How Corridor finds your Fit with counterparties."
            me={me}
          >
            <BusinessSection ref={refs.business} onDirtyChange={onDirty.business} />
          </SectionCard>

          <SectionCard
            id="certifications"
            index="04"
            title="Documents"
            subtitle="Optional. Certificates and licences — each one is reviewed on its own by Corridor ops."
            me={me}
          >
            <CertificationsBlock state={docsState} />
          </SectionCard>
        </div>
      </div>

      {/* Room for the floating save bar above the dock. */}
      <div className="h-16" aria-hidden="true" />

      <SaveBar
        visible={anyDirty || saving || !!saveError || justSaved}
        dirtyLabels={dirtyLabels}
        saving={saving}
        error={saveError}
        justSaved={justSaved}
        onSave={() => void saveAll()}
      />
    </div>
  );
}

// ─── As counterparties see it ────────────────────────────────────────
// Derived from what the public catalog and the contact reveal actually
// expose: the seller's city/state and Verified badge on every lot; the
// company name and contact only through a verified buyer's reveal.

function CounterpartyView({ me }: { me: Me }) {
  const verified = me.verification.status === "verified";
  const place = [me.business.city, me.business.state].filter(Boolean).join(", ");
  return (
    <section aria-labelledby="counterparty-title" className="relief rounded-[26px] p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="counterparty-title" className="t-label text-fg-3">
          What a buyer sees on your lots
        </h2>
        {verified ? (
          <Chip tone="verified">Live to verified buyers</Chip>
        ) : (
          <Chip tone="neutral" icon="eye-off">
            Not on the market yet
          </Chip>
        )}
      </div>
      <dl className="mt-5 grid gap-x-8 gap-y-5 sm:grid-cols-2">
        <SeenRow icon="building" label="Company name" note="Hidden until a verified buyer holds to reveal your contact.">
          <span className="frost inline-flex h-6 w-[170px] items-center px-2.5" role="img" aria-label="Hidden">
            <span className="frost-glyphs t-sub truncate font-medium" aria-hidden="true">
              Verified Trading Co
            </span>
          </span>
        </SeenRow>
        <SeenRow
          icon="pin"
          label="Location"
          note={place ? "Shown as “Seller · city” on every lot." : "Lots show India until a city is on file."}
        >
          <span className="t-headline text-fg">{place || "India"}</span>
        </SeenRow>
        <SeenRow
          icon="shield"
          label="Badge"
          note={verified ? "On every lot you list." : "Lots stay off the market until Corridor ops verifies you."}
        >
          {verified ? <Chip tone="verified">Verified seller</Chip> : <span className="t-headline text-fg-3">None yet</span>}
        </SeenRow>
        <SeenRow
          icon="passport"
          label="Entity type"
          note="Shown with your company name when a verified buyer reveals your contact."
        >
          <span className={cn("t-headline", me.business.entityType ? "text-fg" : "text-fg-3")}>
            {entityTypeShort(me.business.entityType) || "Not specified"}
          </span>
        </SeenRow>
        <SeenRow icon="user" label="Contact" note="Opens to verified buyers only, one hold-to-reveal at a time.">
          <span className="t-headline text-fg">Name, email, address, website</span>
        </SeenRow>
      </dl>
    </section>
  );
}

function SeenRow({ icon, label, note, children }: { icon: IconName; label: string; note: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 items-start gap-3">
      <span className="well grid size-9 shrink-0 place-items-center rounded-full text-fg-2">
        <Icon name={icon} size={16} />
      </span>
      <div className="min-w-0">
        <dt className="t-label text-fg-3">{label}</dt>
        <dd className="mt-1.5">{children}</dd>
        <dd className="t-foot mt-1.5 text-fg-3">{note}</dd>
      </div>
    </div>
  );
}

// ─── Section chrome + navigation ─────────────────────────────────────

function SectionCount({ tab, me }: { tab: FormKey; me: Me }) {
  const { filled, total } = sectionProgress(tab, me.verification.missing);
  if (total === 0) return null;
  if (filled === total) {
    return (
      <Chip tone="quiet" icon="check">
        {total}/{total} to verify
      </Chip>
    );
  }
  return (
    <CountPill className="text-amber shadow-[inset_0_0_0_1px_var(--c-amber-soft)]">
      {filled}/{total} to verify
    </CountPill>
  );
}

function SectionCard({
  id,
  index,
  title,
  subtitle,
  me,
  children,
}: {
  id: AccountSection;
  index: string;
  title: string;
  subtitle: string;
  me: Me;
  children: ReactNode;
}) {
  return (
    <section
      id={`section-${id}`}
      aria-labelledby={`${id}-title`}
      className="relief scroll-mt-32 rounded-[30px] p-5 sm:p-8"
    >
      <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
        <div className="min-w-0">
          <p className="t-label text-fg-3">{index}</p>
          <h2 id={`${id}-title`} className="t-title2 mt-1.5 text-fg">
            {title}
          </h2>
          <p className="t-callout mt-1.5 max-w-xl text-fg-2">{subtitle}</p>
        </div>
        {id !== "certifications" ? <SectionCount tab={id} me={me} /> : null}
      </header>
      <div className="mt-6 border-t border-line pt-6 sm:mt-7 sm:pt-7">{children}</div>
    </section>
  );
}

/** Desktop: the section index under the verification panel. */
function SectionIndex({
  me,
  active,
  onJump,
  docsCount,
}: {
  me: Me;
  active: AccountSection;
  onJump: (k: AccountSection) => void;
  docsCount: number;
}) {
  return (
    <nav aria-label="Passport sections" className="relief hidden rounded-[26px] p-2 lg:block">
      <p className="t-label px-3 pb-2 pt-2.5 text-fg-3">Sections</p>
      <ul className="space-y-0.5">
        {SECTIONS.map((s, i) => {
          const on = active === s.key;
          const raw = s.key === "certifications" ? null : sectionProgress(s.key, me.verification.missing);
          const progress = raw && raw.total > 0 ? raw : null;
          return (
            <li key={s.key}>
              <button
                type="button"
                onClick={() => onJump(s.key)}
                aria-current={on ? "true" : undefined}
                className={cn(
                  "flex w-full items-center justify-between gap-3 rounded-[16px] px-3 py-2.5 text-left text-[14px] font-medium transition-[box-shadow,color,background-color] duration-300 ease-expo",
                  on ? "bg-fg/[0.05] text-fg" : "text-fg-3 hover:text-fg",
                )}
              >
                <span className="flex min-w-0 items-center gap-3">
                  <span className="t-code text-[11px] text-fg-3">{String(i + 1).padStart(2, "0")}</span>
                  <span className="truncate">{s.label}</span>
                </span>
                {progress ? (
                  progress.filled === progress.total ? (
                    <Icon name="check" size={15} className="text-fg-3" label="Complete" />
                  ) : (
                    <span className="t-code text-amber">
                      {progress.filled}/{progress.total}
                    </span>
                  )
                ) : (
                  <span className="t-code text-fg-3">{docsCount}</span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** Phones/tablets: a glass jump strip that sticks under the top cluster. */
function SectionStrip({ active, onJump }: { active: AccountSection; onJump: (k: AccountSection) => void }) {
  return (
    <nav
      aria-label="Jump to section"
      className="sticky z-30 -mx-1 lg:hidden"
      style={{ top: "calc(env(safe-area-inset-top, 0px) + 84px)" }}
    >
      <ul className="glass flex gap-1 overflow-x-auto rounded-full p-1">
        {SECTIONS.map((s) => {
          const on = active === s.key;
          return (
            <li key={s.key} className="flex-1">
              <button
                type="button"
                onClick={() => onJump(s.key)}
                aria-current={on ? "true" : undefined}
                className={cn(
                  "h-9 w-full whitespace-nowrap rounded-full px-3 text-[13px] font-medium transition-colors duration-300",
                  on ? "solid" : "text-fg-2 hover:text-fg",
                )}
              >
                {s.short}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

// ─── Save bar ────────────────────────────────────────────────────────

/**
 * One Save for the whole page. Floats in glass above the dock whenever
 * something is unsaved (or just saved / failed), so it never shifts layout.
 */
function SaveBar({
  visible,
  dirtyLabels,
  saving,
  error,
  justSaved,
  onSave,
}: {
  visible: boolean;
  dirtyLabels: string[];
  saving: boolean;
  error: string | null;
  justSaved: boolean;
  onSave: () => void;
}) {
  const reduce = useReducedMotion();
  const n = dirtyLabels.length;
  return (
    <AnimatePresence>
      {visible ? (
        <motion.div
          role="region"
          aria-label="Unsaved changes"
          initial={reduce ? { opacity: 0 } : { opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduce ? { opacity: 0 } : { opacity: 0, y: 10 }}
          transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
          className="fixed inset-x-0 z-[35] flex justify-center px-4"
          style={{ bottom: "calc(max(14px, env(safe-area-inset-bottom)) + 78px)" }}
        >
          <div className="glass flex w-full max-w-[560px] items-center gap-3 rounded-[24px] py-2 pl-4 pr-2">
            <div className="min-w-0 flex-1" aria-live="polite">
              {n > 0 ? (
                <p className="t-callout flex items-center gap-2 text-fg">
                  <span className="size-2 shrink-0 rounded-full bg-amber" aria-hidden="true" />
                  <span className="min-w-0 truncate">
                    <span className="font-medium">{n} unsaved</span>
                    <span className="text-fg-3"> · {dirtyLabels.join(", ")}</span>
                  </span>
                </p>
              ) : justSaved ? (
                <p className="t-callout flex items-center gap-2 font-medium text-accent">
                  <Icon name="check" size={15} strokeWidth={2} />
                  All changes saved
                </p>
              ) : null}
              {error ? <p className="t-sub mt-0.5 line-clamp-2 text-danger">{error}</p> : null}
            </div>
            <Button onClick={onSave} loading={saving} disabled={n === 0} icon="check" className="shrink-0">
              Save
            </Button>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

// ─── Shared section bits ─────────────────────────────────────────────

/** The `<form>` keeps Enter from doing anything surprising; saving goes through the Save bar. */
function SectionForm({ error, children }: { error: string | null; children: ReactNode }) {
  return (
    <form onSubmit={(e) => e.preventDefault()} noValidate className="grid gap-5">
      {children}
      {error ? <Notice tone="frozen">{error}</Notice> : null}
    </form>
  );
}

/** Multi-select country picker storing ISO codes; picked ones show as solid chips. */
function CountryPicker({
  id,
  label,
  hint,
  error,
  action,
  optional,
  value,
  onChange,
}: {
  id?: string;
  optional?: boolean;
  label: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  action?: ReactNode;
  value: string[];
  onChange: (v: string[]) => void;
}) {
  const options = useMemo(
    () => COUNTRIES.filter((c) => !value.includes(c.code)).map((c) => ({ value: c.code, label: c.name, hint: c.code })),
    [value],
  );
  return (
    <div>
      <Combobox
        id={id}
        label={label}
        hint={hint}
        error={error}
        action={action}
        optional={optional}
        options={options}
        onPick={(code) => onChange(value.includes(code) ? value : [...value, code])}
        placeholder="Search countries"
        emptyText="No more countries to add."
      />
      {value.length ? (
        <ul className="mt-3 flex flex-wrap gap-2" aria-label="Picked countries">
          {value.map((code) => (
            <li key={code}>
              <button
                type="button"
                onClick={() => onChange(value.filter((c) => c !== code))}
                aria-label={`Remove ${countryName(code)}`}
                className="solid inline-flex h-9 items-center gap-1.5 rounded-full pl-3.5 pr-2.5 text-[13px] font-medium"
              >
                {countryName(code)}
                <Icon name="close" size={14} className="opacity-70" />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="t-sub mt-2.5 text-fg-3">None picked yet.</p>
      )}
    </div>
  );
}

/** Hydrate once from `me`; report dirty against that baseline. */
function useBaseline<T>(snapshot: T, ready: boolean, onDirtyChange: (d: boolean) => void) {
  const initial = useRef<string | null>(null);
  const current = JSON.stringify(snapshot);
  if (ready && initial.current === null) initial.current = current;
  const isDirty = initial.current !== null && initial.current !== current;
  useEffect(() => {
    onDirtyChange(isDirty);
  }, [isDirty, onDirtyChange]);
  // The next render (save bar / refetch) recomputes `isDirty` against the
  // new baseline, and the effect above reports it — edits typed while the
  // save was in flight stay dirty.
  const markClean = () => {
    initial.current = current;
  };
  return { isDirty, markClean };
}

// ─── Primary info ────────────────────────────────────────────────────

const PRIMARY_FIELDS = ["fullName", "position", "phone"] as const;

const PrimarySection = forwardRef<SectionHandle, SectionProps>(function PrimarySection({ onDirtyChange }, ref) {
  const { me } = useMe();
  const [fullName, setFullName] = useState("");
  const [position, setPosition] = useState("");
  const [phoneDial, setPhoneDial] = useState("+91");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (hydrated || !me) return;
    const parsed = parsePhone(me.primary.phone);
    setFullName(me.primary.fullName ?? "");
    setPosition(me.primary.position ?? "");
    setPhoneDial(parsed.dial);
    setPhoneNumber(parsed.rest);
    setHydrated(true);
  }, [me, hydrated]);

  const { markClean } = useBaseline({ fullName, position, phoneDial, phoneNumber }, hydrated, onDirtyChange);

  const clear = (k: string) => setErrors((e) => (e[k] ? { ...e, [k]: undefined } : e));

  useImperativeHandle(
    ref,
    () => ({
      async save() {
        setError(null);
        const name = fullName.trim();
        const local: FieldErrors = {};
        if (name.length < 2) local.fullName = "Enter your full name.";
        else if (/\d/.test(name)) local.fullName = "Name should not contain numbers.";
        if (phoneNumber.trim() && !/^[\d\s()-]{4,16}$/.test(phoneNumber.trim())) local.phone = "Digits only, please.";
        setErrors(local);
        const firstLocal = Object.values(local)[0];
        if (firstLocal) throw new Error(`Primary info: ${firstLocal}`);
        try {
          await api.savePrimaryContact({
            fullName: name,
            phone: phoneNumber.trim() ? `${phoneDial} ${phoneNumber.trim()}` : undefined,
            position: position.trim() || undefined,
          });
        } catch (e) {
          const r = routeError(e, PRIMARY_FIELDS);
          if (r.field) setErrors({ [r.field]: r.message });
          else setError(r.message);
          throw new Error(`Primary info: ${r.message}`);
        }
        markClean();
      },
    }),
    [fullName, position, phoneDial, phoneNumber, markClean],
  );

  return (
    <SectionForm error={error}>
      <div>
        <ReadField label="Work email" value={me?.email} />
        <p className="t-sub mt-1.5 text-fg-3">Managed by Corridor — write to support to change it.</p>
      </div>
      <Input
        id="full-name"
        label="Full name"
        required
        maxLength={100}
        autoComplete="name"
        value={fullName}
        onChange={(e) => {
          setFullName(e.target.value);
          clear("fullName");
        }}
        placeholder="e.g. Rhea Kapoor"
        error={errors.fullName}
        action={<VerificationBadge fieldKey="fullName" />}
      />
      <Input
        id="position"
        label="Position / role"
        maxLength={120}
        autoComplete="organization-title"
        value={position}
        onChange={(e) => {
          setPosition(e.target.value);
          clear("position");
        }}
        placeholder="e.g. Export manager"
        error={errors.position}
        action={<VerificationBadge fieldKey="position" />}
      />
      <FieldShell
        label="Phone"
        htmlFor="phone"
        hint="For Corridor ops — not shown on your lots or in a contact reveal."
        error={errors.phone}
        action={<VerificationBadge fieldKey="phone" />}
      >
        <div className="flex gap-2">
          <Select
            aria-label="Country code"
            className="w-[118px] shrink-0"
            value={phoneDial}
            onChange={(e) => {
              setPhoneDial(e.target.value);
              clear("phone");
            }}
            options={DIAL_OPTIONS}
          />
          <Input
            id="phone"
            type="tel"
            inputMode="tel"
            autoComplete="tel-national"
            className="flex-1"
            value={phoneNumber}
            onChange={(e) => {
              setPhoneNumber(e.target.value);
              clear("phone");
            }}
            placeholder="98765 43210"
            aria-invalid={errors.phone ? true : undefined}
          />
        </div>
      </FieldShell>
    </SectionForm>
  );
});

// ─── Company info ────────────────────────────────────────────────────

const COMPANY_FIELDS = [
  "legalName",
  "industry",
  "operatingCountries",
  "websiteUrl",
  "entityType",
  "addressLine",
  "city",
  "state",
  "pincode",
  "country",
  "googleBusinessUrl",
  "facebookUrl",
] as const;

const ENTITY_OPTIONS = (Object.keys(ENTITY_TYPE_SHORT) as EntityType[]).map((value) => ({
  value,
  label: ENTITY_TYPE_SHORT[value],
}));

const COUNTRY_OPTIONS = COUNTRIES.map((c) => ({ value: c.code, label: c.name }));

type PincodeState = "idle" | "loading" | "found" | "not-found" | "down";

const CompanySection = forwardRef<SectionHandle, SectionProps>(function CompanySection({ onDirtyChange }, ref) {
  const { me } = useMe();
  const [legalName, setLegalName] = useState("");
  const [entityType, setEntityType] = useState<EntityType | "">("");
  const [industry, setIndustry] = useState("");
  const [operatingCountries, setOperatingCountries] = useState<string[]>([]);
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [pincode, setPincode] = useState("");
  const [country, setCountry] = useState("IN");
  const [googleBusinessUrl, setGoogleBusinessUrl] = useState("");
  const [facebookUrl, setFacebookUrl] = useState("");
  const [pinState, setPinState] = useState<PincodeState>("idle");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const pinRequest = useRef(0);

  useEffect(() => {
    if (hydrated || !me) return;
    const b = me.business;
    setLegalName(me.businessName ?? b.legalName ?? "");
    setEntityType(b.entityType && b.entityType in ENTITY_TYPE_SHORT ? b.entityType : "");
    setIndustry(b.industry ?? "");
    setOperatingCountries(toCountryCodes(b.operatingCountries));
    setWebsiteUrl(b.websiteUrl ?? "");
    setAddressLine(b.addressLine ?? "");
    setCity(b.city ?? "");
    setState(b.state ?? "");
    setPincode(b.pincode ?? "");
    setCountry(toCountryCodes(b.country ? [b.country] : [])[0] ?? "IN");
    setGoogleBusinessUrl(b.googleBusinessUrl ?? "");
    setFacebookUrl(b.facebookUrl ?? "");
    setHydrated(true);
  }, [me, hydrated]);

  const { markClean } = useBaseline(
    {
      legalName,
      entityType,
      industry,
      operatingCountries,
      websiteUrl,
      addressLine,
      city,
      state,
      pincode,
      country,
      googleBusinessUrl,
      facebookUrl,
    },
    hydrated,
    onDirtyChange,
  );

  const clear = (k: string) => setErrors((e) => (e[k] ? { ...e, [k]: undefined } : e));

  // Older rows may hold an industry outside today's list — keep it selectable.
  const industryOptions = industry && !INDUSTRIES.includes(industry) ? [industry, ...INDUSTRIES] : INDUSTRIES;
  const india = country === "IN";
  // Keep a state typed before (or returned by the lookup) selectable.
  const stateOptions = state && !INDIA_STATES.includes(state) ? [state, ...INDIA_STATES] : INDIA_STATES;
  const countryOptions = COUNTRY_OPTIONS.some((c) => c.value === country)
    ? COUNTRY_OPTIONS
    : [{ value: country, label: country }, ...COUNTRY_OPTIONS];

  /** Indian pincodes: look up city/state once six digits are in. */
  async function lookupPincode(code: string) {
    const id = ++pinRequest.current;
    setPinState("loading");
    try {
      const r = await api.lookupPincode(code);
      if (id !== pinRequest.current) return;
      setCity(r.city || r.district || "");
      setState(normalizeState(r.state) ?? r.state ?? "");
      clear("city");
      clear("state");
      setPinState("found");
    } catch (e) {
      if (id !== pinRequest.current) return;
      setPinState(e instanceof ApiError && e.status === 404 ? "not-found" : "down");
    }
  }

  const onPincode = (raw: string) => {
    const next = india ? raw.replace(/\D/g, "").slice(0, 6) : raw.slice(0, 10);
    setPincode(next);
    clear("pincode");
    pinRequest.current++;
    if (india && next.length === 6) void lookupPincode(next);
    else setPinState("idle");
  };

  const pinHint =
    pinState === "loading"
      ? "Looking up city and state…"
      : pinState === "found"
        ? "City and state filled from the pincode."
        : pinState === "not-found"
          ? <span className="text-amber">Pincode not found — check it, or enter city/state manually.</span>
          : pinState === "down"
            ? <span className="text-amber">Pincode service unavailable — enter city/state manually</span>
            : india
              ? "Six digits — fills city and state."
              : undefined;

  useImperativeHandle(
    ref,
    () => ({
      async save() {
        setError(null);
        const local: FieldErrors = {};
        if (legalName.trim().length < 2) local.legalName = "Enter your registered company name.";
        if (!industry) local.industry = "Pick the closest industry.";
        if (operatingCountries.length === 0) local.operatingCountries = "Pick at least one country.";
        if (india && pincode && !/^\d{6}$/.test(pincode)) local.pincode = "Indian pincodes have six digits.";
        setErrors(local);
        const firstLocal = Object.values(local)[0];
        if (firstLocal) throw new Error(`Company info: ${firstLocal}`);
        try {
          await api.saveCompanyInfo({
            legalName: legalName.trim(),
            entityType: entityType || null,
            industry,
            operatingCountries,
            websiteUrl: websiteUrl.trim() || undefined,
            addressLine: addressLine.trim(),
            city: city.trim(),
            state: state.trim(),
            pincode: pincode.trim(),
            country,
            googleBusinessUrl: googleBusinessUrl.trim(),
            facebookUrl: facebookUrl.trim(),
          });
        } catch (e) {
          const r = routeError(e, COMPANY_FIELDS);
          if (r.field) setErrors({ [r.field]: r.message });
          else setError(r.message);
          throw new Error(`Company info: ${r.message}`);
        }
        markClean();
      },
    }),
    [
      legalName,
      entityType,
      industry,
      operatingCountries,
      websiteUrl,
      addressLine,
      city,
      state,
      pincode,
      country,
      googleBusinessUrl,
      facebookUrl,
      india,
      markClean,
    ],
  );

  return (
    <SectionForm error={error}>
      <Input
        id="legal-name"
        label="Legal company name"
        required
        maxLength={200}
        autoComplete="organization"
        value={legalName}
        onChange={(e) => {
          setLegalName(e.target.value);
          clear("legalName");
        }}
        placeholder="As registered"
        error={errors.legalName}
        action={<VerificationBadge fieldKey="legalName" />}
      />
      <div className="grid gap-5 sm:grid-cols-2">
        <Select
          id="entity-type"
          label="Entity type"
          optional
          value={entityType}
          onChange={(e) => {
            setEntityType(e.target.value as EntityType | "");
            clear("entityType");
          }}
          placeholder="Not specified"
          options={ENTITY_OPTIONS}
          error={errors.entityType}
        />
        <Select
          id="industry"
          label="Industry"
          required
          value={industry}
          onChange={(e) => {
            setIndustry(e.target.value);
            clear("industry");
          }}
          placeholder="Choose the closest match"
          options={industryOptions}
          error={errors.industry}
          action={<VerificationBadge fieldKey="industry" />}
        />
      </div>
      <CountryPicker
        id="operating-countries"
        label="Operating countries"
        hint="Where your company trades today."
        value={operatingCountries}
        onChange={(v) => {
          setOperatingCountries(v);
          clear("operatingCountries");
        }}
        error={errors.operatingCountries}
        action={<VerificationBadge fieldKey="operatingCountries" />}
      />
      <Input
        id="website"
        label="Website"
        optional
        type="url"
        inputMode="url"
        autoComplete="url"
        value={websiteUrl}
        onChange={(e) => {
          setWebsiteUrl(e.target.value);
          clear("websiteUrl");
        }}
        placeholder="https://yourcompany.in"
        error={errors.websiteUrl}
      />

      {/* ── Company address ── */}
      <div role="group" aria-labelledby="company-address-title" className="grid gap-5 border-t border-line pt-6">
        <div>
          <p id="company-address-title" className="t-label text-fg-3">
            Company address
          </p>
          <p className="t-sub mt-1.5 text-fg-3">
            City and state show on your lots; the full address opens only in a contact reveal.
          </p>
        </div>
        <Input
          id="address-line"
          label="Address line"
          optional
          maxLength={200}
          autoComplete="street-address"
          value={addressLine}
          onChange={(e) => {
            setAddressLine(e.target.value);
            clear("addressLine");
          }}
          placeholder="Building, street, area"
          error={errors.addressLine}
        />
        <div className="grid gap-5 sm:grid-cols-2">
          <Select
            id="country"
            label="Country"
            value={country}
            onChange={(e) => {
              setCountry(e.target.value);
              clear("country");
              setPinState("idle");
              pinRequest.current++;
            }}
            options={countryOptions}
            error={errors.country}
          />
          <Input
            id="pincode"
            label={india ? "Pincode" : "Postal code"}
            optional
            inputMode={india ? "numeric" : "text"}
            autoComplete="postal-code"
            maxLength={india ? 6 : 10}
            value={pincode}
            onChange={(e) => onPincode(e.target.value)}
            placeholder={india ? "e.g. 380015" : "Postal code"}
            hint={errors.pincode ? undefined : pinHint}
            error={errors.pincode}
            trailing={
              pinState === "loading" ? (
                <span className="t-code text-fg-3" aria-hidden="true">
                  …
                </span>
              ) : pinState === "found" ? (
                <Icon name="check" size={16} className="text-accent" />
              ) : undefined
            }
          />
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <Input
            id="city"
            label="City"
            optional
            maxLength={100}
            autoComplete="address-level2"
            value={city}
            onChange={(e) => {
              setCity(e.target.value);
              clear("city");
            }}
            placeholder="e.g. Ahmedabad"
            error={errors.city}
          />
          {india ? (
            <Select
              id="state"
              label="State"
              optional
              value={state}
              onChange={(e) => {
                setState(e.target.value);
                clear("state");
              }}
              placeholder="Choose a state"
              options={stateOptions}
              error={errors.state}
            />
          ) : (
            <Input
              id="state"
              label="State / region"
              optional
              maxLength={100}
              autoComplete="address-level1"
              value={state}
              onChange={(e) => {
                setState(e.target.value);
                clear("state");
              }}
              placeholder="State, emirate or region"
              error={errors.state}
            />
          )}
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <Input
            id="google-business-url"
            label="Google Business URL"
            optional
            type="url"
            inputMode="url"
            maxLength={300}
            value={googleBusinessUrl}
            onChange={(e) => {
              setGoogleBusinessUrl(e.target.value);
              clear("googleBusinessUrl");
            }}
            placeholder="https://g.page/yourcompany"
            error={errors.googleBusinessUrl}
          />
          <Input
            id="facebook-url"
            label="Facebook URL"
            optional
            type="url"
            inputMode="url"
            maxLength={300}
            value={facebookUrl}
            onChange={(e) => {
              setFacebookUrl(e.target.value);
              clear("facebookUrl");
            }}
            placeholder="https://facebook.com/yourcompany"
            error={errors.facebookUrl}
          />
        </div>
      </div>
    </SectionForm>
  );
});

// ─── Business profile ────────────────────────────────────────────────

const BUSINESS_FIELDS = [
  "tradePosition",
  "sellerType",
  "exportStatus",
  "targetMarkets",
  "targetBuyerTypes",
  "companyIntroduction",
] as const;

const BusinessSection = forwardRef<SectionHandle, SectionProps>(function BusinessSection({ onDirtyChange }, ref) {
  const { me } = useMe();
  const [tradePosition, setTradePosition] = useState("");
  const [sellerType, setSellerType] = useState("");
  const [exportStatus, setExportStatus] = useState("");
  const [targetMarkets, setTargetMarkets] = useState<string[]>([]);
  const [targetBuyerTypes, setTargetBuyerTypes] = useState<string[]>([]);
  const [companyIntro, setCompanyIntro] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (hydrated || !me) return;
    const b = me.business;
    setTradePosition(b.tradePosition ?? "");
    setSellerType(b.sellerType ?? "");
    setExportStatus(b.exportStatus ?? "");
    setTargetMarkets(toCountryCodes(b.targetMarkets));
    setTargetBuyerTypes(b.targetBuyerTypes ?? []);
    setCompanyIntro(b.companyIntroduction ?? "");
    setHydrated(true);
  }, [me, hydrated]);

  const isSellerSide = tradePosition === "seller" || tradePosition === "both";

  const { markClean } = useBaseline(
    { tradePosition, sellerType, exportStatus, targetMarkets, targetBuyerTypes, companyIntro },
    hydrated,
    onDirtyChange,
  );

  const clear = (k: string) => setErrors((e) => (e[k] ? { ...e, [k]: undefined } : e));

  const sellerTypeOptions = sellerType && !SELLER_TYPES.includes(sellerType) ? [sellerType, ...SELLER_TYPES] : SELLER_TYPES;
  const exportOptions =
    exportStatus && !EXPORT_STATUSES.includes(exportStatus) ? [exportStatus, ...EXPORT_STATUSES] : EXPORT_STATUSES;
  const buyerTypeOptions = useMemo(
    () => [...BUYER_TYPES, ...targetBuyerTypes.filter((t) => !BUYER_TYPES.includes(t))].map((t) => ({ value: t, label: t })),
    [targetBuyerTypes],
  );

  useImperativeHandle(
    ref,
    () => ({
      async save() {
        setError(null);
        if (!tradePosition) {
          const msg = "Pick what you want to do on Corridor.";
          setErrors({ tradePosition: msg });
          throw new Error(`Business profile: ${msg}`);
        }
        setErrors({});
        try {
          await api.saveBusinessProfile({
            tradePosition,
            sellerType: isSellerSide ? sellerType || undefined : undefined,
            exportStatus: isSellerSide ? exportStatus || undefined : undefined,
            targetMarkets,
            targetBuyerTypes: isSellerSide ? targetBuyerTypes : [],
            companyIntroduction: companyIntro.trim() || undefined,
          });
        } catch (e) {
          const r = routeError(e, BUSINESS_FIELDS);
          if (r.field) setErrors({ [r.field]: r.message });
          else setError(r.message);
          throw new Error(`Business profile: ${r.message}`);
        }
        markClean();
      },
    }),
    [
      tradePosition,
      sellerType,
      exportStatus,
      targetMarkets,
      targetBuyerTypes,
      companyIntro,
      isSellerSide,
      markClean,
    ],
  );

  return (
    <SectionForm error={error}>
      <FieldShell
        label="What do you want to do on Corridor?"
        error={errors.tradePosition}
        action={<VerificationBadge fieldKey="tradePosition" />}
      >
        <TradePositionCards
          value={tradePosition}
          onChange={(v) => {
            setTradePosition(v);
            clear("tradePosition");
          }}
          invalid={!!errors.tradePosition}
        />
      </FieldShell>

      {isSellerSide ? (
        <>
          <div className="grid gap-5 sm:grid-cols-2">
            <Select
              label="Which best describes you?"
              optional
              value={sellerType}
              onChange={(e) => setSellerType(e.target.value)}
              placeholder="Not specified"
              options={sellerTypeOptions}
              error={errors.sellerType}
            />
            <Select
              label="Export status"
              optional
              value={exportStatus}
              onChange={(e) => setExportStatus(e.target.value)}
              placeholder="Not specified"
              options={exportOptions}
              error={errors.exportStatus}
            />
          </div>
          <FieldShell label="Who you sell to" optional error={errors.targetBuyerTypes}>
            <ChoiceChips
              label="Target buyer types"
              options={buyerTypeOptions}
              value={targetBuyerTypes}
              onChange={setTargetBuyerTypes}
            />
          </FieldShell>
        </>
      ) : null}

      <CountryPicker
        id="target-markets"
        label="Target markets"
        optional
        hint={tradePosition === "buyer" ? "Countries you want to source from." : "Countries you want to sell to."}
        value={targetMarkets}
        onChange={setTargetMarkets}
        error={errors.targetMarkets}
      />

      <Textarea
        label="Company introduction"
        optional
        counter
        maxLength={800}
        rows={5}
        value={companyIntro}
        onChange={(e) => setCompanyIntro(e.target.value)}
        placeholder="What you do, since when, and what makes your supply different."
        error={errors.companyIntroduction}
      />
    </SectionForm>
  );
});

/** Three choosable relief cards — selected turns solid. Arrow keys move. */
function TradePositionCards({
  value,
  onChange,
  invalid,
}: {
  value: string;
  onChange: (v: string) => void;
  invalid?: boolean;
}) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedIndex = TRADE_POSITIONS.findIndex((t) => t.value === value);
  const focusIndex = selectedIndex === -1 ? 0 : selectedIndex;

  return (
    <div
      id="trade-position"
      role="radiogroup"
      aria-label="Trade position"
      aria-invalid={invalid || undefined}
      className="grid gap-3 sm:grid-cols-3"
    >
      {TRADE_POSITIONS.map((t, i) => {
        const on = t.value === value;
        return (
          <button
            key={t.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={on}
            tabIndex={i === focusIndex ? 0 : -1}
            onClick={() => onChange(t.value)}
            onKeyDown={(e) => {
              const delta = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
              if (!delta) return;
              e.preventDefault();
              const next = (i + delta + TRADE_POSITIONS.length) % TRADE_POSITIONS.length;
              onChange(TRADE_POSITIONS[next].value);
              refs.current[next]?.focus();
            }}
            className={cn(
              // Reference role cards (portal /onboarding): relief to choose,
              // solid once chosen with the icon on a lime disc.
              "relative flex items-center gap-4 rounded-[24px] p-4 text-left transition-[box-shadow,background-color,color,transform] duration-500 ease-expo sm:min-h-[176px] sm:flex-col sm:items-start sm:gap-0 sm:rounded-[28px] sm:p-6",
              on ? "solid" : "relief text-fg hover:-translate-y-0.5",
              invalid && !on && "[box-shadow:var(--relief),0_0_0_1.5px_var(--c-danger)]",
            )}
          >
            <span
              className={cn(
                "grid size-12 shrink-0 place-items-center rounded-full",
                on ? "bg-lime text-ink" : "well text-fg-2",
              )}
            >
              <Icon name={t.icon} size={20} />
            </span>
            <span className="min-w-0 sm:mt-auto sm:pt-6">
              <span className="t-title3 block">{t.title}</span>
              <span className={cn("t-sub mt-1 block", on ? "text-cream/65" : "text-fg-3")}>{t.body}</span>
            </span>
            {on ? (
              <Icon name="check" size={16} strokeWidth={2} className="absolute right-4 top-4 text-cream/80 sm:right-5 sm:top-5" />
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

// ─── Loading ─────────────────────────────────────────────────────────

function PassportSkeleton() {
  return (
    <div className="space-y-10 pt-6 sm:pt-10" aria-busy="true" aria-label="Loading your passport">
      <div className="space-y-3">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-10 w-56" />
        <Skeleton className="h-4 w-80 max-w-full" />
      </div>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Skeleton className="h-[250px] rounded-[34px]" />
          <Skeleton className="h-[420px] rounded-[30px]" />
        </div>
        <Skeleton className="hidden h-[380px] rounded-[30px] lg:block" />
      </div>
    </div>
  );
}
