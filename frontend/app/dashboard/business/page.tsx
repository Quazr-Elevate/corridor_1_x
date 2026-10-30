"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError, type KybCountry, type Me } from "@/lib/api";
import { useFocusField } from "@/lib/useFocusField";
import { useMe } from "@/lib/useMe";
import { useDirtyFlag } from "@/lib/useUnsavedGuard";
import { DETAILS_PATH, fieldByKey, statusMeta } from "@/lib/verification";
import { focusField } from "@/lib/useFocusField";
import { ReviewConfirmProvider, useReviewConfirm } from "@/components/business/ReviewConfirm";
import { COUNTRIES, countryName } from "@/components/account/countries";
import { SendForVerificationBar } from "@/components/account/SendForVerificationBar";
import { BrandingSection } from "@/components/business/BrandingSection";
import { KybSection } from "@/components/business/KybSection";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Input, Select } from "@/components/ui/Field";
import { Notice, PageHeader, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";

/**
 * Business profile — what a business fills in to get verified:
 *   1. Company: registered name, address and country (the KYB document list
 *      follows the country),
 *   2. Branding: business image and banner (public; the dashboard hero),
 *   3. Business verification: the KYB documents admins require for the
 *      country, plus any other certificate.
 * Then "Send for verification" puts it in the Corridor ops queue.
 *
 * Right after sign-up it opens with `?welcome=1` and can be skipped.
 */
export default function BusinessProfilePage() {
  return (
    <Suspense fallback={<ProfileSkeleton />}>
      <BusinessProfile />
    </Suspense>
  );
}

function BusinessProfile() {
  const { me, refetch } = useMe();
  const router = useRouter();
  const welcome = useSearchParams()?.get("welcome") === "1";
  const [companyDirty, setCompanyDirty] = useState(false);
  useFocusField();

  if (!me) return <ProfileSkeleton />;
  return (
    <ReviewConfirmProvider verified={me.verification.status === "verified"}>
      <BusinessProfileBody me={me} refetch={refetch} welcome={welcome} router={router} companyDirty={companyDirty} setCompanyDirty={setCompanyDirty} />
    </ReviewConfirmProvider>
  );
}

function BusinessProfileBody({
  me,
  refetch,
  welcome,
  router,
  companyDirty,
  setCompanyDirty,
}: {
  me: Me;
  refetch: () => Promise<void>;
  welcome: boolean;
  router: ReturnType<typeof useRouter>;
  companyDirty: boolean;
  setCompanyDirty: (d: boolean) => void;
}) {
  const meta = statusMeta(me.verification.status);
  const name = me.business.legalName || me.businessName || "Your company";

  return (
    <div className="space-y-8 pb-24">
      <PageHeader
        eyebrow={welcome ? "Welcome to Corridor One X" : "Business profile"}
        title={welcome ? "Set up your business profile." : name}
        subtitle={
          welcome
            ? "Add your company details and documents so Corridor ops can verify you. You can do this later."
            : "Your company details, branding and verification documents."
        }
        actions={
          welcome ? (
            <Button variant="secondary" iconRight="arrow-right" onClick={() => router.push("/dashboard")}>
              Skip for now
            </Button>
          ) : (
            <Chip tone={meta.tone}>{meta.label}</Chip>
          )
        }
      />

      {me.verification.status === "rejected" ? <ToFix me={me} /> : null}
      {me.verification.status === "pending_verification" ? (
        <Notice tone="move">Corridor ops is reviewing your business. You can keep editing — changes go into the same review.</Notice>
      ) : null}

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start">
        <div className="space-y-8">
          <Section n="01" title="Company" sub="Your registered business name and address.">
            <CompanyForm me={me} onSaved={refetch} onDirty={setCompanyDirty} />
          </Section>

          <Section n="02" title="Branding" sub="Shown on your dashboard and, later, your company page.">
            <BrandingSection
              logoUrl={me.branding?.logoUrl ?? null}
              bannerUrl={me.branding?.bannerUrl ?? null}
              companyName={name}
              onChanged={refetch}
            />
          </Section>

          <Section
            n="03"
            id="kyb"
            title="Business verification"
            sub="The documents Corridor ops checks for your country. Required ones are marked."
          >
            <KybSection
              country={me.business.country ?? "IN"}
              rejectedItems={me.verification.status === "rejected" ? me.verification.rejectedItems ?? [] : []}
              onChanged={() => void refetch()}
            />
          </Section>

          <p className="t-sub text-fg-3">
            Trade details, contact person and more are on your{" "}
            <Link href={DETAILS_PATH} className="font-medium text-fg underline-offset-4 hover:underline">
              Passport
            </Link>
            .
          </p>
        </div>

        <aside className="lg:sticky lg:top-24">
          <SendForVerificationBar dirty={companyDirty} />
          {welcome ? (
            <Button variant="quiet" block className="mt-3" onClick={() => router.push("/dashboard")}>
              I’ll finish this later
            </Button>
          ) : null}
        </aside>
      </div>
    </div>
  );
}

/** After a rejection: the reason plus one chip per flagged item that jumps to it. */
function ToFix({ me }: { me: Me }) {
  const v = me.verification;
  const items = (v.rejectedItems ?? [])
    .map((k, i) => fieldByKey(k, v.rejectedItemLabels?.[i]))
    .filter((f): f is NonNullable<typeof f> => Boolean(f));
  return (
    <Notice tone="frozen" title="Corridor ops asked for changes">
      <span className="block">{v.rejectedReason || "Check your details and send again."}</span>
      {items.length ? (
        <span className="mt-3 flex flex-wrap items-center gap-2">
          <span className="t-label">To fix</span>
          {items.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => focusField(f.anchor)}
              className="inline-flex items-center gap-1.5 rounded-full bg-danger/10 px-3 py-1 text-[13px] font-medium text-danger hover:bg-danger/15"
            >
              {f.label}
              <span aria-hidden="true">→</span>
            </button>
          ))}
        </span>
      ) : null}
      <span className="t-sub mt-3 block">Fix these, then send for verification again.</span>
    </Notice>
  );
}

function Section({
  n,
  id,
  title,
  sub,
  children,
}: {
  n: string;
  id?: string;
  title: string;
  sub: string;
  children: ReactNode;
}) {
  return (
    <section id={id ? `section-${id}` : undefined} aria-labelledby={`h-${n}`} className="animate-rise">
      <div className="mb-4">
        <p className="t-code text-[11px] text-fg-3">{n}</p>
        <h2 id={`h-${n}`} className="t-title3 mt-1 text-fg">
          {title}
        </h2>
        <p className="t-sub mt-1 text-fg-3">{sub}</p>
      </div>
      {children}
    </section>
  );
}

// ── Company ────────────────────────────────────────────────────────────

interface CompanyValues {
  legalName: string;
  country: string;
  addressLine: string;
  city: string;
  state: string;
  pincode: string;
}

function fromMe(me: Me): CompanyValues {
  const b = me.business;
  return {
    legalName: b.legalName ?? me.businessName ?? "",
    country: b.country ?? "IN",
    addressLine: b.addressLine ?? "",
    city: b.city ?? "",
    state: b.state ?? "",
    pincode: b.pincode ?? "",
  };
}

type CompanyErrors = Partial<Record<keyof CompanyValues, string>>;

function CompanyForm({
  me,
  onSaved,
  onDirty,
}: {
  me: Me;
  onSaved: () => Promise<void>;
  onDirty: (dirty: boolean) => void;
}) {
  const toast = useToast();
  const confirmReview = useReviewConfirm();
  const [countries, setCountries] = useState<KybCountry[] | null>(null);
  useEffect(() => {
    api.kybCountries().then(setCountries).catch(() => setCountries(null));
  }, []);
  const flagged = new Set(me.verification.status === "rejected" ? me.verification.rejectedItems ?? [] : []);
  // Re-sync only when the saved values change — not whenever a fresh `me`
  // object arrives (that would wipe what the user is typing).
  const initialKey = JSON.stringify(fromMe(me));
  const initial = useMemo<CompanyValues>(() => JSON.parse(initialKey), [initialKey]);
  const [v, setV] = useState<CompanyValues>(initial);
  const [errors, setErrors] = useState<CompanyErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const dirty = (Object.keys(v) as (keyof CompanyValues)[]).some((k) => v[k].trim() !== initial[k].trim());
  useDirtyFlag(dirty);

  useEffect(() => onDirty(dirty), [dirty, onDirty]);
  useEffect(() => setV(initial), [initial]);

  const set = (k: keyof CompanyValues) => (value: string) => {
    setV((x) => ({ ...x, [k]: value }));
    setErrors((e) => ({ ...e, [k]: undefined }));
  };

  async function submit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    const fe: CompanyErrors = {};
    if (v.legalName.trim().length < 2) fe.legalName = "Enter the registered company name.";
    if (!v.addressLine.trim()) fe.addressLine = "Enter the registered address.";
    if (!v.city.trim()) fe.city = "Enter the city.";
    const pattern = countries?.find((c) => c.code === v.country)?.postalPattern;
    if (pattern && v.pincode.trim() && !new RegExp(`^(?:${pattern})$`).test(v.pincode.trim().toUpperCase())) {
      fe.pincode = `That doesn’t look like a valid ${countries?.find((c) => c.code === v.country)?.postalLabel ?? "postal code"}.`;
    }
    setErrors(fe);
    if (Object.keys(fe).length) return;
    const norm = (x: string) => x.trim().replace(/\s+/g, " ").toLowerCase();
    const kybChanged = (["legalName", "addressLine", "city", "country"] as const).some((k) => norm(v[k]) !== norm(initial[k]));
    if (kybChanged && !(await confirmReview("your company details"))) return;
    setSaving(true);
    try {
      await api.saveBusinessProfileV2({
        legalName: v.legalName.trim(),
        country: v.country,
        addressLine: v.addressLine.trim(),
        city: v.city.trim(),
        state: v.state.trim(),
        pincode: v.pincode.trim(),
      });
      await onSaved();
      toast("Company details saved", "verified");
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Couldn’t save. Try again.");
    } finally {
      setSaving(false);
    }
  }

  const countryChanged = v.country !== initial.country;
  // Only countries Corridor ops has set up (plus the saved one, so it shows).
  const countryOptions = [
    ...(countries ?? []).map((c) => ({ value: c.code, label: `${c.flag ?? ""} ${c.name}`.trim() })),
    ...(countries && !countries.some((c) => c.code === initial.country)
      ? [{ value: initial.country, label: `${COUNTRIES.find((x) => x.code === initial.country)?.flag ?? ""} ${countryName(initial.country)} (not open for new businesses)`.trim() }]
      : []),
  ];
  if (!countries) countryOptions.push({ value: initial.country, label: countryName(initial.country) });
  const selected = countries?.find((c) => c.code === v.country);
  const regionLabel = selected?.regionLabel ?? "State / region";
  const postalLabel = selected?.postalLabel ?? "Postal code";
  /** Red hint while a field the admin flagged still holds the rejected value. */
  const flag = (key: keyof CompanyValues): string | undefined =>
    flagged.has(key) && v[key].trim() === initial[key].trim() ? "Flagged by Corridor ops — please correct this." : undefined;

  return (
    <form onSubmit={submit} noValidate className="relief space-y-4 rounded-[26px] p-5 sm:p-6">
      <Input
        id="legal-name"
        label="Company name"
        required
        maxLength={200}
        autoComplete="organization"
        error={errors.legalName ?? flag("legalName")}
        value={v.legalName}
        onChange={(e) => set("legalName")(e.target.value)}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <Select
          id="country"
          label="Country"
          required
          value={v.country}
          onChange={(e) => set("country")(e.target.value)}
          options={countryOptions}
          error={flag("country")}
          hint={countryChanged ? "The document list below changes with the country." : "Countries Corridor One X onboards today."}
        />
        <Input
          id="city"
          label="City"
          required
          maxLength={100}
          autoComplete="address-level2"
          error={errors.city ?? flag("city")}
          value={v.city}
          onChange={(e) => set("city")(e.target.value)}
        />
      </div>
      <Input
        id="address-line"
        label="Registered address"
        required
        maxLength={200}
        autoComplete="street-address"
        placeholder="Building, street, area"
        error={errors.addressLine ?? flag("addressLine")}
        value={v.addressLine}
        onChange={(e) => set("addressLine")(e.target.value)}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <Input
          label={regionLabel}
          optional
          maxLength={100}
          autoComplete="address-level1"
          value={v.state}
          onChange={(e) => set("state")(e.target.value)}
        />
        <Input
          label={postalLabel}
          error={errors.pincode}
          optional
          maxLength={10}
          autoComplete="postal-code"
          value={v.pincode}
          onChange={(e) => set("pincode")(e.target.value)}
        />
      </div>
      {formError ? <Notice tone="frozen">{formError}</Notice> : null}
      <div className="flex justify-end">
        <Button type="submit" loading={saving} disabled={!dirty && !saving}>
          Save company details
        </Button>
      </div>
    </form>
  );
}

function ProfileSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-24 rounded-[26px]" />
      <Skeleton className="h-72 rounded-[26px]" />
      <Skeleton className="h-48 rounded-[26px]" />
    </div>
  );
}
