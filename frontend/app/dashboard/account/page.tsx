"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMe } from "@/lib/useMe";
import { api } from "@/lib/api";
import {
  AuthButton,
  AuthField,
  AuthInput,
  AuthSelect,
  AuthTextarea,
} from "@/components/auth/AuthCard";
import { CertificationsBlock } from "@/components/account/CertificationsBlock";
import { VerificationBadge } from "@/components/account/VerificationBadge";
import { SendForVerificationControl } from "@/components/account/SendForVerificationBar";

// Scroll-spy anchor keys. Must match the element ids set on each
// section's wrapper below; the sticky strip uses these to highlight the
// current one as the user scrolls.
type SectionKey = "primary" | "company" | "business" | "certifications";

const SECTIONS: { key: SectionKey; label: string }[] = [
  { key: "primary", label: "Primary info" },
  { key: "company", label: "Company info" },
  { key: "business", label: "Business profile" },
  { key: "certifications", label: "Certifications" },
];

const COUNTRIES = [
  "India", "United Arab Emirates", "Saudi Arabia", "Oman", "Qatar", "Kuwait",
  "Bahrain", "United States", "United Kingdom", "Germany", "Netherlands",
  "Singapore", "Malaysia", "Indonesia", "Thailand", "Vietnam", "Japan",
  "China", "South Korea", "Australia",
];

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

const DEPARTMENTS = [
  "Founder / Owner",
  "Sales / Business Development",
  "Exports / Trade",
  "Sourcing / Procurement",
  "Operations / Supply Chain",
  "Finance / Accounts",
  "Other",
];

const TRADE_POSITIONS = [
  { value: "seller", label: "I want to sell (I have supply)" },
  { value: "buyer", label: "I want to buy (I need supply)" },
  { value: "both", label: "Both — I trade in both directions" },
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

// Country dial codes for the phone field. Ordered with the most common
// Cor1x markets first; alphabetical after that.
const COUNTRY_CODES: { name: string; dial: string; flag: string }[] = [
  { name: "India", dial: "+91", flag: "🇮🇳" },
  { name: "United Arab Emirates", dial: "+971", flag: "🇦🇪" },
  { name: "Saudi Arabia", dial: "+966", flag: "🇸🇦" },
  { name: "Oman", dial: "+968", flag: "🇴🇲" },
  { name: "Qatar", dial: "+974", flag: "🇶🇦" },
  { name: "Kuwait", dial: "+965", flag: "🇰🇼" },
  { name: "Bahrain", dial: "+973", flag: "🇧🇭" },
  { name: "United States", dial: "+1", flag: "🇺🇸" },
  { name: "United Kingdom", dial: "+44", flag: "🇬🇧" },
  { name: "Germany", dial: "+49", flag: "🇩🇪" },
  { name: "Netherlands", dial: "+31", flag: "🇳🇱" },
  { name: "Singapore", dial: "+65", flag: "🇸🇬" },
  { name: "Malaysia", dial: "+60", flag: "🇲🇾" },
  { name: "Indonesia", dial: "+62", flag: "🇮🇩" },
  { name: "Thailand", dial: "+66", flag: "🇹🇭" },
  { name: "Vietnam", dial: "+84", flag: "🇻🇳" },
  { name: "Japan", dial: "+81", flag: "🇯🇵" },
  { name: "China", dial: "+86", flag: "🇨🇳" },
  { name: "South Korea", dial: "+82", flag: "🇰🇷" },
  { name: "Australia", dial: "+61", flag: "🇦🇺" },
];

function parsePhone(raw: string | null | undefined): {
  dial: string;
  rest: string;
} {
  if (!raw) return { dial: "+91", rest: "" };
  const trimmed = raw.trim();
  // Find the dial code that this value starts with (longest match wins so
  // "+971" beats "+9").
  const sortedDials = [...COUNTRY_CODES].sort(
    (a, b) => b.dial.length - a.dial.length,
  );
  for (const c of sortedDials) {
    if (trimmed.startsWith(c.dial)) {
      return { dial: c.dial, rest: trimmed.slice(c.dial.length).trim() };
    }
  }
  return { dial: "+91", rest: trimmed };
}

export default function MyAccountPage() {
  const params = useSearchParams();
  const [active, setActive] = useState<SectionKey>("primary");

  // Deep-links: ?tab= jumps to a section; ?doc= scrolls to one of the
  // uploaded doc rows inside the Certifications card. Both come from
  // the dashboard rejection popups.
  useEffect(() => {
    const next = params.get("tab");
    if (next === "primary" || next === "company" || next === "business") {
      setTimeout(() => {
        document.getElementById(`section-${next}`)?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 100);
    }
    const docId = params.get("doc");
    if (docId) {
      setTimeout(() => {
        document.getElementById(`doc-${docId}`)?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
      }, 500);
    }
  }, [params]);

  // Scroll-spy: whichever section's top edge is above the sticky-strip
  // line is the "current" one. Deterministic — unlike IntersectionObserver
  // this always has a defined answer, including after fast scrolls past
  // multiple sections.
  useEffect(() => {
    function updateActive() {
      // 160px matches the dashboard header + sticky strip height; the
      // active section flips the moment its top crosses just below the
      // strip, which is the perceptual "I'm in this section" line.
      const line = window.scrollY + 160;
      let current: SectionKey = "primary";
      for (const s of SECTIONS) {
        const el = document.getElementById(`section-${s.key}`);
        if (el && el.offsetTop <= line) current = s.key;
      }
      setActive(current);
    }
    updateActive();
    window.addEventListener("scroll", updateActive, { passive: true });
    window.addEventListener("resize", updateActive);
    return () => {
      window.removeEventListener("scroll", updateActive);
      window.removeEventListener("resize", updateActive);
    };
  }, []);

  function jumpTo(key: SectionKey) {
    document.getElementById(`section-${key}`)?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 pb-16">
      <header>
        <p className="text-[10px] uppercase tracking-widest text-paper-muted">
          Account
        </p>
        <h1 className="mt-2 text-display text-paper">My Account</h1>
        <p className="mt-2 text-sm text-paper-muted">
          Review and update your personal info, company details, business
          profile, and certifications — all on one page.
        </p>
      </header>

      {/* Sticky scroll-spy strip. ``top-16`` leaves room for the
          dashboard's own sticky top bar; adjust if that bar's height
          changes. ``backdrop-blur`` keeps text readable when a section
          scrolls underneath. */}
      <nav
        aria-label="Jump to section"
        className="sticky top-16 z-20 -mx-6 md:-mx-0 border-b border-line-soft bg-ink/85 backdrop-blur px-6 md:rounded-pill md:border md:px-4"
      >
        <ul className="flex gap-4 overflow-x-auto py-2 text-[12px] font-medium">
          {SECTIONS.map((s) => {
            const isActive = active === s.key;
            return (
              <li key={s.key}>
                <button
                  type="button"
                  onClick={() => jumpTo(s.key)}
                  aria-current={isActive ? "true" : undefined}
                  className={`relative whitespace-nowrap rounded-pill px-3 py-1.5 transition ${
                    isActive
                      ? "bg-accent/15 text-accent"
                      : "text-paper-muted hover:text-paper"
                  }`}
                >
                  {s.label}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Each section is its own card so the visual chunking of the
          old tabs survives. ``scroll-mt-28`` keeps the header visible
          below the sticky strip when the user jumps or deep-links. */}
      <section
        id="section-primary"
        className="scroll-mt-28 rounded-card border border-line-soft bg-ink-soft/70 p-6 md:p-8"
      >
        <PrimarySection />
      </section>

      <section
        id="section-company"
        className="scroll-mt-28 rounded-card border border-line-soft bg-ink-soft/70 p-6 md:p-8"
      >
        <CompanySection />
      </section>

      <section
        id="section-business"
        className="scroll-mt-28 rounded-card border border-line-soft bg-ink-soft/70 p-6 md:p-8"
      >
        <BusinessSection />
      </section>

      <section
        id="section-certifications"
        className="scroll-mt-28 rounded-card border border-line-soft bg-ink-soft/70 p-6 md:p-8"
      >
        <div className="border-b border-line-soft pb-4 mb-2">
          <h2 className="text-display text-paper tracking-tight">
            Certifications &amp; documents
          </h2>
          <p className="mt-1 text-sm text-paper-muted">
            Attach the certificates buyers trust — these feed the admin
            review and your future trust-score tier.
          </p>
        </div>
        <CertificationsBlock />
      </section>

      {/* Verification submission — one place at the end of the page,
          renders differently based on verification state (disabled
          button / enabled button / "Under review" / "Verified"). */}
      <div className="flex justify-end pt-2">
        <SendForVerificationControl />
      </div>
    </div>
  );
}

// ─── Primary info ────────────────────────────────────────────────────

function PrimarySection() {
  const { me, refetch } = useMe();
  const [fullName, setFullName] = useState("");
  const [position, setPosition] = useState("");
  const [phoneDial, setPhoneDial] = useState("+91");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [department, setDepartment] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const hydrated = useRef(false);

  // Hydrate once per user. Repeated /me refetches would otherwise reset
  // every field the user hasn't committed yet.
  useEffect(() => {
    if (hydrated.current || !me) return;
    setFullName(me.primary.fullName ?? "");
    setPosition(me.primary.position ?? "");
    const parsed = parsePhone(me.primary.phone);
    setPhoneDial(parsed.dial);
    setPhoneNumber(parsed.rest);
    setDepartment(me.primary.department ?? "");
    hydrated.current = true;
  }, [me]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (/\d/.test(fullName)) {
      setError("Name should not contain numbers.");
      return;
    }
    const phone = phoneNumber.trim()
      ? `${phoneDial} ${phoneNumber.trim()}`
      : undefined;
    setSaving(true);
    try {
      await api.savePrimaryContact({
        fullName: fullName.trim(),
        phone,
        department: department || undefined,
        position: position.trim() || undefined,
      });
      await refetch();
      setSavedAt(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <SectionForm
      title="Primary info"
      subtitle="You and how buyers reach you."
      error={error}
      saving={saving}
      savedAt={savedAt}
      onSubmit={onSubmit}
    >
      <AuthField label="Email" hint="Managed by Cor1x — contact support to change.">
        <AuthInput type="email" value={me?.email ?? ""} readOnly disabled />
      </AuthField>
      <AuthField
        label="Full name"
        anchor="full-name"
        labelExtra={<VerificationBadge fieldKey="fullName" />}
      >
        <AuthInput
          required
          maxLength={100}
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          placeholder="e.g. Pegan Raj"
        />
      </AuthField>
      <div className="grid gap-5 sm:grid-cols-2">
        <AuthField
          label="Position / role"
          anchor="position"
          labelExtra={<VerificationBadge fieldKey="position" />}
        >
          <AuthInput
            maxLength={120}
            value={position}
            onChange={(e) => setPosition(e.target.value)}
            placeholder="e.g. Export Manager"
          />
        </AuthField>
        <AuthField label="Department">
          <AuthSelect
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
          >
            <option value="">Not specified</option>
            {DEPARTMENTS.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </AuthSelect>
        </AuthField>
      </div>
      <AuthField
        label="Phone"
        anchor="phone"
        hint="Buyers only see this once they reveal your contact."
        labelExtra={<VerificationBadge fieldKey="phone" />}
      >
        <div className="flex gap-2">
          <DialCodePicker value={phoneDial} onChange={setPhoneDial} />
          <AuthInput
            type="tel"
            inputMode="tel"
            value={phoneNumber}
            onChange={(e) => setPhoneNumber(e.target.value)}
            placeholder="98xxxxxxxx"
            className="flex-1"
          />
        </div>
      </AuthField>
    </SectionForm>
  );
}

// ─── Company info ────────────────────────────────────────────────────

function CompanySection() {
  const { me, refetch } = useMe();
  const [legalName, setLegalName] = useState("");
  const [industry, setIndustry] = useState("");
  const [operatingCountries, setOperatingCountries] = useState<string[]>([]);
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const hydrated = useRef(false);

  // Hydrate once per user. We intentionally skip `business` as a dep so
  // the form doesn't clobber the user's edits every /me refetch.
  useEffect(() => {
    if (hydrated.current || !me) return;
    const business = me.business;
    setLegalName(me.businessName ?? business?.legalName ?? "");
    setIndustry(business?.industry ?? "");
    setOperatingCountries(business?.operatingCountries ?? []);
    setWebsiteUrl(business?.websiteUrl ?? "");
    hydrated.current = true;
  }, [me]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await api.saveCompanyInfo({
        legalName: legalName.trim(),
        industry,
        operatingCountries,
        websiteUrl: websiteUrl.trim() || undefined,
      });
      await refetch();
      setSavedAt(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <SectionForm
      title="Company info"
      subtitle="The public identity buyers see on your listings."
      error={error}
      saving={saving}
      savedAt={savedAt}
      onSubmit={onSubmit}
    >
      <AuthField
        label="Legal company name"
        anchor="legal-name"
        labelExtra={<VerificationBadge fieldKey="legalName" />}
      >
        <AuthInput
          required
          maxLength={200}
          value={legalName}
          onChange={(e) => setLegalName(e.target.value)}
        />
      </AuthField>
      <AuthField
        label="Industry"
        anchor="industry"
        labelExtra={<VerificationBadge fieldKey="industry" />}
      >
        <AuthSelect
          required
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
        >
          <option value="" disabled>Choose the closest match…</option>
          {INDUSTRIES.map((i) => (
            <option key={i} value={i}>{i}</option>
          ))}
        </AuthSelect>
      </AuthField>
      <AuthField
        label="Operating countries"
        anchor="operating-countries"
        labelExtra={<VerificationBadge fieldKey="operatingCountries" />}
      >
        <CountrySelector
          selected={operatingCountries}
          onChange={setOperatingCountries}
        />
      </AuthField>
      <AuthField label="Website (optional)">
        <AuthInput
          type="url"
          value={websiteUrl}
          onChange={(e) => setWebsiteUrl(e.target.value)}
          placeholder="https://yourcompany.in"
        />
      </AuthField>
    </SectionForm>
  );
}

// ─── Business profile ────────────────────────────────────────────────

function BusinessSection() {
  const { me, refetch } = useMe();
  const [tradePosition, setTradePosition] = useState("");
  const [sellerType, setSellerType] = useState("");
  const [exportStatus, setExportStatus] = useState("");
  const [targetMarkets, setTargetMarkets] = useState<string[]>([]);
  const [mainObjective, setMainObjective] = useState("");
  const [companyIntro, setCompanyIntro] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const hydrated = useRef(false);

  // Hydrate once per user. We DELIBERATELY avoid `[business]` as the dep —
  // every /me refetch returns a fresh object reference, which would wipe
  // the user's unsaved edits (e.g. a half-selected country list).
  useEffect(() => {
    if (hydrated.current) return;
    const business = me?.business;
    if (!me || !business) return;
    setTradePosition(business.tradePosition ?? "");
    setSellerType(business.sellerType ?? "");
    setExportStatus(business.exportStatus ?? "");
    setTargetMarkets(business.targetMarkets ?? []);
    setMainObjective(business.mainObjective ?? "");
    setCompanyIntro(business.companyIntroduction ?? "");
    hydrated.current = true;
  }, [me]);

  const isSellerSide = tradePosition === "seller" || tradePosition === "both";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await api.saveBusinessProfile({
        tradePosition,
        sellerType: isSellerSide ? sellerType || undefined : undefined,
        exportStatus: isSellerSide ? exportStatus || undefined : undefined,
        targetMarkets,
        targetBuyerTypes: [],
        mainObjective: mainObjective.trim() || undefined,
        companyIntroduction: companyIntro.trim() || undefined,
      });
      await refetch();
      setSavedAt(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <SectionForm
      title="Business profile"
      subtitle="How Cor1x matches you with the right counterparties."
      error={error}
      saving={saving}
      savedAt={savedAt}
      onSubmit={onSubmit}
    >
      <AuthField
        label="What do you want to do on Cor1x?"
        anchor="trade-position"
        hint="Click a tile to select it. Click again to clear."
        labelExtra={<VerificationBadge fieldKey="tradePosition" />}
      >
        <div className="grid gap-2 sm:grid-cols-3">
          {TRADE_POSITIONS.map((tp) => {
            const active = tradePosition === tp.value;
            return (
              <button
                key={tp.value}
                type="button"
                onClick={() =>
                  setTradePosition(active ? "" : tp.value)
                }
                aria-pressed={active}
                className={`cursor-pointer rounded-field border px-4 py-3 text-left text-sm transition ${
                  active
                    ? "border-accent bg-accent/10 text-paper"
                    : "border-line-soft bg-ink text-paper-soft hover:border-line"
                }`}
              >
                {tp.label}
              </button>
            );
          })}
        </div>
      </AuthField>

      {isSellerSide && (
        <div className="grid gap-5 sm:grid-cols-2">
          <AuthField label="Which best describes you?">
            <AuthSelect
              value={sellerType}
              onChange={(e) => setSellerType(e.target.value)}
            >
              <option value="">Not specified</option>
              {SELLER_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </AuthSelect>
          </AuthField>
          <AuthField label="Export status">
            <AuthSelect
              value={exportStatus}
              onChange={(e) => setExportStatus(e.target.value)}
            >
              <option value="">Not specified</option>
              {EXPORT_STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </AuthSelect>
          </AuthField>
        </div>
      )}

      <AuthField
        label="Target markets"
        hint={
          tradePosition === "buyer"
            ? "Countries you want to source from."
            : "Countries you want to sell to."
        }
      >
        <CountrySelector selected={targetMarkets} onChange={setTargetMarkets} />
      </AuthField>

      <AuthField label="Main objective (optional)">
        <AuthInput
          maxLength={200}
          value={mainObjective}
          onChange={(e) => setMainObjective(e.target.value)}
          placeholder="e.g. Reach GCC importers for premium basmati rice."
        />
      </AuthField>

      <AuthField label="Company introduction (optional)">
        <AuthTextarea
          maxLength={800}
          value={companyIntro}
          onChange={(e) => setCompanyIntro(e.target.value)}
          placeholder="Tell buyers what you do, since when, and what makes your supply unique."
        />
      </AuthField>
    </SectionForm>
  );
}

// ─── Shared bits ─────────────────────────────────────────────────────

function SectionForm({
  title,
  subtitle,
  error,
  saving,
  savedAt,
  onSubmit,
  children,
}: {
  title: string;
  subtitle: string;
  error: string | null;
  saving: boolean;
  savedAt: number | null;
  onSubmit: (e: React.FormEvent) => void;
  children: React.ReactNode;
}) {
  const showSaved = savedAt && Date.now() - savedAt < 3000;
  return (
    <form onSubmit={onSubmit} className="grid gap-5">
      <div className="border-b border-line-soft pb-4 mb-2">
        <h2 className="text-display text-paper tracking-tight">{title}</h2>
        <p className="mt-1 text-sm text-paper-muted">{subtitle}</p>
      </div>
      {children}
      {error && (
        <div className="rounded-field border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
          {error}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3 pt-2">
        <AuthButton type="submit" loading={saving} className="sm:w-auto sm:px-6">
          Save changes
        </AuthButton>
        {showSaved && (
          <span className="text-xs text-accent">Saved ✓</span>
        )}
      </div>
    </form>
  );
}

function DialCodePicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (dial: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement | null>(null);

  // Dismiss on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return COUNTRY_CODES;
    return COUNTRY_CODES.filter(
      (c) =>
        c.name.toLowerCase().includes(needle) ||
        c.dial.includes(needle),
    );
  }, [q]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="w-[92px] flex-none inline-flex items-center justify-between rounded-field border border-line-soft bg-ink px-3 py-3 text-paper hover:border-line transition"
      >
        <span className="text-sm font-medium">{value}</span>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-paper-muted"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && (
        <div className="absolute left-0 top-full z-20 mt-1 w-72 rounded-field border border-line-soft bg-ink-elevated shadow-card">
          <div className="p-2 border-b border-line-soft">
            <input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search country or code…"
              className="w-full rounded-field border border-line-soft bg-ink px-3 py-2 text-sm text-paper placeholder-mute-soft/60 focus:outline-none focus:border-accent/60"
            />
          </div>
          <ul className="max-h-56 overflow-y-auto py-1">
            {filtered.length === 0 && (
              <li className="px-3 py-2 text-xs text-paper-muted">
                No match.
              </li>
            )}
            {filtered.map((c) => {
              const selected = c.dial === value;
              return (
                <li key={c.name}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange(c.dial);
                      setOpen(false);
                      setQ("");
                    }}
                    className={`w-full flex items-center gap-2 px-3 py-2 text-left text-sm transition ${
                      selected
                        ? "bg-accent/10 text-paper"
                        : "text-paper-soft hover:bg-ink hover:text-paper"
                    }`}
                  >
                    <span className="text-base w-5">{c.flag}</span>
                    <span className="flex-1 truncate">{c.name}</span>
                    <span className="text-xs text-paper-muted font-mono">
                      {c.dial}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

function CountrySelector({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (v: string[]) => void;
}) {
  const [q, setQ] = useState("");
  const filtered = useMemo(
    () =>
      COUNTRIES.filter(
        (c) =>
          !selected.includes(c) &&
          (q.trim() === "" || c.toLowerCase().includes(q.toLowerCase())),
      ).slice(0, 8),
    [selected, q],
  );
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2 min-h-[36px]">
        {selected.length === 0 && (
          <span className="text-xs text-paper-muted/70">
            Nothing selected yet
          </span>
        )}
        {selected.map((c) => (
          <button
            type="button"
            key={c}
            onClick={() => onChange(selected.filter((x) => x !== c))}
            className="inline-flex items-center gap-1.5 rounded-pill border border-accent/40 bg-accent/10 px-3 py-1 text-xs text-paper hover:bg-accent/20 transition"
          >
            <span>{c}</span>
            <span className="text-paper-muted/70">×</span>
          </button>
        ))}
      </div>
      <div className="relative">
        <AuthInput
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search countries…"
        />
        {q && filtered.length > 0 && (
          <div className="absolute z-10 mt-1 w-full rounded-field border border-line-soft bg-ink-elevated shadow-card max-h-56 overflow-y-auto">
            {filtered.map((c) => (
              <button
                type="button"
                key={c}
                onClick={() => {
                  onChange([...selected, c]);
                  setQ("");
                }}
                className="w-full px-3 py-2 text-sm text-paper-soft hover:bg-ink hover:text-paper text-left"
              >
                {c}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
