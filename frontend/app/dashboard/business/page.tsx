"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError, type Me } from "@/lib/api";
import { useFocusField } from "@/lib/useFocusField";
import { useMe } from "@/lib/useMe";
import { useDirtyFlag } from "@/lib/useUnsavedGuard";
import { DETAILS_PATH, statusMeta } from "@/lib/verification";
import { COUNTRIES } from "@/components/account/countries";
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

      {me.verification.status === "rejected" && me.verification.rejectedReason ? (
        <Notice tone="frozen">Corridor ops asked for changes: {me.verification.rejectedReason}</Notice>
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
            <KybSection country={me.business.country ?? "IN"} onChanged={() => void refetch()} />
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
    setErrors(fe);
    if (Object.keys(fe).length) return;
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

  return (
    <form onSubmit={submit} noValidate className="relief space-y-4 rounded-[26px] p-5 sm:p-6">
      <Input
        id="legal-name"
        label="Company name"
        required
        maxLength={200}
        autoComplete="organization"
        error={errors.legalName}
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
          options={COUNTRIES.map((c) => ({ value: c.code, label: `${c.flag} ${c.name}` }))}
          hint={countryChanged ? "The document list below changes with the country." : undefined}
        />
        <Input
          id="city"
          label="City"
          required
          maxLength={100}
          autoComplete="address-level2"
          error={errors.city}
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
        error={errors.addressLine}
        value={v.addressLine}
        onChange={(e) => set("addressLine")(e.target.value)}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <Input
          label={v.country === "IN" ? "State" : "State / emirate"}
          optional
          maxLength={100}
          autoComplete="address-level1"
          value={v.state}
          onChange={(e) => set("state")(e.target.value)}
        />
        <Input
          label={v.country === "IN" ? "PIN code" : "Postal code"}
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
