"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { DEAL_CURRENCIES, PAYMENT_TERMS, fromMinor, money, toMinor, trade, type PaymentTerms, type Quote, type RfqSellerView } from "@/lib/trade";
import { cn } from "@/lib/cn";
import { formatDay } from "@/lib/verification";
import { Button } from "@/components/ui/Button";
import { ChoiceChips, Segmented } from "@/components/ui/Controls";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { Card, Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { RequestSheet } from "@/components/trade/parts";

/**
 * Whether a stated value meets the buyer's limit, the way the server works
 * it out (CX-180): numbers compare as numbers, text must match exactly.
 * Only a hint while typing; the saved quote carries the server's answer.
 */
function meetsLimit(value: string, limit: string, operator: string): boolean | null {
  const v = value.trim();
  if (!v) return null;
  const a = Number(v);
  const b = Number(limit);
  if (Number.isFinite(a) && Number.isFinite(b) && v !== "" && limit.trim() !== "") {
    if (operator === "MAX") return a <= b;
    if (operator === "MIN") return a >= b;
    return a === b;
  }
  return operator === "EQ" && v.toLowerCase().replace(/\s+/g, " ") === limit.trim().toLowerCase().replace(/\s+/g, " ");
}

/**
 * A matched request, opened: the request as the buyer wrote it (no name, no
 * target price) and this seller's quote. The quote can be revised until
 * Corridor One X starts pricing it.
 */
export default function MatchedRequestPage() {
  const { id } = useParams<{ id: string }>();
  const toast = useToast();
  const [rfq, setRfq] = useState<RfqSellerView | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState("INR");
  const [quantity, setQuantity] = useState("");
  const [incoterm, setIncoterm] = useState("");
  const [port, setPort] = useState("");
  const [lead, setLead] = useState("");
  const [terms, setTerms] = useState<PaymentTerms[]>([]);
  const [validUntil, setValidUntil] = useState("");
  const [notes, setNotes] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});

  useEffect(() => {
    let live = true;
    // Opening is free from here: the first opening was paid for on the list.
    trade
      .openMatched(id)
      .then(async (view) => {
        if (!live) return;
        setRfq(view);
        setQuantity(view.quantity ? String(Number(view.quantity)) : "");
        setIncoterm(view.incoterms[0] ?? "");
        setAnswers(Object.fromEntries(view.specs.map((s) => [s.parameterId, ""])));
        const q = await trade.getQuote(id).catch(() => null);
        if (!live || !q) return;
        setQuote(q);
        setPrice(fromMinor(q.priceMinor));
        setCurrency(q.currency);
        setQuantity(String(Number(q.quantity)));
        setIncoterm(q.incoterm);
        setPort(q.portOfLoading ?? "");
        setLead(String(q.leadTimeDays));
        setTerms(q.paymentTerms);
        setValidUntil(q.validUntil);
        setNotes(q.notes ?? "");
        setAnswers(Object.fromEntries(q.specs.map((s) => [s.parameterId, s.value ?? ""])));
      })
      .catch((err) =>
        live &&
        setError(
          err instanceof ApiError && err.status === 402
            ? err.message
            : err instanceof ApiError && err.status === 404
              ? "This request is closed or was not sent to you."
              : "Couldn’t open the request.",
        ),
      );
    return () => {
      live = false;
    };
  }, [id]);

  const save = async () => {
    if (!rfq) return;
    const priceMinor = toMinor(price);
    if (priceMinor === null || priceMinor <= 0) return setFormError(`Enter your price per ${rfq.unit} as a number, like 72000 or 72000.50.`);
    if (!/^\d+(\.\d{1,2})?$/.test(quantity)) return setFormError("Enter the quantity you can supply.");
    if (!/^\d+$/.test(lead)) return setFormError("Enter the lead time in days.");
    if (!terms.length) return setFormError("Choose at least one way you accept payment.");
    if (rfq.quantity && Number(quantity) > Number(rfq.quantity))
      return setFormError(`Quote at most the ${Number(rfq.quantity)} ${rfq.unit} the buyer asked for.`);
    const blank = rfq.specs.filter((s) => !(answers[s.parameterId] ?? "").trim());
    if (blank.length) return setFormError(`Give your value for ${blank.map((s) => s.name).join(", ")}.`);
    setBusy(true);
    setFormError(null);
    try {
      const saved = await trade.saveQuote(id, {
        priceMinor,
        currency,
        quantity,
        unit: rfq.unit,
        incoterm,
        portOfLoading: port || null,
        leadTimeDays: Number(lead),
        paymentTerms: terms,
        validUntil: validUntil || null,
        notes: notes || null,
        specs: rfq.specs.map((s) => ({ parameterId: s.parameterId, value: (answers[s.parameterId] ?? "").trim() || null })),
      });
      setQuote(saved);
      setValidUntil(saved.validUntil);
      toast(quote ? "Quote updated" : "Quote sent to Corridor One X", "verified");
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Couldn’t save the quote.");
    } finally {
      setBusy(false);
    }
  };

  const locked = quote !== null && !quote.editable;

  return (
    <div className="pt-6 sm:pt-10">
      <Link href="/dashboard/requests" className="t-sub inline-flex items-center gap-1.5 text-fg-3 hover:text-fg">
        <Icon name="arrow-left" size={15} />
        Requests
      </Link>
      {error ? (
        <Notice tone="frozen" className="mt-6">{error}</Notice>
      ) : !rfq ? (
        <Skeleton className="mt-6 h-64 w-full rounded-[26px]" />
      ) : (
        <div className="mt-6 grid grid-cols-[minmax(0,1fr)] items-start gap-6 lg:grid-cols-[380px_minmax(0,1fr)]">
          <aside className="relief rounded-[26px] p-5 lg:sticky lg:top-24" aria-label="The request">
            <p className="t-label text-fg-3">The request</p>
            <div className="mt-3">
              <RequestSheet rfq={rfq} />
            </div>
            {rfq.expiresAt ? <p className="t-sub mt-4 text-fg-3">Open for quotes until {formatDay(rfq.expiresAt)}.</p> : null}
          </aside>

          <Card as="section" className="space-y-4 rounded-[26px] p-5 sm:p-6" aria-labelledby="quote-title">
            <div>
              <h1 id="quote-title" className="t-title2 text-fg">
                Your quote
              </h1>
              <p className="t-sub mt-1 text-fg-2">
                Corridor One X is your buyer. It adds freight and its margin and makes the offer to the end buyer, who never sees your price.
              </p>
            </div>
            {locked ? (
              <Notice tone="verified" title="Corridor One X is working on your quote">
                {money(quote.priceMinor, quote.currency)} per {quote.unit}, valid until {formatDay(quote.validUntil)}. It can no longer be changed.
              </Notice>
            ) : null}
            <fieldset disabled={locked} className="space-y-4 disabled:opacity-60">
              <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto]">
                <Input label={`Price per ${rfq.unit}`} inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} inputClassName="t-code" />
                <Segmented label="Currency" value={currency} onChange={setCurrency} options={DEAL_CURRENCIES.map((c) => ({ value: c as string, label: c }))} />
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <Input label={`Quantity (${rfq.unit})`} inputMode="decimal" value={quantity} onChange={(e) => setQuantity(e.target.value)} inputClassName="t-code" />
                <Input label="Lead time (days)" inputMode="numeric" value={lead} onChange={(e) => setLead(e.target.value)} inputClassName="t-code" />
                <Select label="Incoterm" value={incoterm} onChange={(e) => setIncoterm(e.target.value)} options={rfq.incoterms} />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Input label="Port of loading" optional value={port} maxLength={100} placeholder="e.g. Mundra" onChange={(e) => setPort(e.target.value)} />
                <Input label="Quote valid until" optional type="date" value={validUntil} hint="Seven days when left empty." onChange={(e) => setValidUntil(e.target.value)} />
              </div>
              <div>
                <p className="t-label mb-2 text-fg-3">Payment you accept</p>
                <ChoiceChips label="Payment you accept" value={terms} onChange={setTerms} options={PAYMENT_TERMS} />
              </div>
              {rfq.specs.length ? (
                <div>
                  <p className="t-label mb-2 text-fg-3">Your value for each specification</p>
                  <ul className="space-y-3">
                    {rfq.specs.map((s) => {
                      const value = answers[s.parameterId] ?? "";
                      const meets = meetsLimit(value, s.value, s.operator);
                      return (
                        <li key={s.parameterId} className="well grid items-end gap-3 rounded-[18px] p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,160px)_auto]">
                          <p className="t-body text-fg">
                            {s.name}
                            <span className="t-code ml-2 text-fg-3">
                              {s.operator.toLowerCase()} {s.value}
                              {s.unit ? ` ${s.unit}` : ""}
                            </span>
                          </p>
                          <Input
                            label="Your value"
                            value={value}
                            maxLength={200}
                            onChange={(e) => setAnswers((all) => ({ ...all, [s.parameterId]: e.target.value }))}
                            inputClassName="t-code"
                          />
                          <span className={cn("t-sub pb-3", meets === null ? "text-fg-3" : meets ? "text-accent" : "text-danger")}>
                            {meets === null ? "—" : meets ? "Meets" : "Does not meet"}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ) : null}
              <Textarea
                label="Notes"
                optional
                counter
                maxLength={2000}
                rows={3}
                value={notes}
                hint="Don’t include your company name, phone or email."
                onChange={(e) => setNotes(e.target.value)}
              />
            </fieldset>
            {formError ? <Notice tone="frozen">{formError}</Notice> : null}
            {!locked ? (
              <Button variant="primary" loading={busy} onClick={() => void save()}>
                {quote ? "Update quote" : "Send quote"}
              </Button>
            ) : null}
          </Card>
        </div>
      )}
    </div>
  );
}
