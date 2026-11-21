"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type FormEvent, type ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { ChoiceChips, Segmented } from "@/components/ui/Controls";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { api, assetUrl, type ProductCertificate, type ProductRead, type ProductWrite, type SpecOperator } from "@/lib/api";
import { cn } from "@/lib/cn";
import { INDIA_STATES } from "@/lib/indiaStates";
import { publicApi, type CategoryTemplate, type PublicProductCard as CardData } from "@/lib/publicApi";
import { useMe } from "@/lib/useMe";
import { useDirtyFlag, useUnsavedGuard } from "@/lib/useUnsavedGuard";
import { LISTING_CURRENCIES, currencySymbol, type ListingCurrency } from "./format";
import { PublicProductCard } from "./PublicProductCard";

export const PRODUCT_CATEGORIES = [
  "Rice", "Sugar", "Wheat", "Pulses", "Spices", "Oilseeds",
  "Cotton", "Millets", "Tea", "Coffee", "Other",
] as const;
export const PRODUCT_UNITS = ["MT", "kg", "quintal"] as const;
export const PRODUCT_PACKAGING = ["Jute", "PP woven", "HDPE", "Bulk", "Other"] as const;
export const INCOTERMS = ["EXW", "FOB", "CIF", "CFR", "DAP", "DDP"] as const;
/** Shown until the onboarded list arrives (the API checks the same list). */
const ORIGIN_FALLBACK = [{ value: "IN", label: "India" }];

/** Countries of origin a listing may name: the ones Corridor onboards. */
function useOriginCountries(current: string): { value: string; label: string }[] {
  const [opts, setOpts] = useState<{ value: string; label: string }[]>(ORIGIN_FALLBACK);
  useEffect(() => {
    let live = true;
    api
      .kybCountries()
      .then((cs) => live && cs.length && setOpts(cs.map((c) => ({ value: c.code, label: c.name }))))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);
  // A saved value that is no longer offered stays visible so the seller sees what to change.
  return !current || opts.some((o) => o.value === current) ? opts : [...opts, { value: current, label: `${current} (not offered)` }];
}
const OPERATORS: ReadonlyArray<{ value: SpecOperator; label: string }> = [
  { value: "MAX", label: "Max" },
  { value: "MIN", label: "Min" },
  { value: "EQ", label: "Exactly" },
];

const MAX_PHOTOS = 5;
const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_DOC_BYTES = 10 * 1024 * 1024;
const DOC_TYPES = ["application/pdf", ...PHOTO_TYPES];
const MAX_DESCRIPTION = 5000;

interface SpecDraft {
  value: string;
  operator: SpecOperator;
  testMethod: string;
}

interface FormState {
  name: string;
  category: string;
  variety: string;
  grade: string;
  hsCode: string;
  originCountry: string;
  originState: string;
  packaging: string;
  description: string;
  quantity: string;
  unit: string;
  moq: string;
  capacityPerMonth: string;
  capacityUnit: string;
  leadTimeDays: string;
  priceMin: string;
  priceMax: string;
  currency: string;
  priceValidUntil: string;
  incoterms: string[];
  portOfLoading: string;
  photos: string[];
  specs: Record<string, SpecDraft>;
}

const EMPTY: FormState = {
  name: "", category: "Rice", variety: "", grade: "", hsCode: "", originCountry: "IN", originState: "",
  packaging: "", description: "", quantity: "", unit: "MT", moq: "", capacityPerMonth: "", capacityUnit: "MT",
  leadTimeDays: "", priceMin: "", priceMax: "", currency: "INR", priceValidUntil: "", incoterms: [],
  portOfLoading: "", photos: [], specs: {},
};

type FieldKey = keyof FormState;
type Errors = Partial<Record<FieldKey, string>>;

const str = (v: unknown) => (v === null || v === undefined ? "" : String(v));
/** "500.00" → "500"; keeps "72.5". */
const num = (v: unknown) => {
  const s = str(v);
  return s && Number.isFinite(Number(s)) ? String(Number(s)) : s;
};

/** Form values for a listing. Edits waiting for review are laid over the
 * published values, so the seller carries on from what they proposed. */
function toForm(p: ProductRead): FormState {
  const pending = p.pendingRevision ?? {};
  const pick = <K extends keyof ProductRead>(k: K) => (k in pending ? pending[k as string] : p[k]);
  const specs: Record<string, SpecDraft> = {};
  for (const s of pending.specs ?? p.specs) {
    specs[s.parameterId] = { value: s.value, operator: s.operator, testMethod: s.testMethod ?? "" };
  }
  return {
    name: str(pick("name")),
    category: str(pick("category")),
    variety: str(pick("variety")),
    grade: str(pick("grade")),
    hsCode: str(pick("hsCode")),
    originCountry: str(pick("originCountry")) || "IN",
    originState: str(pick("originState")),
    packaging: str(pick("packaging")),
    description: str(pick("description")),
    quantity: num(p.quantity),
    unit: str(pick("unit")) || "MT",
    moq: num(p.moq),
    capacityPerMonth: num(pick("capacityPerMonth")),
    capacityUnit: str(pick("capacityUnit")) || str(pick("unit")) || "MT",
    leadTimeDays: str(pick("leadTimeDays")),
    priceMin: num(p.priceMin),
    priceMax: num(p.priceMax),
    currency: p.currency,
    priceValidUntil: str(p.priceValidUntil),
    incoterms: (pick("incoterms") as string[] | null) ?? [],
    portOfLoading: str(pick("portOfLoading")),
    photos: (pick("photos") as string[] | null) ?? [],
    specs,
  };
}

const numberOrNull = (v: string) => (v.trim() === "" ? null : Number(v));
const textOrNull = (v: string) => v.trim() || null;

function toPayload(f: FormState): ProductWrite {
  return {
    name: f.name.trim(),
    category: f.category,
    variety: textOrNull(f.variety),
    grade: textOrNull(f.grade),
    hsCode: textOrNull(f.hsCode),
    originCountry: f.originCountry || null,
    originState: textOrNull(f.originState),
    packaging: f.packaging || null,
    description: textOrNull(f.description),
    quantity: numberOrNull(f.quantity),
    unit: f.unit,
    moq: numberOrNull(f.moq),
    capacityPerMonth: numberOrNull(f.capacityPerMonth),
    capacityUnit: f.capacityPerMonth.trim() ? f.capacityUnit : null,
    leadTimeDays: numberOrNull(f.leadTimeDays),
    priceMin: numberOrNull(f.priceMin),
    priceMax: numberOrNull(f.priceMax),
    currency: f.currency,
    priceValidUntil: f.priceValidUntil || null,
    incoterms: f.incoterms,
    portOfLoading: textOrNull(f.portOfLoading),
    photos: f.photos,
    specs: Object.entries(f.specs)
      .filter(([, s]) => s.value.trim())
      .map(([parameterId, s]) => ({
        parameterId,
        value: s.value.trim(),
        operator: s.operator,
        testMethod: s.testMethod.trim() || null,
      })),
  };
}

/** Digits and one dot, at most two decimals. */
const decimal = (v: string) => {
  const cleaned = v.replace(/[^\d.]/g, "");
  const [whole, ...rest] = cleaned.split(".");
  return rest.length ? `${whole}.${rest.join("").slice(0, 2)}` : whole;
};
const digits = (v: string) => v.replace(/\D/g, "");

/** What the listing still needs before it can be submitted — the same list
 * the API enforces (decision A-023), worked out as the seller types. */
function missingToSubmit(f: FormState, template: CategoryTemplate | null, certificates: ProductCertificate[]): string[] {
  const today = new Date().toISOString().slice(0, 10);
  const out: string[] = [];
  const need = (ok: boolean, label: string) => {
    if (!ok) out.push(label);
  };
  need(!!f.description.trim(), "a description");
  need(!!f.grade.trim(), "the grade or quality");
  need(!!f.originCountry, "the country of origin");
  need(!!f.originState.trim(), "the state or region of origin");
  need(!!f.moq, "the minimum order quantity");
  need(!!f.capacityPerMonth, "the monthly capacity");
  need(f.leadTimeDays !== "", "the lead time");
  need(!!f.priceMin, "the minimum price");
  need(!!f.priceMax, "the maximum price");
  need(!!f.priceValidUntil, "the price validity date");
  if (f.priceValidUntil && f.priceValidUntil < today) out.push("a price validity date that hasn’t passed");
  need(f.incoterms.length > 0, "at least one incoterm");
  need(f.photos.length > 0, "at least one photo");
  for (const p of template?.specParameters ?? []) {
    if (p.isRequired && !f.specs[p.id]?.value.trim()) out.push(`the specification “${p.name}”`);
  }
  const have = new Set(certificates.map((c) => c.certificateTypeId));
  for (const t of template?.certificateTypes ?? []) {
    if (t.isRequired && !have.has(t.id)) out.push(`the document “${t.name}”`);
  }
  return out;
}

const STATUS_LABEL: Record<ProductRead["status"], string> = {
  draft: "Draft",
  under_review: "In review",
  published: "Published",
  rejected: "Needs changes",
  paused: "Paused",
};

/**
 * One form for a new listing and for editing one. A listing starts as a
 * draft, is submitted for review once the checklist is met, and reaches the
 * market when a reviewer approves it. On a published listing, price and
 * stock change at once; everything else waits for review.
 */
export function ListingForm({ productId }: { productId?: string }) {
  const router = useRouter();
  const toast = useToast();
  const { me } = useMe();
  const verified = me?.verification.status === "verified";
  const { confirmIfDirty, isDirty } = useUnsavedGuard();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [product, setProduct] = useState<ProductRead | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);
  const originCountries = useOriginCountries(form.originCountry);
  const [baseline, setBaseline] = useState(() => JSON.stringify(EMPTY));
  const [template, setTemplate] = useState<CategoryTemplate | null>(null);
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState<null | "save" | "submit" | "other">(null);
  const [uploading, setUploading] = useState(0);
  const [dragOver, setDragOver] = useState(false);
  const [leaveTo, setLeaveTo] = useState<string | null>(null);

  const status = product?.status ?? "draft";
  const locked = status === "under_review";
  const isLive = status === "published" || status === "paused";
  const certificates = useMemo(() => product?.certificates ?? [], [product?.certificates]);

  const adopt = useCallback((p: ProductRead) => {
    const next = toForm(p);
    setProduct(p);
    setForm(next);
    setBaseline(JSON.stringify(next));
  }, []);

  useEffect(() => {
    if (!productId) return;
    let alive = true;
    api
      .getProduct(productId)
      .then((p) => alive && adopt(p))
      .catch((e) => alive && setLoadError(e instanceof Error ? e.message : "Could not load the listing."));
    return () => {
      alive = false;
    };
  }, [productId, adopt]);

  useEffect(() => {
    let alive = true;
    setTemplate(null);
    publicApi
      .categoryTemplate(form.category)
      .then((t) => alive && setTemplate(t))
      .catch(() => alive && setTemplate({ category: form.category, specParameters: [], certificateTypes: [] }));
    return () => {
      alive = false;
    };
  }, [form.category]);

  const dirty = JSON.stringify(form) !== baseline;
  useDirtyFlag(dirty);

  // Navigate only once the unsaved-changes guard has seen the flag clear;
  // its cleanup rewrites history and would otherwise cancel the redirect.
  useEffect(() => {
    if (!leaveTo || isDirty) return;
    const t = window.setTimeout(() => router.replace(leaveTo), 0);
    return () => window.clearTimeout(t);
  }, [leaveTo, isDirty, router]);

  const set = <K extends FieldKey>(key: K, value: FormState[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => {
      if (!e[key]) return e;
      const next = { ...e };
      delete next[key];
      return next;
    });
  };

  const setSpec = (id: string, patch: Partial<SpecDraft>, fallback: SpecOperator) =>
    setForm((f) => ({
      ...f,
      specs: {
        ...f.specs,
        [id]: { ...(f.specs[id] ?? { value: "", operator: fallback, testMethod: "" }), ...patch },
      },
    }));

  // ── Photos ────────────────────────────────────────────────────────
  const addPhotos = async (list: FileList | File[] | null) => {
    const files = Array.from(list ?? []);
    if (!files.length) return;
    const room = MAX_PHOTOS - form.photos.length - uploading;
    const problem =
      room <= 0
        ? `Up to ${MAX_PHOTOS} photos per listing`
        : files.find((f) => !PHOTO_TYPES.includes(f.type))
          ? "Use JPG, PNG or WEBP photos"
          : files.find((f) => f.size > MAX_PHOTO_BYTES)
            ? "Each photo must be under 5 MB"
            : null;
    if (problem) {
      setErrors((e) => ({ ...e, photos: problem }));
      return;
    }
    const take = files.slice(0, room);
    setUploading((n) => n + take.length);
    for (const file of take) {
      try {
        const { url } = await api.uploadProductPhoto(file);
        setForm((f) => (f.photos.length < MAX_PHOTOS ? { ...f, photos: [...f.photos, url] } : f));
      } catch (err) {
        setErrors((e) => ({ ...e, photos: err instanceof Error ? err.message : "Upload failed" }));
      } finally {
        setUploading((n) => n - 1);
      }
    }
  };

  const movePhoto = (idx: number, dir: -1 | 1) => {
    const to = idx + dir;
    if (to < 0 || to >= form.photos.length) return;
    const next = [...form.photos];
    [next[idx], next[to]] = [next[to], next[idx]];
    set("photos", next);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (!locked) void addPhotos(e.dataTransfer.files);
  };

  // ── Save / submit ─────────────────────────────────────────────────
  const validate = (): Errors => {
    const e: Errors = {};
    const name = form.name.trim();
    if (name.length < 2) e.name = name ? "Use at least 2 characters" : "Name the listing";
    if (form.hsCode && !/^\d{6,10}$/.test(form.hsCode)) e.hsCode = "An HS code is 6 to 10 digits";
    if (form.quantity && form.moq && Number(form.moq) > Number(form.quantity)) {
      e.moq = "The minimum order can’t exceed the volume";
    }
    if (form.priceMax && !form.priceMin) e.priceMin = "Enter the minimum price too";
    if (form.priceMin && form.priceMax && Number(form.priceMax) < Number(form.priceMin)) {
      e.priceMax = "The maximum can’t be lower than the minimum";
    }
    return e;
  };

  const save = async (): Promise<ProductRead | null> => {
    setFormError(null);
    const e = validate();
    setErrors(e);
    const first = Object.keys(e)[0];
    if (first) {
      document.getElementById(`lf-${first}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
      return null;
    }
    const payload = toPayload(form);
    const saved = product ? await api.updateProduct(product.id, payload) : await api.createProduct(payload);
    adopt(saved);
    return saved;
  };

  const run = async (kind: "save" | "submit" | "other", fn: () => Promise<void>) => {
    if (busy || uploading) return;
    setBusy(kind);
    try {
      await fn();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(null);
    }
  };

  const onSave = (ev?: FormEvent) => {
    ev?.preventDefault();
    void run("save", async () => {
      const created = !product;
      const saved = await save();
      if (!saved) return;
      if (isLive) {
        toast(saved.pendingRevision ? "Saved. Changes sent for review" : "Saved", "verified");
      } else {
        toast("Draft saved", "verified");
      }
      if (created) setLeaveTo(`/dashboard/products/${saved.id}`);
    });
  };

  const onSubmit = () =>
    void run("submit", async () => {
      const saved = await save();
      if (!saved) return;
      adopt(await api.submitProduct(saved.id));
      toast("Sent for review", "verified");
      setLeaveTo("/dashboard/products");
    });

  const act = (label: string, call: (id: string) => Promise<ProductRead>) =>
    void run("other", async () => {
      if (!product) return;
      adopt(await call(product.id));
      toast(label, "verified");
    });

  // ── Documents ─────────────────────────────────────────────────────
  const [docBusy, setDocBusy] = useState<string | null>(null);
  const [docError, setDocError] = useState<string | null>(null);

  const uploadDoc = async (typeId: string, file: File | undefined) => {
    if (!file || !product) return;
    setDocError(null);
    if (!DOC_TYPES.includes(file.type)) return setDocError("Use a PDF, JPG, PNG or WEBP file.");
    if (file.size > MAX_DOC_BYTES) return setDocError("The file must be under 10 MB.");
    setDocBusy(typeId);
    try {
      const cert = await api.uploadProductCertificate(product.id, typeId, file);
      setProduct((p) =>
        p ? { ...p, certificates: [...p.certificates.filter((c) => c.certificateTypeId !== typeId), cert] } : p,
      );
    } catch (err) {
      setDocError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setDocBusy(null);
    }
  };

  const removeDoc = async (cert: ProductCertificate) => {
    if (!product) return;
    setDocError(null);
    setDocBusy(cert.certificateTypeId);
    try {
      await api.deleteProductCertificate(product.id, cert.id);
      setProduct((p) => (p ? { ...p, certificates: p.certificates.filter((c) => c.id !== cert.id) } : p));
    } catch (err) {
      setDocError(err instanceof Error ? err.message : "Could not remove the document.");
    } finally {
      setDocBusy(null);
    }
  };

  const missing = useMemo(() => missingToSubmit(form, template, certificates), [form, template, certificates]);

  const preview: CardData = useMemo(
    () => ({
      id: product?.id ?? "00000000-0000-0000-0000-000000000000",
      name: form.name.trim() || "Your listing",
      category: form.category,
      variety: textOrNull(form.variety),
      grade: textOrNull(form.grade),
      originCountry: form.originCountry || null,
      originState: textOrNull(form.originState),
      packaging: form.packaging || null,
      quantity: form.quantity || null,
      unit: form.unit,
      moq: form.moq || null,
      capacityPerMonth: form.capacityPerMonth || null,
      capacityUnit: form.capacityUnit,
      incoterms: form.incoterms,
      priceVisible: true,
      priceMin: form.priceMin || null,
      priceMax: form.priceMax || null,
      currency: form.currency,
      priceUsd: null,
      priceUsdMax: null,
      priceUsdAsOf: null,
      priceValidUntil: form.priceValidUntil || null,
      photo: form.photos[0] ?? null,
      seller: { companyCode: me?.companyCode ?? null, state: me?.business.state ?? null, verified: true },
    }),
    [form, product?.id, me?.business.state],
  );

  if (productId && !product) {
    return loadError ? (
      <Notice tone="frozen" title="We couldn’t load this listing">
        {loadError}
      </Notice>
    ) : (
      <div className="space-y-6" aria-busy="true">
        <Skeleton className="h-64 w-full rounded-[32px]" />
        <Skeleton className="h-48 w-full rounded-[32px]" />
      </div>
    );
  }

  const symbol = currencySymbol(form.currency);
  const err = (k: FieldKey) => ({ id: `lf-${k}`, error: errors[k] });
  const canSubmit = verified && missing.length === 0;

  return (
    <form onSubmit={onSave} noValidate className="space-y-6" aria-busy={busy !== null || undefined}>
      {product ? <StatusBanner product={product} onDiscard={() => act("Pending changes discarded", api.discardProductRevision)} busy={busy !== null} /> : null}

      <fieldset disabled={locked} className="min-w-0 space-y-6 border-0 p-0">
        <Section title="The product" index="01">
          <div className="grid gap-5 sm:grid-cols-2">
            <Input
              {...err("name")}
              label="Product name"
              required
              maxLength={200}
              placeholder="e.g. 1121 Basmati, steam, 2025 crop"
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              className="sm:col-span-2"
            />
            <Select
              id="lf-category"
              label="Category"
              required
              value={form.category}
              onChange={(e) => setForm((f) => ({ ...f, category: e.target.value, specs: {} }))}
              options={PRODUCT_CATEGORIES}
              hint="Decides the specifications and documents below."
            />
            <Input
              {...err("grade")}
              label="Grade or quality"
              maxLength={100}
              placeholder="e.g. Grade A, Sortex clean"
              value={form.grade}
              onChange={(e) => set("grade", e.target.value)}
            />
            <Input
              {...err("variety")}
              label="Variety"
              optional
              maxLength={100}
              placeholder="e.g. 1121 Steam, Sona Masoori"
              value={form.variety}
              onChange={(e) => set("variety", e.target.value)}
            />
            <Input
              {...err("hsCode")}
              label="HS code"
              optional
              inputMode="numeric"
              maxLength={10}
              placeholder="e.g. 100630"
              value={form.hsCode}
              onChange={(e) => set("hsCode", digits(e.target.value))}
              inputClassName="t-code"
            />
            <Select
              id="lf-originCountry"
              label="Country of origin"
              value={form.originCountry}
              onChange={(e) => setForm((f) => ({ ...f, originCountry: e.target.value, originState: "" }))}
              options={originCountries}
            />
            {form.originCountry === "IN" ? (
              <Select
                id="lf-originState"
                label="State of origin"
                placeholder="Select a state"
                value={form.originState}
                onChange={(e) => set("originState", e.target.value)}
                options={INDIA_STATES}
                hint="Buyers see the state, never the city."
              />
            ) : (
              <Input
                {...err("originState")}
                label="Region of origin"
                maxLength={100}
                value={form.originState}
                onChange={(e) => set("originState", e.target.value)}
                hint="Buyers see the region, never the city."
              />
            )}
            <Textarea
              {...err("description")}
              label="Description"
              counter
              maxLength={MAX_DESCRIPTION}
              rows={4}
              placeholder="Quality, sourcing, crop year, when it ships…"
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
              hint="Don’t include your company name, phone or email. Reviewers reject listings that do."
              className="sm:col-span-2"
            />
          </div>
        </Section>

        <Section title="Specifications" index="02" meta={<span className="t-code text-fg-3">{form.category}</span>}>
          {!template ? (
            <Skeleton className="h-20 w-full rounded-[18px]" />
          ) : template.specParameters.length === 0 ? (
            <p className="t-sub text-fg-3">
              {form.category} has no specification template yet. Describe the quality in the description.
            </p>
          ) : (
            <ul className="space-y-4">
              {template.specParameters.map((p) => {
                const s = form.specs[p.id];
                return (
                  <li key={p.id} className="grid items-end gap-3 sm:grid-cols-[minmax(0,2fr)_minmax(0,1.4fr)_minmax(0,2fr)]">
                    <Input
                      label={
                        <>
                          {p.name}
                          {p.unit ? <span className="ml-1 normal-case text-fg-3">({p.unit})</span> : null}
                        </>
                      }
                      optional={!p.isRequired}
                      inputMode={p.valueType === "number" ? "decimal" : undefined}
                      placeholder={p.valueType === "number" ? "0" : ""}
                      value={s?.value ?? ""}
                      onChange={(e) =>
                        setSpec(p.id, { value: p.valueType === "number" ? e.target.value.replace(/[^\d.]/g, "") : e.target.value }, p.defaultOperator)
                      }
                      inputClassName="t-code"
                    />
                    <Select
                      label="Stated as"
                      value={s?.operator ?? p.defaultOperator}
                      onChange={(e) => setSpec(p.id, { operator: e.target.value as SpecOperator }, p.defaultOperator)}
                      options={OPERATORS}
                    />
                    <Input
                      label="Test method"
                      optional
                      maxLength={100}
                      placeholder={p.testMethod ?? "e.g. ISO 712"}
                      value={s?.testMethod ?? ""}
                      onChange={(e) => setSpec(p.id, { testMethod: e.target.value }, p.defaultOperator)}
                    />
                  </li>
                );
              })}
            </ul>
          )}
        </Section>

        <Section title="Quantity and availability" index="03">
          <div className="mb-5">
            <p className="t-label text-fg-3">Unit</p>
            <Segmented
              label="Unit"
              className="mt-2"
              value={form.unit}
              onChange={(u) => setForm((f) => ({ ...f, unit: u, capacityUnit: u }))}
              options={PRODUCT_UNITS.map((u) => ({ value: u, label: u }))}
            />
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            <Input
              {...err("quantity")}
              label="Volume available"
              optional
              inputMode="decimal"
              placeholder="0"
              value={form.quantity}
              onChange={(e) => set("quantity", decimal(e.target.value))}
              trailing={<UnitTag>{form.unit}</UnitTag>}
              inputClassName="t-code pr-24"
            />
            <Input
              {...err("moq")}
              label="Minimum order"
              inputMode="decimal"
              placeholder="0"
              value={form.moq}
              onChange={(e) => set("moq", decimal(e.target.value))}
              trailing={<UnitTag>{form.unit}</UnitTag>}
              inputClassName="t-code pr-24"
            />
            <Input
              {...err("capacityPerMonth")}
              label="Monthly capacity"
              inputMode="decimal"
              placeholder="0"
              value={form.capacityPerMonth}
              onChange={(e) => set("capacityPerMonth", decimal(e.target.value))}
              trailing={<UnitTag>{form.capacityUnit}/month</UnitTag>}
              inputClassName="t-code pr-32"
            />
            <Input
              {...err("leadTimeDays")}
              label="Lead time"
              inputMode="numeric"
              placeholder="0"
              value={form.leadTimeDays}
              onChange={(e) => set("leadTimeDays", digits(e.target.value).slice(0, 3))}
              trailing={<UnitTag>days</UnitTag>}
              hint="From a confirmed order to ready to ship."
              inputClassName="t-code pr-20"
            />
          </div>
        </Section>

        <Section title="Price and terms" index="04">
          <div className="mb-5">
            <p className="t-label text-fg-3">Price currency</p>
            <Segmented
              label="Price currency"
              className="mt-2"
              value={form.currency as ListingCurrency}
              onChange={(c) => set("currency", c)}
              options={LISTING_CURRENCIES.map((c) => ({ value: c, label: c }))}
            />
          </div>
          <div className="grid gap-5 sm:grid-cols-3">
            <Input
              {...err("priceMin")}
              label="Minimum price"
              inputMode="decimal"
              placeholder="0"
              value={form.priceMin}
              onChange={(e) => set("priceMin", decimal(e.target.value))}
              leading={<span className="t-code">{symbol}</span>}
              trailing={<UnitTag>/{form.unit}</UnitTag>}
              inputClassName={cn("t-code pr-24", symbol.length > 1 && "pl-[60px]")}
            />
            <Input
              {...err("priceMax")}
              label="Maximum price"
              inputMode="decimal"
              placeholder="0"
              value={form.priceMax}
              onChange={(e) => set("priceMax", decimal(e.target.value))}
              leading={<span className="t-code">{symbol}</span>}
              trailing={<UnitTag>/{form.unit}</UnitTag>}
              inputClassName={cn("t-code pr-24", symbol.length > 1 && "pl-[60px]")}
            />
            <Input
              {...err("priceValidUntil")}
              label="Price valid until"
              type="date"
              min={new Date().toISOString().slice(0, 10)}
              value={form.priceValidUntil}
              onChange={(e) => set("priceValidUntil", e.target.value)}
            />
          </div>
          <p className="t-sub mt-3 text-fg-3">
            Only signed-in, verified businesses see the range. Everyone else sees “On request”.
          </p>
          <div className="mt-6 grid gap-5 border-t border-line pt-6 sm:grid-cols-2">
            <div id="lf-incoterms">
              <p className="t-label text-fg-3">Accepted incoterms</p>
              <ChoiceChips
                label="Accepted incoterms"
                className="mt-2.5"
                value={form.incoterms}
                onChange={(v) => set("incoterms", INCOTERMS.filter((i) => v.includes(i)))}
                options={INCOTERMS.map((i) => ({ value: i as string, label: i }))}
              />
            </div>
            <div className="grid gap-5">
              <Select
                id="lf-packaging"
                label="Packaging"
                optional
                placeholder="Not specified"
                value={form.packaging}
                onChange={(e) => set("packaging", e.target.value)}
                options={PRODUCT_PACKAGING}
              />
              <Input
                {...err("portOfLoading")}
                label="Port of loading"
                optional
                maxLength={100}
                placeholder="e.g. Mundra"
                value={form.portOfLoading}
                onChange={(e) => set("portOfLoading", e.target.value)}
                hint="For the trade desk only. Buyers don’t see it."
              />
            </div>
          </div>
        </Section>

        <Section title="Photos" index="05" meta={<span className="t-code tabular text-fg-3">{form.photos.length}/{MAX_PHOTOS}</span>}>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              if (!dragOver) setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            className="space-y-4"
          >
            {form.photos.length < MAX_PHOTOS ? (
              <button
                id="lf-photos"
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  "well group/drop relative flex w-full flex-col items-center justify-center rounded-[22px] px-6 py-9 text-center transition-shadow duration-300 ease-expo",
                  dragOver && "shadow-[var(--well),0_0_0_1px_var(--c-fg),0_0_0_4px_rgb(196_216_46/0.35)]",
                  errors.photos && !dragOver && "shadow-[var(--well),0_0_0_1px_var(--c-danger)]",
                )}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    "pointer-events-none absolute inset-2 rounded-[16px] border-[1.5px] border-dashed transition-colors duration-300 ease-expo",
                    dragOver ? "border-transparent" : "border-line-2 group-hover/drop:border-fg-3",
                  )}
                />
                <span className="relief-sm relative grid size-12 place-items-center rounded-full text-fg-2">
                  <Icon name="upload" size={20} />
                </span>
                <span className="t-headline relative mt-4 text-fg">
                  {uploading
                    ? `Uploading ${uploading} ${uploading === 1 ? "photo" : "photos"}…`
                    : form.photos.length
                      ? "Add more photos"
                      : "Drop photos or browse"}
                </span>
                <span className="t-sub relative mt-1 text-fg-3">
                  JPG, PNG or WEBP · up to 5 MB each · the first is the cover · no logos or contact details
                </span>
              </button>
            ) : (
              <p className="t-sub text-fg-3">That’s the maximum. Remove one to add another.</p>
            )}
            {errors.photos ? (
              <p role="alert" className="t-sub flex items-start gap-1.5 text-danger">
                <Icon name="alert" size={14} className="mt-[1px] shrink-0" />
                {errors.photos}
              </p>
            ) : null}
            {form.photos.length ? (
              <ol className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5" aria-label="Photo order">
                {form.photos.map((rel, i) => (
                  <li key={rel} className="relief-sm relative overflow-hidden rounded-[20px] p-1.5">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={assetUrl(rel)} alt={`Photo ${i + 1}`} className="aspect-square w-full rounded-[15px] object-cover" />
                    {i === 0 ? (
                      <span className="solid t-label absolute left-3 top-3 rounded-full px-2 py-1 text-[10px]">Cover</span>
                    ) : null}
                    <div className="mt-1.5 flex items-center justify-between gap-1">
                      <div className="flex items-center">
                        <TileButton label={`Move photo ${i + 1} earlier`} disabled={i === 0} onClick={() => movePhoto(i, -1)}>
                          ←
                        </TileButton>
                        <TileButton
                          label={`Move photo ${i + 1} later`}
                          disabled={i === form.photos.length - 1}
                          onClick={() => movePhoto(i, 1)}
                        >
                          →
                        </TileButton>
                      </div>
                      <TileButton label={`Remove photo ${i + 1}`} danger onClick={() => set("photos", form.photos.filter((_, k) => k !== i))}>
                        <Icon name="trash" size={15} />
                      </TileButton>
                    </div>
                  </li>
                ))}
              </ol>
            ) : null}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept={PHOTO_TYPES.join(",")}
            multiple
            className="sr-only"
            tabIndex={-1}
            aria-hidden="true"
            onChange={(e) => {
              const files = e.target.files ? Array.from(e.target.files) : [];
              e.target.value = "";
              void addPhotos(files);
            }}
          />
        </Section>

        <Section title="Documents" index="06">
          {!product ? (
            <p className="t-sub text-fg-3">Save the draft first, then add certificates here.</p>
          ) : !template ? (
            <Skeleton className="h-16 w-full rounded-[18px]" />
          ) : (
            <>
              <ul className="space-y-3">
                {template.certificateTypes.map((t) => {
                  const cert = certificates.find((c) => c.certificateTypeId === t.id);
                  return (
                    <li key={t.id} className="relief-sm flex flex-wrap items-center gap-3 rounded-[18px] px-4 py-3">
                      <div className="min-w-0 flex-1">
                        <p className="t-body flex flex-wrap items-center gap-2 text-fg">
                          {t.name}
                          {t.isRequired ? (
                            <Chip tone="move" size="sm" noIcon>
                              Required
                            </Chip>
                          ) : null}
                          {cert ? (
                            <Chip tone={cert.visibility === "downloadable" ? "verified" : "quiet"} size="sm" noIcon>
                              {cert.visibility === "downloadable" ? "Buyers can download" : "Internal"}
                            </Chip>
                          ) : null}
                        </p>
                        <p className="t-sub mt-0.5 truncate text-fg-3">
                          {cert ? (
                            <a href={assetUrl(cert.url)} target="_blank" rel="noopener noreferrer" className="underline underline-offset-4">
                              {cert.filename}
                            </a>
                          ) : (
                            t.helpText ?? "PDF, JPG, PNG or WEBP, up to 10 MB"
                          )}
                        </p>
                      </div>
                      <label className={cn("t-sub cursor-pointer rounded-full px-3 py-1.5 font-medium text-fg", "relief-sm hover:shadow-[var(--relief)]", docBusy === t.id && "pointer-events-none opacity-60")}>
                        {docBusy === t.id ? "Working…" : cert ? "Replace" : "Upload"}
                        <input
                          type="file"
                          accept={DOC_TYPES.join(",")}
                          className="sr-only"
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            e.target.value = "";
                            void uploadDoc(t.id, file);
                          }}
                        />
                      </label>
                      {cert ? (
                        <TileButton label={`Remove ${t.name}`} danger onClick={() => void removeDoc(cert)}>
                          <Icon name="trash" size={15} />
                        </TileButton>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
              {docError ? (
                <p role="alert" className="t-sub mt-3 text-danger">
                  {docError}
                </p>
              ) : null}
              <p className="t-sub mt-3 text-fg-3">
                Documents stay internal until a reviewer approves them for download by verified buyers.
              </p>
            </>
          )}
        </Section>
      </fieldset>

      <div className="grid gap-5 lg:grid-cols-2">
        <section aria-label="What buyers see" className="min-w-0">
          <p className="t-label mb-3 text-fg-3">What buyers see</p>
          <div className="pointer-events-none max-w-[360px]" aria-hidden="true">
            <PublicProductCard product={preview} />
          </div>
          <p className="t-foot mt-3 text-fg-3">Your company name and contact are never on the card.</p>
        </section>
        <section aria-label="Before you submit" className="well rounded-[26px] p-5">
          <p className="t-label text-fg-3">Before you submit</p>
          {missing.length === 0 ? (
            <p className="t-body mt-4 flex items-center gap-2 text-fg">
              <Icon name="doc-check" size={18} className="text-accent" />
              Everything a reviewer needs is here.
            </p>
          ) : (
            <>
              <p className="t-sub mt-3 text-fg-2">Still needed:</p>
              <ul className="t-sub mt-2 space-y-1.5 text-fg-2" aria-live="polite">
                {missing.map((m) => (
                  <li key={m} className="flex items-start gap-2">
                    <span aria-hidden="true" className="mt-[7px] size-1.5 shrink-0 rounded-full bg-amber" />
                    {m}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>

      {/* Action bar — floats above the dock. */}
      <div className="sticky bottom-[calc(max(14px,env(safe-area-inset-bottom))_+_80px)] z-30 pt-2">
        <div className="glass flex flex-col gap-3 rounded-[24px] p-2 sm:flex-row sm:items-center sm:rounded-full sm:pl-5">
          <p className="t-sub min-w-0 flex-1 px-3 pt-1 sm:px-0 sm:pt-0" aria-live="polite">
            {formError ? (
              <span className="flex items-start gap-1.5 text-danger">
                <Icon name="alert" size={14} className="mt-[2px] shrink-0" />
                {formError}
              </span>
            ) : Object.keys(errors).length ? (
              <span className="text-danger">Fix the highlighted fields to save.</span>
            ) : locked ? (
              <span className="text-fg-3">A reviewer has this listing. Withdraw it to make changes.</span>
            ) : isLive ? (
              <span className="text-fg-3">Price and stock update at once. Other changes go to a reviewer first.</span>
            ) : !verified ? (
              <span className="text-fg-3">Save drafts now. You can submit once your company is verified.</span>
            ) : missing.length ? (
              <span className="text-fg-3">{missing.length} more {missing.length === 1 ? "thing" : "things"} needed before you can submit.</span>
            ) : (
              <span className="text-fg-3">Ready. A reviewer checks it before it reaches the market.</span>
            )}
          </p>
          {/* Three buttons do not fit one row on a phone: submit takes its own. */}
          <div className="flex flex-wrap items-center gap-2 sm:flex-nowrap">
            <Button variant="quiet" onClick={() => confirmIfDirty(() => router.push("/dashboard/products"))} disabled={busy !== null} className="flex-1 sm:flex-none">
              {dirty ? "Cancel" : "Back"}
            </Button>
            {locked ? (
              <Button variant="secondary" loading={busy === "other"} onClick={() => act("Withdrawn. You can edit it now", api.withdrawProduct)} className="flex-[2] sm:flex-none">
                Withdraw to edit
              </Button>
            ) : isLive ? (
              <Button type="submit" variant="primary" loading={busy === "save"} disabled={uploading > 0 || !dirty} className="flex-[2] sm:flex-none">
                Save changes
              </Button>
            ) : (
              <>
                <Button type="submit" variant="secondary" loading={busy === "save"} disabled={uploading > 0} className="flex-1 sm:flex-none">
                  Save draft
                </Button>
                <Button
                  variant="primary"
                  iconRight="arrow-right"
                  loading={busy === "submit"}
                  disabled={uploading > 0 || !canSubmit}
                  title={canSubmit ? undefined : verified ? "Complete the checklist first" : "Verify your company first"}
                  onClick={onSubmit}
                  className="flex-1 basis-full sm:flex-none sm:basis-auto"
                >
                  Submit for review
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </form>
  );
}

function StatusBanner({ product: p, onDiscard, busy }: { product: ProductRead; onDiscard: () => void; busy: boolean }) {
  if (p.status === "rejected") {
    return (
      <Notice tone="frozen" title="The reviewer asked for changes">
        {p.rejectionReason ?? "Fix the listing and submit it again."}
      </Notice>
    );
  }
  if (p.status === "under_review") {
    return (
      <Notice tone="move" title="In review">
        A reviewer is checking this listing. It reaches the market when they approve it.
      </Notice>
    );
  }
  if (p.pendingRevision) {
    return (
      <Notice
        tone="move"
        title="Changes waiting for review"
        action={
          <Button variant="secondary" size="sm" onClick={onDiscard} disabled={busy}>
            Discard changes
          </Button>
        }
      >
        Buyers still see the published version. The form below shows what you proposed.
      </Notice>
    );
  }
  if (p.revisionRejectionReason) {
    return (
      <Notice tone="frozen" title="Your last changes were not accepted">
        {p.revisionRejectionReason} The published version is unchanged.
      </Notice>
    );
  }
  if (p.status === "published" || p.status === "paused") {
    return (
      <Notice tone={p.status === "published" ? "verified" : "info"} title={STATUS_LABEL[p.status]}>
        {p.status === "published" ? "This listing is in the market." : "Hidden from the market until you resume it."}
      </Notice>
    );
  }
  return null;
}

function Section({ title, index, meta, children }: { title: string; index: string; meta?: ReactNode; children: ReactNode }) {
  return (
    <section className="relief rounded-[30px] p-5 sm:p-7" aria-label={title}>
      <div className="mb-5 flex items-center justify-between gap-4">
        <h2 className="t-label flex items-baseline gap-2 text-fg-3">
          <span className="t-code">{index}</span>
          {title}
        </h2>
        {meta}
      </div>
      {children}
    </section>
  );
}

function UnitTag({ children }: { children: ReactNode }) {
  return <span className="t-code pointer-events-none pr-2 text-fg-3">{children}</span>;
}

function TileButton({
  label,
  onClick,
  disabled,
  danger,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={cn(
        "grid size-8 place-items-center rounded-full transition-colors duration-200 disabled:pointer-events-none disabled:opacity-30",
        danger ? "text-fg-3 hover:bg-danger-soft hover:text-danger" : "text-fg-3 hover:bg-[rgb(10_10_10/0.05)] hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}
