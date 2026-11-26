"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ApiError, type Wallet } from "@/lib/api";
import { publicApi, type CategoryTemplate } from "@/lib/publicApi";
import { DEAL_CURRENCIES, INCOTERMS, PAYMENT_TERMS, fromMinor, toMinor, trade, type PaymentTerms, type Rfq, type RfqInput, type RfqSellerView } from "@/lib/trade";
import { useMe } from "@/lib/useMe";
import { COUNTRIES } from "@/components/account/countries";
import { Button } from "@/components/ui/Button";
import { ChoiceChips, Segmented } from "@/components/ui/Controls";
import { CreditButton } from "@/components/ui/CreditButton";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Card, Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { RequestSheet } from "@/components/trade/parts";

const OPERATOR_HINT = { MAX: "at most", MIN: "at least", EQ: "exactly" } as const;
const UNITS = ["MT", "kg", "quintal"] as const;

interface FormState {
  productName: string;
  variety: string;
  grade: string;
  specs: Record<string, string>;
  quantity: string;
  unit: string;
  packaging: string;
  certificateTypeIds: string[];
  targetMin: string;
  targetMax: string;
  currency: string;
  incoterms: string[];
  paymentTerms: string;
  deliveryCountry: string;
  destinationPort: string;
  deliveryFrom: string;
  deliveryTo: string;
  notes: string;
}

function fromRfq(r: Rfq): FormState {
  return {
    productName: r.productName,
    variety: r.variety ?? "",
    grade: r.grade ?? "",
    specs: Object.fromEntries(r.specs.map((s) => [s.parameterId, s.value])),
    quantity: r.quantity ? String(Number(r.quantity)) : "",
    unit: r.unit,
    packaging: r.packaging ?? "",
    certificateTypeIds: r.certificates.map((c) => c.certificateTypeId),
    targetMin: fromMinor(r.targetPriceMin),
    targetMax: fromMinor(r.targetPriceMax),
    currency: r.currency ?? "INR",
    incoterms: r.incoterms,
    paymentTerms: r.paymentTerms ?? "",
    deliveryCountry: r.deliveryCountry ?? "",
    destinationPort: r.destinationPort ?? "",
    deliveryFrom: r.deliveryFrom ?? "",
    deliveryTo: r.deliveryTo ?? "",
    notes: r.notes ?? "",
  };
}

/**
 * The draft editor of a request for quotation. Saving is explicit; the
 * checklist and the seller preview come back from the API after each save,
 * so the buyer checks the request as the seller will read it. Submitting
 * prints its price on the button first.
 */
export function RfqForm({ rfq, onChange, onSubmitted }: { rfq: Rfq; onChange: (r: Rfq) => void; onSubmitted: (r: Rfq) => void }) {
  const toast = useToast();
  const { me } = useMe();
  const [form, setForm] = useState<FormState>(() => fromRfq(rfq));
  // The buyer's own calendar day, as the date inputs show it.
  const today = useMemo(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }, []);
  const [template, setTemplate] = useState<CategoryTemplate | null>(null);
  const [preview, setPreview] = useState<RfqSellerView | null>(null);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [busy, setBusy] = useState<"save" | "submit" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(fromRfq(rfq)), [form, rfq]);
  const verified = me?.verification.status === "verified";

  useEffect(() => {
    let live = true;
    void publicApi.categoryTemplate(rfq.category).then((t) => live && setTemplate(t)).catch(() => undefined);
    void trade.sellerPreview(rfq.id).then((p) => live && setPreview(p)).catch(() => undefined);
    void api.getWallet().then((w) => live && setWallet(w)).catch(() => undefined);
    return () => {
      live = false;
    };
  }, [rfq.id, rfq.category]);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((f) => ({ ...f, [key]: value }));

  const body = (): RfqInput | string => {
    const min = form.targetMin ? toMinor(form.targetMin) : null;
    const max = form.targetMax ? toMinor(form.targetMax) : null;
    if ((form.targetMin && min === null) || (form.targetMax && max === null)) return "Enter the target price as a number, like 72000 or 72000.50.";
    if (form.quantity && !/^\d+(\.\d{1,2})?$/.test(form.quantity)) return "Enter the quantity as a number.";
    return {
      productName: form.productName,
      variety: form.variety || null,
      grade: form.grade || null,
      specs: Object.entries(form.specs).filter(([, v]) => v.trim()).map(([parameterId, value]) => ({ parameterId, value: value.trim() })),
      quantity: form.quantity || null,
      unit: form.unit,
      packaging: form.packaging || null,
      certificateTypeIds: form.certificateTypeIds,
      targetPriceMin: min,
      targetPriceMax: max,
      currency: min !== null ? form.currency : null,
      incoterms: form.incoterms,
      paymentTerms: (form.paymentTerms || null) as PaymentTerms | null,
      deliveryCountry: form.deliveryCountry || null,
      destinationPort: form.destinationPort || null,
      deliveryFrom: form.deliveryFrom || null,
      deliveryTo: form.deliveryTo || null,
      notes: form.notes || null,
    };
  };

  const save = async (): Promise<Rfq | null> => {
    const payload = body();
    if (typeof payload === "string") {
      setError(payload);
      return null;
    }
    setError(null);
    try {
      const saved = await trade.updateRfq(rfq.id, payload);
      onChange(saved);
      setForm(fromRfq(saved));
      setPreview(await trade.sellerPreview(saved.id));
      return saved;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn’t save the request.");
      return null;
    }
  };

  const onSave = async () => {
    setBusy("save");
    if (await save()) toast("Draft saved", "verified");
    setBusy(null);
  };

  const onSubmit = async () => {
    setBusy("submit");
    const saved = dirty ? await save() : rfq;
    if (saved && saved.missing.length === 0) {
      try {
        onSubmitted(await trade.submitRfq(saved.id));
        toast("Request sent to Corridor One X", "verified");
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Couldn’t submit the request.");
      }
    }
    setBusy(null);
  };

  return (
    <div className="mt-8 grid grid-cols-[minmax(0,1fr)] items-start gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
      <div className="min-w-0 space-y-6">
        <Card as="section" className="space-y-4 rounded-[26px] p-5 sm:p-6" aria-label="The product">
          <p className="t-label text-fg-3">01 · The product</p>
          <p className="t-sub text-fg-2">
            Fields marked <span className="text-danger">*</span> are needed to send the request. You can save a draft at any time.
          </p>
          <Input label="Product" required value={form.productName} maxLength={200} onChange={(e) => set("productName", e.target.value)} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Variety" optional value={form.variety} maxLength={100} onChange={(e) => set("variety", e.target.value)} />
            <Input label="Grade" optional value={form.grade} maxLength={100} onChange={(e) => set("grade", e.target.value)} />
          </div>
          {!template ? (
            <Skeleton className="h-16 w-full rounded-[18px]" />
          ) : template.specParameters.length ? (
            <div className="space-y-3">
              <p className="t-sub text-fg-2">Your limits. A seller must meet every required one to be matched.</p>
              <div className="grid gap-4 sm:grid-cols-2">
                {template.specParameters.map((p) => (
                  <Input
                    key={p.id}
                    label={
                      <>
                        {p.name}
                        <span className="ml-1 normal-case text-fg-3">
                          ({OPERATOR_HINT[p.defaultOperator]}
                          {p.unit ? `, ${p.unit}` : ""})
                        </span>
                      </>
                    }
                    optional={!p.isRequired}
                    required={p.isRequired}
                    inputMode={p.valueType === "number" ? "decimal" : undefined}
                    value={form.specs[p.id] ?? ""}
                    onChange={(e) => set("specs", { ...form.specs, [p.id]: e.target.value })}
                    inputClassName="t-code"
                  />
                ))}
              </div>
            </div>
          ) : null}
        </Card>

        <Card as="section" className="space-y-4 rounded-[26px] p-5 sm:p-6" aria-label="Quantity and delivery">
          <p className="t-label text-fg-3">02 · Quantity and delivery</p>
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto]">
            <Input label="Quantity" required inputMode="decimal" value={form.quantity} onChange={(e) => set("quantity", e.target.value)} inputClassName="t-code" />
            <Segmented label="Unit" value={form.unit} onChange={(v) => set("unit", v)} options={UNITS.map((u) => ({ value: u, label: u }))} />
          </div>
          <Input label="Packaging" optional value={form.packaging} maxLength={50} placeholder="e.g. 50 kg PP bags" onChange={(e) => set("packaging", e.target.value)} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Select
              label="Delivery country"
              required
              placeholder="Select a country"
              value={form.deliveryCountry}
              onChange={(e) => set("deliveryCountry", e.target.value)}
              options={COUNTRIES.map((c) => ({ value: c.code, label: c.name }))}
            />
            <Input label="Destination port" optional value={form.destinationPort} maxLength={100} placeholder="e.g. Jebel Ali" onChange={(e) => set("destinationPort", e.target.value)} />
            {/* Past days can't be picked; a typed one is flagged before saving. */}
            <Input
              label="Deliver from"
              required
              type="date"
              min={today}
              value={form.deliveryFrom}
              error={form.deliveryFrom && form.deliveryFrom < today ? "Choose today or a later date." : undefined}
              onChange={(e) => set("deliveryFrom", e.target.value)}
            />
            <Input
              label="Deliver by"
              required
              type="date"
              min={form.deliveryFrom && form.deliveryFrom > today ? form.deliveryFrom : today}
              value={form.deliveryTo}
              error={
                form.deliveryTo && form.deliveryTo < today
                  ? "Choose today or a later date."
                  : form.deliveryTo && form.deliveryFrom && form.deliveryTo < form.deliveryFrom
                    ? "This is before the start of the window."
                    : undefined
              }
              onChange={(e) => set("deliveryTo", e.target.value)}
            />
          </div>
          {template?.certificateTypes.length ? (
            <div>
              <p className="t-label mb-2 text-fg-3">Certificates you need</p>
              <ChoiceChips
                label="Certificates you need"
                value={form.certificateTypeIds}
                onChange={(v) => set("certificateTypeIds", v)}
                options={template.certificateTypes.map((t) => ({ value: t.id, label: t.name }))}
              />
            </div>
          ) : null}
        </Card>

        <Card as="section" className="space-y-4 rounded-[26px] p-5 sm:p-6" aria-label="Terms">
          <p className="t-label text-fg-3">03 · Terms</p>
          <div>
            <p className="t-label mb-2 text-fg-3">
              Incoterms you accept<span className="ml-1 text-danger">*</span>
            </p>
            <ChoiceChips label="Incoterms you accept" value={form.incoterms} onChange={(v) => set("incoterms", v)} options={INCOTERMS.map((i) => ({ value: i as string, label: i }))} />
          </div>
          <Select label="How you would like to pay" required placeholder="Select" value={form.paymentTerms} onChange={(e) => set("paymentTerms", e.target.value)} options={PAYMENT_TERMS} />
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
            <Input label={`Target price from (per ${form.unit})`} optional inputMode="decimal" value={form.targetMin} onChange={(e) => set("targetMin", e.target.value)} inputClassName="t-code" />
            <Input label="Up to" optional inputMode="decimal" value={form.targetMax} onChange={(e) => set("targetMax", e.target.value)} inputClassName="t-code" />
            <Segmented label="Currency" value={form.currency} onChange={(v) => set("currency", v)} options={DEAL_CURRENCIES.map((c) => ({ value: c as string, label: c }))} />
          </div>
          <p className="t-sub text-fg-3">Your target price is for Corridor One X only. Sellers never see it.</p>
          <Textarea
            label="Notes"
            optional
            counter
            maxLength={2000}
            rows={3}
            value={form.notes}
            hint="Don’t include your company name, phone or email. Sellers reach you through Corridor One X."
            onChange={(e) => set("notes", e.target.value)}
          />
        </Card>

        {error ? <Notice tone="frozen">{error}</Notice> : null}
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="secondary" loading={busy === "save"} disabled={busy !== null || !dirty} onClick={() => void onSave()}>
            Save draft
          </Button>
          {verified ? (
            <CreditButton wallet={wallet} action="RFQ_POST" size="md" loading={busy === "submit"} disabled={busy !== null || (!dirty && rfq.missing.length > 0)} onClick={() => void onSubmit()}>
              Submit request
            </CreditButton>
          ) : (
            <p className="t-sub text-fg-3">Your draft is saved. You can submit once your company is verified.</p>
          )}
        </div>
      </div>

      <aside className="space-y-5 lg:sticky lg:top-24">
        <section className="well rounded-[26px] p-5" aria-label="Before you submit">
          <p className="t-label text-fg-3">Before you submit</p>
          {rfq.missing.length === 0 ? (
            <p className="t-sub mt-2 text-fg-2">Everything a seller needs is here.</p>
          ) : (
            <ul className="mt-2 space-y-1.5">
              {rfq.missing.map((m) => (
                <li key={m} className="t-sub flex items-start gap-2 text-fg-2">
                  <span aria-hidden="true" className="mt-[7px] size-1.5 shrink-0 rounded-full bg-amber" />
                  {m}
                </li>
              ))}
            </ul>
          )}
          {dirty ? <p className="t-foot mt-3 text-fg-3">Save to refresh this list and the preview.</p> : null}
        </section>
        <section className="relief rounded-[26px] p-5" aria-label="What sellers see">
          <p className="t-label text-fg-3">What sellers see</p>
          <div className="mt-3">{preview ? <RequestSheet rfq={preview} /> : <Skeleton className="h-40 w-full rounded-[18px]" />}</div>
        </section>
      </aside>
    </div>
  );
}
