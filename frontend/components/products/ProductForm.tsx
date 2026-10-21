"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type DragEvent, type FormEvent, type ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { Segmented } from "@/components/ui/Controls";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import {
  ChoiceEditor,
  ComposerSurface,
  NumberEditor,
  Sentence,
  TextEditor,
  Token,
} from "@/components/market/Composer";
import { lotCompleteness } from "@/components/market/completeness";
import { LotThumb } from "@/components/market/LotPhoto";
import { SellerLine } from "@/components/market/SellerFrost";
import { api, assetUrl } from "@/lib/api";
import { cn } from "@/lib/cn";
import { INDIA_STATES } from "@/lib/indiaStates";
import { useMe } from "@/lib/useMe";
import { useDirtyFlag, useUnsavedGuard } from "@/lib/useUnsavedGuard";
import { LISTING_CURRENCIES, currencySymbol, formatQty, joinDot, packingLabel, priceFigure, type ListingCurrency } from "./format";

export const PRODUCT_CATEGORIES = [
  "Rice", "Sugar", "Wheat", "Pulses", "Spices", "Oilseeds",
  "Cotton", "Millets", "Tea", "Coffee", "Other",
] as const;
export const PRODUCT_UNITS = ["MT", "kg", "quintal"] as const;
export const PRODUCT_PACKAGING = ["Jute", "PP woven", "HDPE", "Bulk", "Other"] as const;

type Category = (typeof PRODUCT_CATEGORIES)[number];
type Unit = (typeof PRODUCT_UNITS)[number];
type Packaging = (typeof PRODUCT_PACKAGING)[number];

const MAX_PHOTOS = 5;
const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_DESCRIPTION = 5000;
const MAX_AMOUNT = 9_999_999_999.99; // Numeric(12, 2)

type FieldKey = "name" | "variety" | "quantity" | "moq" | "pricePerUnit" | "description" | "photos";
type Errors = Partial<Record<FieldKey, string>>;

const FIELD_ORDER: FieldKey[] = ["name", "variety", "quantity", "moq", "pricePerUnit", "photos", "description"];
/** Fields the sentence edits (the rest live in the cards below it). */
const SENTENCE_FIELDS: ReadonlyArray<FieldKey> = ["name", "variety", "quantity", "moq", "pricePerUnit"];

type Mode = "sentence" | "form";

const numeric = (v: string) => {
  // Digits and one dot, at most two decimals.
  const cleaned = v.replace(/[^\d.]/g, "");
  const [whole, ...rest] = cleaned.split(".");
  return rest.length ? `${whole}.${rest.join("").slice(0, 2)}` : whole;
};

function amountError(v: string, label: string): string | undefined {
  if (!v) return undefined;
  const n = Number(v);
  if (!Number.isFinite(n)) return `Enter a number for ${label.toLowerCase()}`;
  if (n <= 0) return `${label} must be more than 0`;
  if (n > MAX_AMOUNT) return `${label} is too large`;
  return undefined;
}

const fmt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
const amount = (v: string) => (v && Number.isFinite(Number(v)) ? fmt.format(Number(v)) : null);

/**
 * New-listing form. The lot is told as one sentence (the style guide's
 * Sentence Composer — tap a word to change it), with a plain form a tap
 * away for anyone who prefers fields. Photos and the description sit in
 * cards below; a glass action bar floats above the dock.
 */
export function ProductForm() {
  const router = useRouter();
  const toast = useToast();
  const { me, refetch } = useMe();
  const live = me?.verification.status === "verified";
  const { confirmIfDirty, isDirty } = useUnsavedGuard();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [mode, setMode] = useState<Mode>("sentence");
  const [openToken, setOpenToken] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [category, setCategory] = useState<Category>("Rice");
  const [variety, setVariety] = useState("");
  const [originState, setOriginState] = useState("");
  const [packaging, setPackaging] = useState<Packaging | "">("");
  const [quantity, setQuantity] = useState("");
  const [unit, setUnit] = useState<Unit>("MT");
  const [moq, setMoq] = useState("");
  const [pricePerUnit, setPricePerUnit] = useState("");
  const [currency, setCurrency] = useState<ListingCurrency>("INR");
  const [description, setDescription] = useState("");

  const [photos, setPhotos] = useState<string[]>([]);
  const [uploading, setUploading] = useState(0);
  const [dragOver, setDragOver] = useState(false);

  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [published, setPublished] = useState(false);

  const dirty =
    !published &&
    !!(
      name.trim() ||
      category !== "Rice" ||
      variety.trim() ||
      originState ||
      packaging ||
      quantity ||
      unit !== "MT" ||
      moq ||
      pricePerUnit ||
      currency !== "INR" ||
      description.trim() ||
      photos.length
    );
  useDirtyFlag(dirty);

  // Navigate only after the guard has seen the dirty flag clear. Its cleanup
  // rewrites the URL (history.replaceState), which Next turns into a router
  // "restore" — fired after our replace, it would cancel the redirect.
  useEffect(() => {
    if (!published || isDirty) return;
    const t = window.setTimeout(() => router.replace("/dashboard/products"), 0);
    return () => window.clearTimeout(t);
  }, [published, isDirty, router]);

  const clearError = (k: FieldKey) =>
    setErrors((e) => {
      if (!e[k]) return e;
      const next = { ...e };
      delete next[k];
      return next;
    });

  // ── Photos ────────────────────────────────────────────────────────
  const addFiles = async (list: FileList | File[] | null) => {
    const files = Array.from(list ?? []);
    if (!files.length) return;
    const room = MAX_PHOTOS - photos.length - uploading;
    if (room <= 0) {
      setErrors((e) => ({ ...e, photos: `Up to ${MAX_PHOTOS} photos per lot` }));
      return;
    }
    const bad = files.find((f) => !PHOTO_TYPES.includes(f.type));
    if (bad) {
      setErrors((e) => ({ ...e, photos: `${bad.name}: use JPG, PNG or WEBP` }));
      return;
    }
    const big = files.find((f) => f.size > MAX_PHOTO_BYTES);
    if (big) {
      setErrors((e) => ({ ...e, photos: `${big.name} is over 5 MB` }));
      return;
    }
    const take = files.slice(0, room);
    clearError("photos");
    if (files.length > room) {
      setErrors((e) => ({ ...e, photos: `Only ${room} more ${room === 1 ? "photo fits" : "photos fit"} — added the first ${room}` }));
    }
    setUploading((n) => n + take.length);
    for (const file of take) {
      try {
        const { url } = await api.uploadProductPhoto(file);
        setPhotos((prev) => (prev.length < MAX_PHOTOS ? [...prev, url] : prev));
      } catch (err) {
        setErrors((e) => ({ ...e, photos: err instanceof Error ? err.message : "Upload failed" }));
      } finally {
        setUploading((n) => n - 1);
      }
    }
  };

  const removePhoto = (idx: number) => {
    setPhotos((prev) => prev.filter((_, i) => i !== idx));
    clearError("photos");
  };

  const movePhoto = (idx: number, dir: -1 | 1) =>
    setPhotos((prev) => {
      const to = idx + dir;
      if (to < 0 || to >= prev.length) return prev;
      const next = [...prev];
      [next[idx], next[to]] = [next[to], next[idx]];
      return next;
    });

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (uploading || photos.length >= MAX_PHOTOS) return;
    void addFiles(e.dataTransfer.files);
  };

  // ── Submit ────────────────────────────────────────────────────────
  const validate = (): Errors => {
    const e: Errors = {};
    const n = name.trim();
    if (!n) e.name = "Name the lot";
    else if (n.length < 2) e.name = "Use at least 2 characters";
    else if (n.length > 200) e.name = "Keep it under 200 characters";
    if (variety.trim().length > 100) e.variety = "Keep it under 100 characters";
    e.quantity = amountError(quantity, "Volume");
    e.moq = amountError(moq, "Minimum order");
    e.pricePerUnit = amountError(pricePerUnit, "Price");
    if (!e.quantity && !e.moq && quantity && moq && Number(moq) > Number(quantity)) {
      e.moq = "Minimum order can’t exceed the volume";
    }
    if (description.trim().length > MAX_DESCRIPTION) e.description = `Keep it under ${MAX_DESCRIPTION} characters`;
    if (photos.length === 0) e.photos = "Add at least one photo";
    for (const k of Object.keys(e) as FieldKey[]) if (!e[k]) delete e[k];
    return e;
  };

  const focusFirst = (e: Errors) => {
    const first = FIELD_ORDER.find((k) => e[k]);
    if (!first) return;
    const el = document.getElementById(`pf-${first}`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
    if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLButtonElement) {
      el.focus({ preventScroll: true });
    }
    // In the sentence, open the word's editor so the fix is one step away.
    if (mode === "sentence" && SENTENCE_FIELDS.includes(first)) setOpenToken(first);
  };

  const handleSubmit = async (ev: FormEvent) => {
    ev.preventDefault();
    if (saving || uploading) return;
    setFormError(null);
    setOpenToken(null);
    const e = validate();
    setErrors(e);
    if (Object.keys(e).length) {
      focusFirst(e);
      return;
    }
    setSaving(true);
    try {
      await api.createProduct({
        name: name.trim(),
        category,
        variety: variety.trim() || null,
        originState: originState || null,
        packaging: packaging || null,
        quantity: quantity ? Number(quantity) : null,
        unit,
        moq: moq ? Number(moq) : null,
        pricePerUnit: pricePerUnit ? Number(pricePerUnit) : null,
        currency,
        description: description.trim() || null,
        photos,
      });
      void refetch();
      toast("Listing published", "verified");
      setPublished(true);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not publish the listing");
      setSaving(false);
    }
  };

  const cancel = () => confirmIfDirty(() => router.push("/dashboard/products"));

  const errorCount = Object.keys(errors).length;
  const busy = saving || published;

  const unitSwitch = (
    <Segmented
      label="Unit"
      size="sm"
      value={unit}
      onChange={setUnit}
      options={PRODUCT_UNITS.map((u) => ({ value: u, label: u }))}
      className="flex w-full [&>button]:flex-1 [&>button]:justify-center"
    />
  );

  const currencySwitch = (
    <Segmented
      label="Currency"
      size="sm"
      value={currency}
      onChange={setCurrency}
      options={LISTING_CURRENCIES.map((c) => ({ value: c, label: c }))}
      className="flex w-full [&>button]:flex-1 [&>button]:justify-center"
    />
  );
  const priceShown = amount(pricePerUnit) ? priceFigure(pricePerUnit, unit, currency) : null;
  const symbol = currencySymbol(currency);

  const sentenceErrors = SENTENCE_FIELDS.filter((k) => errors[k]);
  const errProps = (k: FieldKey) => ({
    id: `pf-${k}`,
    invalid: !!errors[k],
    describedBy: errors[k] ? `pf-err-${k}` : undefined,
  });

  const completeness = lotCompleteness({
    name,
    category,
    variety,
    originState,
    packaging,
    quantity,
    moq,
    pricePerUnit,
    description,
    photos,
  });
  const cover = photos[0] ? assetUrl(photos[0]) : null;
  const previewQty = formatQty(quantity || null, unit);
  const sellerPlace = joinDot(me?.business.city, me?.business.state) || null;

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-6" aria-busy={busy || undefined}>
      {/* ── The lot ── */}
      <section aria-labelledby="pf-lot-title" className="relief rounded-[32px] p-5 sm:p-8 lg:p-10">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <h2 id="pf-lot-title" className="t-label flex items-baseline gap-2 text-fg-3">
            <span className="t-code">01</span> The lot
          </h2>
          <Segmented
            label="Describe the lot as"
            size="sm"
            value={mode}
            onChange={(m) => {
              setOpenToken(null);
              setMode(m);
            }}
            options={[
              { value: "sentence", label: "Sentence", icon: "pen" },
              { value: "form", label: "Form", icon: "list" },
            ]}
          />
        </div>

        {mode === "sentence" ? (
          <ComposerSurface openKey={openToken} onOpenChange={setOpenToken}>
            <Sentence>
              I&rsquo;m selling{" "}
              <Token
                tokenKey="quantity"
                {...errProps("quantity")}
                label="Volume available"
                value={amount(quantity) ? `${amount(quantity)} ${unit}` : null}
                placeholder="how much"
              >
                {(close) => (
                  <NumberEditor
                    label="Volume available"
                    value={quantity}
                    sanitize={numeric}
                    suffix={unit}
                    error={errors.quantity}
                    onChange={(v) => {
                      setQuantity(v);
                      clearError("quantity");
                    }}
                    extra={unitSwitch}
                    onDone={close}
                  />
                )}
              </Token>{" "}
              of{" "}
              <Token tokenKey="category" id="pf-category" label="Category" value={category} placeholder="Rice">
                {(close) => (
                  <ChoiceEditor
                    label="Category"
                    options={PRODUCT_CATEGORIES}
                    value={category}
                    onChange={(v) => v && setCategory(v)}
                    onDone={close}
                  />
                )}
              </Token>{" "}
              &mdash;{" "}
              <Token tokenKey="name" {...errProps("name")} label="Name" value={name.trim() || null} placeholder="name this lot" editorWidth={320}>
                {(close) => (
                  <TextEditor
                    label="Name"
                    value={name}
                    maxLength={200}
                    placeholder="e.g. 1121 Basmati, steam, 2025 crop"
                    hint="What buyers search for. Required."
                    error={errors.name}
                    onChange={(v) => {
                      setName(v);
                      clearError("name");
                    }}
                    onDone={close}
                  />
                )}
              </Token>
              ,{" "}
              <Token tokenKey="variety" {...errProps("variety")} label="Variety / grade" value={variety.trim() || null} placeholder="any">
                {(close) => (
                  <TextEditor
                    label="Variety / grade"
                    value={variety}
                    maxLength={100}
                    placeholder="e.g. 1121 Steam, Sona Masoori"
                    hint="Optional."
                    error={errors.variety}
                    onChange={(v) => {
                      setVariety(v);
                      clearError("variety");
                    }}
                    onDone={close}
                  />
                )}
              </Token>{" "}
              grade &mdash; from{" "}
              <Token tokenKey="originState" id="pf-origin" label="Origin state" value={originState || null} placeholder="which state">
                {(close) => (
                  <ChoiceEditor
                    label="Origin state"
                    options={INDIA_STATES}
                    value={originState}
                    onChange={setOriginState}
                    noneLabel="Not specified"
                    search
                    onDone={close}
                  />
                )}
              </Token>{" "}
              at{" "}
              <Token
                tokenKey="pricePerUnit"
                {...errProps("pricePerUnit")}
                label="Price"
                value={priceShown}
                placeholder="price on request"
              >
                {(close) => (
                  <NumberEditor
                    label="Price"
                    value={pricePerUnit}
                    sanitize={numeric}
                    prefix={symbol}
                    suffix={`/${unit}`}
                    error={errors.pricePerUnit}
                    onChange={(v) => {
                      setPricePerUnit(v);
                      clearError("pricePerUnit");
                    }}
                    extra={
                      <>
                        <div className="space-y-2">
                          {currencySwitch}
                          {unitSwitch}
                        </div>
                        <p className="t-sub mt-2 px-1 text-fg-3">Leave it blank to show &ldquo;On request&rdquo;.</p>
                      </>
                    }
                    onDone={close}
                  />
                )}
              </Token>
              .{" "}
              <Token tokenKey="packaging" id="pf-packaging" label="Packaging" value={packaging || null} placeholder="Any">
                {(close) => (
                  <ChoiceEditor
                    label="Packaging"
                    options={PRODUCT_PACKAGING}
                    value={packaging}
                    onChange={setPackaging}
                    noneLabel="Not specified"
                    onDone={close}
                  />
                )}
              </Token>{" "}
              packing, minimum order{" "}
              <Token
                tokenKey="moq"
                {...errProps("moq")}
                label="Minimum order"
                value={amount(moq) ? `${amount(moq)} ${unit}` : null}
                placeholder="none"
              >
                {(close) => (
                  <NumberEditor
                    label="Minimum order"
                    value={moq}
                    sanitize={numeric}
                    suffix={unit}
                    error={errors.moq}
                    onChange={(v) => {
                      setMoq(v);
                      clearError("moq");
                    }}
                    extra={unitSwitch}
                    onDone={close}
                  />
                )}
              </Token>
              .
            </Sentence>

            <p className="t-sub mt-5 flex items-start gap-2 text-fg-3">
              <Icon name="info" size={15} className="mt-[1px] shrink-0" />
              Tap any underlined word to change it. Only the name is required — photos and a description go below.
            </p>

            {sentenceErrors.length ? (
              <ul className="mt-4 space-y-1.5" aria-label="Fix these to publish">
                {sentenceErrors.map((k) => (
                  <li key={k} id={`pf-err-${k}`}>
                    <button
                      type="button"
                      onClick={() => setOpenToken(k)}
                      className="t-sub inline-flex items-start gap-1.5 rounded-[8px] text-left text-danger underline-offset-4 hover:underline"
                    >
                      <Icon name="alert" size={14} className="mt-[1px] shrink-0" />
                      {errors[k]}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </ComposerSurface>
        ) : (
          <div className="space-y-7">
            <div className="grid gap-5 sm:grid-cols-2">
              <Input
                id="pf-name"
                label="Name"
                required
                placeholder="e.g. 1121 Basmati, steam, 2025 crop"
                value={name}
                maxLength={200}
                onChange={(e) => {
                  setName(e.target.value);
                  clearError("name");
                }}
                error={errors.name}
                className="sm:col-span-2"
                size="lg"
              />
              <Select
                id="pf-category"
                label="Category"
                required
                value={category}
                onChange={(e) => setCategory(e.target.value as Category)}
                options={PRODUCT_CATEGORIES}
              />
              <Input
                id="pf-variety"
                label="Variety / grade"
                optional
                placeholder="e.g. 1121 Steam, Sona Masoori"
                value={variety}
                maxLength={100}
                onChange={(e) => {
                  setVariety(e.target.value);
                  clearError("variety");
                }}
                error={errors.variety}
              />
              <Select
                id="pf-origin"
                label="Origin state"
                optional
                placeholder="Select a state"
                value={originState}
                onChange={(e) => setOriginState(e.target.value)}
                options={INDIA_STATES}
              />
              <Select
                id="pf-packaging"
                label="Packaging"
                optional
                placeholder="Not specified"
                value={packaging}
                onChange={(e) => setPackaging(e.target.value as Packaging | "")}
                options={PRODUCT_PACKAGING}
              />
            </div>

            <div className="border-t border-line pt-6">
              <div className="mb-5 flex flex-wrap gap-x-8 gap-y-4">
                <div>
                  <p className="t-label text-fg-3">Unit</p>
                  <Segmented
                    label="Unit"
                    className="mt-2"
                    value={unit}
                    onChange={setUnit}
                    options={PRODUCT_UNITS.map((u) => ({ value: u, label: u }))}
                  />
                </div>
                <div>
                  <p className="t-label text-fg-3">Price currency</p>
                  <Segmented
                    label="Price currency"
                    className="mt-2"
                    value={currency}
                    onChange={setCurrency}
                    options={LISTING_CURRENCIES.map((c) => ({ value: c, label: c }))}
                  />
                </div>
              </div>
              <div className="grid gap-5 sm:grid-cols-3">
                <Input
                  id="pf-quantity"
                  label="Volume available"
                  optional
                  inputMode="decimal"
                  placeholder="0"
                  value={quantity}
                  onChange={(e) => {
                    setQuantity(numeric(e.target.value));
                    clearError("quantity");
                  }}
                  trailing={<UnitTag>{unit}</UnitTag>}
                  error={errors.quantity}
                  inputClassName="t-code pr-24 text-[15px]"
                />
                <Input
                  id="pf-moq"
                  label="Minimum order"
                  optional
                  inputMode="decimal"
                  placeholder="0"
                  value={moq}
                  onChange={(e) => {
                    setMoq(numeric(e.target.value));
                    clearError("moq");
                  }}
                  trailing={<UnitTag>{unit}</UnitTag>}
                  error={errors.moq}
                  inputClassName="t-code pr-24 text-[15px]"
                />
                <Input
                  id="pf-pricePerUnit"
                  label="Price"
                  optional
                  inputMode="decimal"
                  placeholder="On request"
                  value={pricePerUnit}
                  onChange={(e) => {
                    setPricePerUnit(numeric(e.target.value));
                    clearError("pricePerUnit");
                  }}
                  leading={<span className="t-code">{symbol}</span>}
                  trailing={<UnitTag>/{unit}</UnitTag>}
                  error={errors.pricePerUnit}
                  hint="Blank shows “On request”."
                  inputClassName={cn("t-code pr-24 text-[15px]", symbol.length > 1 && "pl-[60px]")}
                />
              </div>
            </div>
          </div>
        )}
      </section>

      {/* ── What buyers see · listing strength ── */}
      <div className="grid gap-5 lg:grid-cols-2">
        <section aria-label="What buyers see" className="relief rounded-[26px] p-5">
          <p className="t-label text-fg-3">What buyers see</p>
          <div className="mt-4 flex items-center gap-4">
            <LotThumb src={cover} category={category} size={56} radius={14} />
            <div className="min-w-0">
              <p className="t-headline truncate text-fg">
                {joinDot(previewQty, name.trim() || "Your lot")}
              </p>
              <p className="t-sub truncate text-fg-3">
                {joinDot(variety.trim() || category, originState && `from ${originState}`, packingLabel(packaging))}
              </p>
            </div>
            <p className="t-code tabular ml-auto shrink-0 text-fg">
              {priceShown ?? "On request"}
            </p>
          </div>
          <div className="mt-4 border-t border-line pt-4">
            <SellerLine place={sellerPlace} lead={live ? "Verified seller" : "Your company"} />
          </div>
          <p className="t-foot mt-3 text-fg-3">
            Your name and contact open only to verified buyers who reveal them.
          </p>
        </section>

        <section aria-label="Listing strength" className="well rounded-[26px] p-5">
          <div className="flex items-center justify-between gap-3">
            <p className="t-label text-fg-3">Listing strength</p>
            <span className="t-code text-fg-3">
              {photos.length}/{MAX_PHOTOS} photos
            </span>
          </div>
          <p className="tabular mt-4 text-[26px] font-medium leading-none tracking-[-0.03em] text-fg">
            {completeness.score}%
          </p>
          <div
            role="progressbar"
            aria-label="Listing completeness"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={completeness.score}
            className="well mt-3 h-1.5 overflow-hidden rounded-full"
          >
            <div
              className="h-full rounded-full bg-fg transition-[width] duration-700 ease-expo"
              style={{ width: `${completeness.score}%` }}
            />
          </div>
          <p className="t-sub mt-3 text-fg-2" aria-live="polite">
            {completeness.hint}
          </p>
        </section>
      </div>

      {/* ── Photos ── */}
      <Section
        title="Photos"
        index="02"
        meta={
          <span className="t-code tabular text-fg-3">
            {photos.length}/{MAX_PHOTOS}
          </span>
        }
      >
        <div
          onDragOver={(e) => {
            e.preventDefault();
            if (!dragOver) setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          className="space-y-4"
        >
          {photos.length < MAX_PHOTOS ? (
            <button
              id="pf-photos"
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading > 0 && photos.length + uploading >= MAX_PHOTOS}
              aria-describedby={errors.photos ? "pf-photos-help pf-photos-error" : "pf-photos-help"}
              className={cn(
                "well group/drop relative flex w-full flex-col items-center justify-center rounded-[22px] px-6 py-10 text-center transition-shadow duration-300 ease-expo",
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
              <span className={cn("relative grid size-12 place-items-center rounded-full", dragOver ? "solid" : "relief-sm text-fg-2")}>
                {uploading ? (
                  <svg width="20" height="20" viewBox="0 0 24 24" className="animate-spin" aria-hidden="true">
                    <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity=".25" strokeWidth="2" />
                    <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                ) : (
                  <Icon name="upload" size={20} />
                )}
              </span>
              <span className="t-headline relative mt-4 text-fg">
                {uploading
                  ? `Uploading ${uploading} ${uploading === 1 ? "photo" : "photos"}…`
                  : dragOver
                    ? "Drop to upload"
                    : photos.length
                      ? "Add more photos"
                      : "Drop photos or browse"}
              </span>
              <span id="pf-photos-help" className="t-sub relative mt-1 text-fg-3">
                JPG, PNG or WEBP · up to 5 MB each · 1–{MAX_PHOTOS} photos · the first is the cover
              </span>
            </button>
          ) : (
            <p className="t-sub text-fg-3">That&rsquo;s the maximum. Remove one to add another.</p>
          )}

          {errors.photos ? (
            <p id="pf-photos-error" role="alert" className="t-sub flex items-start gap-1.5 text-danger">
              <Icon name="alert" size={14} className="mt-[1px] shrink-0" />
              {errors.photos}
            </p>
          ) : null}

          {photos.length ? (
            <ol className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5" aria-label="Photo order">
              {photos.map((rel, i) => (
                <li key={rel} className="relief-sm group relative overflow-hidden rounded-[20px] p-1.5">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={assetUrl(rel)}
                    alt={`Photo ${i + 1}`}
                    className="aspect-square w-full rounded-[15px] object-cover"
                  />
                  {i === 0 ? (
                    <span className="solid t-label absolute left-3 top-3 rounded-full px-2 py-1 text-[10px]">
                      Cover
                    </span>
                  ) : null}
                  <div className="mt-1.5 flex items-center justify-between gap-1">
                    <div className="flex items-center">
                      <TileButton
                        icon="arrow-left"
                        label={`Move photo ${i + 1} earlier`}
                        disabled={i === 0}
                        onClick={() => movePhoto(i, -1)}
                      />
                      <TileButton
                        icon="arrow-right"
                        label={`Move photo ${i + 1} later`}
                        disabled={i === photos.length - 1}
                        onClick={() => movePhoto(i, 1)}
                      />
                    </div>
                    <TileButton icon="trash" label={`Remove photo ${i + 1}`} danger onClick={() => removePhoto(i)} />
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
            e.target.value = ""; // allow re-picking the same file
            void addFiles(files);
          }}
        />
      </Section>

      {/* ── Description ── */}
      <Section title="Description" index="03">
        <Textarea
          id="pf-description"
          label="About this lot"
          optional
          counter
          maxLength={MAX_DESCRIPTION}
          rows={5}
          placeholder="Quality, moisture, sourcing, certifications, when it ships…"
          value={description}
          onChange={(e) => {
            setDescription(e.target.value);
            clearError("description");
          }}
          error={errors.description}
          hint="Search reads the description, so the words buyers use help them find this lot."
        />
      </Section>

      {/* ── Action bar — floats above the dock ── */}
      <div className="sticky bottom-[calc(max(14px,env(safe-area-inset-bottom))_+_80px)] z-30 pt-2">
        <div className="glass flex flex-col gap-3 rounded-[24px] p-2 sm:flex-row sm:items-center sm:rounded-full sm:pl-5">
          <p className="t-sub min-w-0 flex-1 px-3 pt-1 sm:px-0 sm:pt-0" aria-live="polite">
            {formError ? (
              <span className="flex items-start gap-1.5 text-danger">
                <Icon name="alert" size={14} className="mt-[2px] shrink-0" />
                {formError}
              </span>
            ) : errorCount ? (
              <span className="text-danger">
                Fix {errorCount} {errorCount === 1 ? "field" : "fields"} to publish
              </span>
            ) : uploading ? (
              <span className="text-fg-2">Waiting for photos to finish…</span>
            ) : (
              <span className="text-fg-3">
                {live ? "Goes live in the market when you publish." : "Buyers see it once your company is verified."}
              </span>
            )}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="quiet"
              onClick={cancel}
              disabled={busy}
              className="flex-1 hover:bg-[rgb(10_10_10/0.05)] sm:flex-none"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              iconRight="arrow-right"
              loading={busy}
              disabled={uploading > 0}
              className="flex-[2] sm:flex-none"
            >
              Publish listing
            </Button>
          </div>
        </div>
      </div>
    </form>
  );
}

function Section({
  title,
  index,
  meta,
  children,
}: {
  title: string;
  index: string;
  meta?: ReactNode;
  children: ReactNode;
}) {
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
  icon,
  label,
  onClick,
  disabled,
  danger,
}: {
  icon: "arrow-left" | "arrow-right" | "trash";
  label: string;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
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
        danger
          ? "text-fg-3 hover:bg-danger-soft hover:text-danger"
          : "text-fg-3 hover:bg-[rgb(10_10_10/0.05)] hover:text-fg",
      )}
    >
      <Icon name={icon} size={15} />
    </button>
  );
}
