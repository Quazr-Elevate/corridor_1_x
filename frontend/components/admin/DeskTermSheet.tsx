"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi, errorMessage, type DeskTermSheet, type TermSheetEdit } from "@/lib/adminApi";
import { INCOTERMS, PAYMENT_TERMS, fromMinor, money, paymentLabel, toMinor } from "@/lib/trade";
import { Button } from "@/components/ui/Button";
import { Chip, type ChipTone } from "@/components/ui/Chip";
import { HoldButton } from "@/components/ui/Controls";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { RejectSheet } from "@/components/admin/RejectSheet";
import { fmtAgo } from "@/components/admin/format";

const STATUS: Record<DeskTermSheet["status"], { label: string; tone: ChipTone }> = {
  draft: { label: "Draft", tone: "move" },
  issued: { label: "Waiting for answers", tone: "move" },
  agreed: { label: "Agreed", tone: "verified" },
  declined: { label: "Declined", tone: "frozen" },
  withdrawn: { label: "Withdrawn", tone: "neutral" },
  superseded: { label: "Replaced", tone: "neutral" },
};

type Form = Record<keyof TermSheetEdit, string>;

function formOf(t: DeskTermSheet): Form {
  return {
    product: t.product, quality: t.quality ?? "", packaging: t.packaging ?? "", quantity: String(Number(t.quantity)),
    incoterm: t.incoterm, portOfLoading: t.portOfLoading ?? "", destinationPort: t.destinationPort ?? "",
    deliveryFrom: t.deliveryFrom ?? "", deliveryTo: t.deliveryTo ?? "", buyerPriceMinor: fromMinor(t.buyerPriceMinor),
    buyerPaymentTerms: t.buyerPaymentTerms, sellerPriceMinor: fromMinor(t.sellerPriceMinor),
    sellerPaymentTerms: t.sellerPaymentTerms, notes: t.notes ?? "",
  };
}

/** The form as a PATCH body, or the first thing wrong with it. */
function bodyOf(f: Form): TermSheetEdit | string {
  const buyer = toMinor(f.buyerPriceMinor);
  const seller = toMinor(f.sellerPriceMinor);
  if (!buyer || !seller) return "Enter both prices per unit, e.g. 83160 or 83160.50.";
  if (!/^\d+(\.\d{1,2})?$/.test(f.quantity) || Number(f.quantity) <= 0) return "Enter the quantity.";
  const opt = (v: string) => v.trim() || null;
  return {
    product: f.product.trim(), quality: opt(f.quality), packaging: opt(f.packaging), quantity: f.quantity,
    incoterm: f.incoterm, portOfLoading: opt(f.portOfLoading), destinationPort: opt(f.destinationPort),
    deliveryFrom: opt(f.deliveryFrom), deliveryTo: opt(f.deliveryTo), buyerPriceMinor: buyer,
    buyerPaymentTerms: f.buyerPaymentTerms, sellerPriceMinor: seller, sellerPaymentTerms: f.sellerPaymentTerms,
    notes: opt(f.notes),
  };
}

/**
 * The deal's term sheet as the desk works it (CX-103, A-076): draft a
 * version (a copy of the last, or the offer at the accepted counter's
 * prices), edit it, then issue it. Issuing freezes it; the two sides then
 * accept or decline. Both prices and the margin are shown here only.
 */
export function DeskTermSheetPanel({ dealCode }: { dealCode: string }) {
  const toast = useToast();
  const [items, setItems] = useState<DeskTermSheet[] | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [withdrawing, setWithdrawing] = useState<DeskTermSheet | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const rows = await adminApi.dealTermSheets(dealCode);
      setItems(rows);
      setForm(rows[0]?.status === "draft" ? formOf(rows[0]) : null);
    } catch {
      setItems(null);
    }
  }, [dealCode]);

  useEffect(() => {
    void load();
  }, [load]);

  if (items === null) return null;
  const latest = items[0];
  const set = (k: keyof Form, v: string) => setForm((f) => (f ? { ...f, [k]: v } : f));

  const run = async (fn: () => Promise<unknown>, done: string) => {
    setBusy(true);
    try {
      await fn();
      toast(done);
      await load();
    } catch (e) {
      toast(errorMessage(e, "Couldn’t do that."), "frozen");
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    if (!latest || !form) return false;
    const body = bodyOf(form);
    if (typeof body === "string") {
      toast(body, "frozen");
      return false;
    }
    await adminApi.editTermSheet(latest.id, body);
    return true;
  };

  const open = latest && (latest.status === "draft" || latest.status === "issued");

  return (
    <section aria-labelledby="ts-h" className="relief rounded-[26px] p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="ts-h" className="t-title3 text-fg">
          Term sheet{latest ? ` · version ${latest.version}` : ""}
        </h2>
        {latest ? (
          <Chip tone={STATUS[latest.status].tone} size="sm" noIcon>
            {STATUS[latest.status].label}
          </Chip>
        ) : null}
      </div>

      {!latest || !open ? (
        <div className="mt-3 flex items-center justify-between gap-3">
          <p className="t-sub text-fg-3">
            {latest ? "Draft the next version to change the terms." : "No term sheet yet. The first draft starts from the chosen offer."}
          </p>
          <Button size="sm" variant="secondary" loading={busy} onClick={() => void run(() => adminApi.draftTermSheet(dealCode), "Draft started")}>
            {latest ? `Draft version ${latest.version + 1}` : "Draft the term sheet"}
          </Button>
        </div>
      ) : null}

      {latest && form ? (
        <div className="mt-4 space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Product" value={form.product} maxLength={200} onChange={(e) => set("product", e.target.value)} className="sm:col-span-2" />
            <Textarea label="Quality" optional rows={2} maxLength={2000} value={form.quality} onChange={(e) => set("quality", e.target.value)} className="sm:col-span-2" />
            <Input label={`Quantity (${latest.unit})`} inputMode="decimal" value={form.quantity} onChange={(e) => set("quantity", e.target.value)} inputClassName="t-code" />
            <Input label="Packaging" optional value={form.packaging} maxLength={100} onChange={(e) => set("packaging", e.target.value)} />
            <Select label="Incoterm" value={form.incoterm} options={INCOTERMS} onChange={(e) => set("incoterm", e.target.value)} />
            <Input label="Port of loading" optional value={form.portOfLoading} maxLength={100} onChange={(e) => set("portOfLoading", e.target.value)} />
            <Input label="Destination port" optional value={form.destinationPort} maxLength={100} onChange={(e) => set("destinationPort", e.target.value)} />
            <div className="grid grid-cols-2 gap-3">
              <Input label="Delivery from" optional type="date" value={form.deliveryFrom} onChange={(e) => set("deliveryFrom", e.target.value)} />
              <Input label="Delivery to" optional type="date" value={form.deliveryTo} onChange={(e) => set("deliveryTo", e.target.value)} />
            </div>
            <Input label={`Buyer price per ${latest.unit} (${latest.buyerCurrency})`} inputMode="decimal" value={form.buyerPriceMinor} onChange={(e) => set("buyerPriceMinor", e.target.value)} inputClassName="t-code" />
            <Select label="Buyer pays by" value={form.buyerPaymentTerms} options={PAYMENT_TERMS} onChange={(e) => set("buyerPaymentTerms", e.target.value)} />
            <Input label={`Seller price per ${latest.unit} (${latest.sellerCurrency})`} inputMode="decimal" value={form.sellerPriceMinor} onChange={(e) => set("sellerPriceMinor", e.target.value)} inputClassName="t-code" />
            <Select label="Seller is paid by" value={form.sellerPaymentTerms} options={PAYMENT_TERMS} onChange={(e) => set("sellerPaymentTerms", e.target.value)} />
            <Textarea label="Notes" optional rows={2} maxLength={2000} value={form.notes} onChange={(e) => set("notes", e.target.value)} className="sm:col-span-2" hint="Both sides read these." />
          </div>
          <p className="t-sub text-fg-2">
            Margin at the saved prices: <span className="t-code font-semibold">{Number(latest.marginPct)}%</span> (limits{" "}
            {Number(latest.minMarginPct)}–{latest.maxMarginPct ? Number(latest.maxMarginPct) : "—"}%). Save to recompute.
          </p>
          <div className="flex flex-wrap justify-end gap-2">
            <Button size="sm" variant="danger" disabled={busy} onClick={() => setWithdrawing(latest)}>
              Withdraw…
            </Button>
            <Button size="sm" variant="secondary" loading={busy} onClick={() => void run(async () => { if (!(await save())) throw new Error("Check the form."); }, "Draft saved")}>
              Save draft
            </Button>
            <HoldButton
              size="sm"
              tone="commit"
              icon="check"
              onCommit={() =>
                void run(async () => {
                  if (!(await save())) throw new Error("Check the form.");
                  await adminApi.issueTermSheet(latest.id);
                }, "Issued to both sides")
              }
            >
              Save and issue
            </HoldButton>
          </div>
        </div>
      ) : null}

      {latest && !form ? (
        <div className="well mt-4 rounded-[18px] p-4">
          <p className="t-body text-fg">
            {latest.product} · {Number(latest.quantity)} {latest.unit} · {latest.incoterm}
          </p>
          <p className="t-sub mt-1 text-fg-2">
            Buyer {money(latest.buyerPriceMinor, latest.buyerCurrency)} ({paymentLabel(latest.buyerPaymentTerms)}) · seller{" "}
            {money(latest.sellerPriceMinor, latest.sellerCurrency)} ({paymentLabel(latest.sellerPaymentTerms)}) · margin{" "}
            {Number(latest.marginPct)}%
          </p>
          <p className="t-sub mt-1 text-fg-3">
            Buyer {latest.buyerAcceptedAt ? `accepted ${fmtAgo(latest.buyerAcceptedAt)}` : "has not accepted"} · seller{" "}
            {latest.sellerAcceptedAt ? `accepted ${fmtAgo(latest.sellerAcceptedAt)}` : "has not accepted"}
            {latest.contentSha256 ? <span className="t-code"> · {latest.contentSha256.slice(0, 12)}</span> : null}
          </p>
          {latest.declineNote ? (
            <p className="t-sub mt-1 text-danger">
              The {latest.declinedSide} declined: “{latest.declineNote}”
            </p>
          ) : null}
          {latest.withdrawNote ? <p className="t-sub mt-1 text-fg-3">Withdrawn: {latest.withdrawNote}</p> : null}
          {latest.status === "issued" ? (
            <div className="mt-3 flex justify-end">
              <Button size="sm" variant="danger" disabled={busy} onClick={() => setWithdrawing(latest)}>
                Withdraw…
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}

      <RejectSheet
        open={withdrawing !== null}
        onClose={() => setWithdrawing(null)}
        title={`Withdraw version ${withdrawing?.version ?? ""}`}
        description="It can no longer be accepted. Draft a new version afterwards."
        quickReasons={["Waiting for a new freight quote.", "The terms need to change after the sample result."]}
        submitLabel="Withdraw"
        onSubmit={async (reason) => {
          if (!withdrawing) return;
          await adminApi.withdrawTermSheet(withdrawing.id, reason);
          toast("Withdrawn");
          await load();
        }}
      />
    </section>
  );
}
