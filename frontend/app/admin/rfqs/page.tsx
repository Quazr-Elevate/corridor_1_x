"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi, type CostSheet, type CostSheetInput, type DeskQuote, type DeskRfqDetail, type DeskRfqRow } from "@/lib/adminApi";
import { cn } from "@/lib/cn";
import { DEAL_CURRENCIES, fromMinor, money, paymentLabel, toMinor } from "@/lib/trade";
import { Button } from "@/components/ui/Button";
import { Chip, type ChipTone } from "@/components/ui/Chip";
import { HoldButton, Segmented } from "@/components/ui/Controls";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { EmptyState, Notice, Skeleton } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";
import { RejectSheet } from "@/components/admin/RejectSheet";
import { LaneHeader } from "@/components/admin/tower";
import { fmtAgo } from "@/components/admin/format";
import { RequestSheet } from "@/components/trade/parts";
import { DeskDealChatPanel, HeldMessages, OpenSamples, PendingCounters } from "@/components/admin/DeskChat";
import { DeskTermSheetPanel } from "@/components/admin/DeskTermSheet";
import { DeskDocumentsPanel, TemplateApprovals } from "@/components/admin/DeskDocuments";

const STATUS: Record<string, { label: string; tone: ChipTone }> = {
  submitted: { label: "Waiting", tone: "move" },
  held: { label: "On hold", tone: "frozen" },
  matched: { label: "With sellers", tone: "verified" },
  rejected: { label: "Rejected", tone: "neutral" },
  unmatched: { label: "No match", tone: "neutral" },
  expired: { label: "Expired", tone: "neutral" },
};
const RULE = {
  category: "Category",
  capacity: "Capacity",
  specs: "Specifications",
  lead_time: "Lead time",
  incoterms: "Incoterms",
  certificates: "Documents",
} as Record<string, string>;
const LINES = [
  ["inlandFreightMinor", "Inland freight"],
  ["oceanFreightMinor", "Ocean freight"],
  ["insuranceMinor", "Insurance"],
  ["inspectionMinor", "Inspection"],
  ["documentationMinor", "Documentation"],
  ["financeMinor", "Finance"],
  ["otherMinor", "Other"],
] as const;

const message = (err: unknown, fallback: string) => (err instanceof Error && err.message ? err.message : fallback);

/**
 * The trade desk. A request arrives with the sellers the rules propose and
 * why; the desk adjusts, confirms, rejects or closes it. Once sellers quote,
 * each quote is costed into an offer here. Parties are company codes
 * throughout: this screen never shows a name.
 */
export default function DeskPage() {
  const toast = useToast();
  const [queue, setQueue] = useState<"pending" | "all">("pending");
  const [rows, setRows] = useState<DeskRfqRow[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<DeskRfqDetail | null>(null);
  const [quotes, setQuotes] = useState<DeskQuote[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");
  const [listingId, setListingId] = useState("");

  const load = useCallback(async (q: "pending" | "all") => {
    setError(null);
    try {
      setRows((await adminApi.listRfqs(q)).items);
    } catch (err) {
      setError(message(err, "Couldn’t load the queue."));
    }
  }, []);

  const open = useCallback(async (id: string) => {
    setSelected(id);
    setDetail(null);
    setReason("");
    try {
      const [d, q] = await Promise.all([adminApi.getRfq(id), adminApi.listRfqQuotes(id)]);
      setDetail(d);
      setQuotes(q);
    } catch (err) {
      setError(message(err, "Couldn’t load the request."));
    }
  }, []);

  useEffect(() => {
    void load(queue);
  }, [load, queue]);

  /** Run a desk action, then reload the queue and the open request. */
  const act = async (fn: () => Promise<unknown>, done: string) => {
    if (!selected) return;
    setBusy(true);
    try {
      await fn();
      toast(done, "verified");
      await Promise.all([load(queue), open(selected)]);
    } catch (err) {
      toast(message(err, "That didn’t work."));
    } finally {
      setBusy(false);
    }
  };

  const proposed = detail?.matches.filter((m) => m.status === "proposed") ?? [];
  const reasonOk = reason.trim().length >= 5;

  return (
    <div>
      <LaneHeader
        eyebrow="Trade desk"
        title="Requests"
        subtitle="Confirm which sellers see a request, then price their quotes into offers. Buyers and sellers appear as codes."
        actions={
          <Segmented
            label="Which requests"
            size="sm"
            value={queue}
            onChange={setQueue}
            options={[
              { value: "pending", label: "Waiting" },
              { value: "all", label: "All" },
            ]}
          />
        }
      />
      {error ? <Notice tone="frozen" className="mt-6">{error}</Notice> : null}
      <div className="mt-6 space-y-6">
        <TemplateApprovals />
        <PendingCounters />
        <HeldMessages />
        <OpenSamples />
      </div>

      <div className="mt-8 grid grid-cols-[minmax(0,1fr)] items-start gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <section aria-label="Queue" className="relief rounded-[26px] p-2">
          {rows === null ? (
            <Skeleton className="h-24 w-full rounded-[18px]" />
          ) : rows.length === 0 ? (
            <EmptyState icon="inbox" title="Nothing waiting">
              New requests appear here once a buyer submits one.
            </EmptyState>
          ) : (
            <ul className="space-y-1">
              {rows.map((r) => (
                <li key={r.id}>
                  <button
                    type="button"
                    onClick={() => void open(r.id)}
                    aria-current={selected === r.id || undefined}
                    className={cn("w-full rounded-[18px] px-4 py-3 text-left transition-colors hover:bg-fg/5", selected === r.id && "bg-fg/[0.07]")}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="t-code text-fg-3">{r.dealCode}</span>
                      <Chip tone={STATUS[r.status]?.tone ?? "neutral"} size="sm" noIcon>
                        {STATUS[r.status]?.label ?? r.status}
                      </Chip>
                    </span>
                    <span className="t-headline mt-1 block truncate text-fg">{r.productName}</span>
                    <span className="t-sub block text-fg-3">
                      {r.buyerCode ?? "No code"} · {r.quantity ? `${Number(r.quantity)} ${r.unit}` : ""} · {r.deliveryCountry ?? ""} ·{" "}
                      {r.submittedAt ? fmtAgo(r.submittedAt) : ""}
                    </span>
                    <span className="t-foot block text-fg-3">
                      {r.proposed} proposed · {r.confirmed} confirmed
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-label="Request" className="relief min-w-0 rounded-[32px] p-5 sm:p-7">
          {!selected ? (
            <EmptyState icon="match" title="Pick a request">
              Choose one from the queue to work it.
            </EmptyState>
          ) : !detail ? (
            <Skeleton className="h-64 w-full rounded-[18px]" />
          ) : (
            <div className="space-y-7">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <RequestSheet rfq={detail.rfq} />
                </div>
                <Chip tone={STATUS[detail.status]?.tone ?? "neutral"} noIcon>
                  {STATUS[detail.status]?.label ?? detail.status}
                </Chip>
              </div>
              <p className="t-sub text-fg-2">
                Buyer’s target:{" "}
                {detail.targetPriceMin !== null
                  ? `${money(detail.targetPriceMin, detail.currency)}${detail.targetPriceMax !== null ? ` to ${money(detail.targetPriceMax, detail.currency)}` : ""} per ${detail.rfq.unit}`
                  : "not given"}
                . Sellers never see it.
              </p>
              {detail.status === "held" && detail.deskReason ? (
                <Notice tone="frozen" title="On hold for a compliance check">
                  {detail.deskReason}
                </Notice>
              ) : null}
              {detail.leakFlags.length ? (
                <Notice tone="move" title="Check this text before confirming">
                  {detail.leakFlags.map((f) => `${f.field}: ${f.reasons.join(", ")}`).join(" · ")}
                </Notice>
              ) : null}

              <div>
                <p className="t-label text-fg-3">Sellers</p>
                {detail.matches.length === 0 ? (
                  <p className="t-sub mt-2 text-fg-2">No listing meets every hard rule.</p>
                ) : (
                  <ul className="mt-2 space-y-2">
                    {detail.matches.map((m) => (
                      <li key={m.id} className="well rounded-[18px] p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="t-body text-fg">
                            <span className="t-code">{m.sellerCode ?? "No code"}</span>
                            <span className="ml-2 text-fg-3">{m.listingName}</span>
                          </p>
                          <span className="flex items-center gap-2">
                            {m.score !== null ? (
                              <span className="t-code text-fg-2" title="Fit score out of 100">
                                {m.score}/100
                              </span>
                            ) : null}
                            <Chip tone={m.status === "confirmed" ? "verified" : "quiet"} size="sm" noIcon>
                              {m.status === "confirmed" ? (m.viewedAt ? "Opened" : "Sent") : m.source === "desk" ? "Added by desk" : "Proposed"}
                            </Chip>
                            {detail.status === "submitted" && m.status === "proposed" ? (
                              <Button size="sm" variant="quiet" disabled={busy} onClick={() => void act(() => adminApi.removeRfqMatch(selected, m.id), "Seller removed")}>
                                Remove
                              </Button>
                            ) : null}
                          </span>
                        </div>
                        <ul className="mt-2 space-y-0.5">
                          {m.reasons.map((r) => (
                            <li key={r.rule} className="t-sub text-fg-3">
                              <span className={r.ok ? "text-accent" : "text-danger"}>{r.ok ? "✓" : "✕"}</span> {RULE[r.rule] ?? r.rule}: {r.detail}
                            </li>
                          ))}
                        </ul>
                        {m.scoreParts ? (
                          <p className="t-sub mt-2 text-fg-3">
                            Ranked on: {(["specs", "price", "response"] as const)
                              .map((k) => `${m.scoreParts![k].detail} (${m.scoreParts![k].points}/${m.scoreParts![k].of})`)
                              .join(" · ")}
                          </p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {detail.status === "submitted" ? (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-end gap-3">
                    <Input label="Add a listing by its id" optional value={listingId} onChange={(e) => setListingId(e.target.value)} className="min-w-[260px] flex-1" inputClassName="t-code" />
                    <Button variant="secondary" disabled={busy || listingId.trim().length < 30} onClick={() => void act(() => adminApi.addRfqMatch(selected, listingId.trim()).then(() => setListingId("")), "Seller added")}>
                      Add
                    </Button>
                    <Button variant="quiet" disabled={busy} onClick={() => void act(() => adminApi.rematchRfq(selected), "Rules run again")}>
                      Run the rules again
                    </Button>
                  </div>
                  <Textarea label="Reason (for a rejection)" optional rows={2} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} hint="The buyer reads this. Their credit is returned." />
                  <div className="flex flex-wrap items-center justify-end gap-3">
                    <Button variant="danger" disabled={busy || !reasonOk} onClick={() => void act(() => adminApi.rejectRfq(selected, reason.trim()), "Request rejected and refunded")}>
                      Reject…
                    </Button>
                    <Button variant="secondary" disabled={busy || proposed.length > 0} onClick={() => void act(() => adminApi.closeRfqUnmatched(selected), "Closed as unmatched and refunded")}>
                      Close: no match
                    </Button>
                    <HoldButton tone="commit" loading={busy} disabled={proposed.length === 0} onCommit={() => void act(() => adminApi.confirmRfq(selected), "Sellers notified")}>
                      Confirm {proposed.length} {proposed.length === 1 ? "seller" : "sellers"}
                    </HoldButton>
                  </div>
                </div>
              ) : detail.status === "held" ? (
                <div className="space-y-3">
                  <Textarea label="What was checked" rows={2} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
                  <div className="flex flex-wrap justify-end gap-3">
                    <Button variant="danger" disabled={busy || !reasonOk} onClick={() => void act(() => adminApi.rejectRfq(selected, reason.trim()), "Request rejected and refunded")}>
                      Reject…
                    </Button>
                    <Button variant="primary" disabled={busy || !reasonOk} onClick={() => void act(() => adminApi.releaseRfq(selected, reason.trim()), "Released to the queue")}>
                      Release to the queue
                    </Button>
                  </div>
                </div>
              ) : null}

              {detail.rfq.dealCode ? <DeskDealChatPanel key={detail.rfq.dealCode} dealCode={detail.rfq.dealCode} /> : null}
              {detail.rfq.dealCode ? <DeskTermSheetPanel key={`ts-${detail.rfq.dealCode}`} dealCode={detail.rfq.dealCode} /> : null}
              {detail.rfq.dealCode ? <DeskDocumentsPanel key={`docs-${detail.rfq.dealCode}`} dealCode={detail.rfq.dealCode} /> : null}

              {quotes.length ? (
                <div>
                  <p className="t-label text-fg-3">Quotes</p>
                  <ul className="mt-2 space-y-4">
                    {quotes.map((q) => (
                      <QuoteCard key={q.id} quote={q} busy={busy} act={act} />
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

/** "oceanFreightMinor" → "ocean_freight", the key the API keeps line entries under. */
const lineName = (key: string) => key.replace(/Minor$/, "").replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
const currencyKey = (key: string) => key.replace(/Minor$/, "Currency");

function sheetForm(sheet: CostSheet | null, purchaseCurrency: string): Record<string, string> {
  const values: Record<string, string> = { marginPct: sheet ? String(Number(sheet.marginPct)) : "", freightQuotedOn: sheet?.freightQuotedOn ?? "" };
  for (const [key] of LINES) {
    // A line entered in another currency shows what was entered, not the conversion.
    const entry = sheet?.lineEntries.find((e) => e.line === lineName(key));
    values[key] = entry ? fromMinor(entry.amountMinor) : sheet ? fromMinor(sheet[key]) : "";
    values[currencyKey(key)] = entry?.currency ?? purchaseCurrency;
  }
  return values;
}

/** One seller's quote with its cost sheet: cost it, get it approved, publish the offer. */
const WITHDRAW_REASONS = [
  "A cost on the sheet was wrong. A corrected offer follows.",
  "The seller can no longer supply at this price.",
] as const;

function QuoteCard({ quote, busy, act }: { quote: DeskQuote; busy: boolean; act: (fn: () => Promise<unknown>, done: string) => Promise<void> }) {
  const [withdrawing, setWithdrawing] = useState(false);
  const [form, setForm] = useState(() => sheetForm(quote.costSheet, quote.currency));
  const [problem, setProblem] = useState<string | null>(null);
  const sheet = quote.costSheet;
  const published = sheet?.status === "published";

  const save = () => {
    const body: Record<string, unknown> = { freightQuotedOn: form.freightQuotedOn || null, marginPct: form.marginPct };
    for (const [key, label] of LINES) {
      const minor = form[key] ? toMinor(form[key]) : 0;
      if (minor === null) return setProblem(`${label}: enter a number.`);
      body[key] = minor;
      const currency = form[currencyKey(key)];
      body[currencyKey(key)] = currency && currency !== quote.currency ? currency : null;
    }
    if (!/^\d+(\.\d{1,2})?$/.test(form.marginPct)) return setProblem("Enter the margin as a percentage.");
    setProblem(null);
    void act(() => adminApi.saveCostSheet(quote.id, body as unknown as CostSheetInput), "Cost sheet saved");
  };

  return (
    <li className="well rounded-[20px] p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="t-body text-fg">
          <span className="t-code">{quote.sellerCode ?? "No code"}</span>
          <span className="ml-2 text-fg-3">
            {quote.incoterm} · {quote.leadTimeDays} days · {quote.portOfLoading ?? "port not stated"}
          </span>
        </p>
        <p className="t-headline text-fg">
          {money(quote.priceMinor, quote.currency)} <span className="t-sub text-fg-3">per {quote.unit}</span>
        </p>
      </div>
      <p className="t-sub mt-1 text-fg-3">
        {Number(quote.quantity)} {quote.unit} · valid until {quote.validUntil} · {quote.paymentTerms.map(paymentLabel).join(", ")} ·{" "}
        {quote.specs.filter((s) => s.meets).length} of {quote.specs.length} specifications met
        {quote.partQuote ? (
          <Chip tone="move" size="sm" noIcon className="ml-2">
            Part quote
          </Chip>
        ) : null}
      </p>
      {quote.notes ? <p className="t-sub mt-1 text-fg-2">{quote.notes}</p> : null}

      <fieldset disabled={published || busy} className="mt-4 space-y-3 disabled:opacity-70">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {LINES.map(([key, label]) => (
            <div key={key} className="grid grid-cols-[minmax(0,1fr)_6rem] items-end gap-2">
              <Input label={label} optional inputMode="decimal" value={form[key]} onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))} inputClassName="t-code" />
              <Select
                label="Currency"
                value={form[currencyKey(key)]}
                options={DEAL_CURRENCIES as unknown as string[]}
                onChange={(e) => setForm((f) => ({ ...f, [currencyKey(key)]: e.target.value }))}
              />
            </div>
          ))}
          <Input label="Freight quoted on" optional type="date" value={form.freightQuotedOn} onChange={(e) => setForm((f) => ({ ...f, freightQuotedOn: e.target.value }))} />
          <Input label="Margin %" inputMode="decimal" value={form.marginPct} onChange={(e) => setForm((f) => ({ ...f, marginPct: e.target.value }))} inputClassName="t-code" />
        </div>
      </fieldset>
      {problem ? <p role="alert" className="t-sub mt-2 text-danger">{problem}</p> : null}

      {sheet ? (
        <p className="t-sub mt-3 text-fg-2">
          Cost {money(sheet.totalCostMinor, sheet.purchaseCurrency)}
          {sheet.dealCurrency !== sheet.purchaseCurrency ? ` · rate ${Number(sheet.fxRate)} of ${sheet.fxAsOf ?? "today"} + ${Number(sheet.fxBufferPct)}% buffer` : ""} · margin{" "}
          {Number(sheet.marginPct)}% (floor {Number(sheet.minMarginPct)}%
          {sheet.maxMarginPct ? `, ceiling ${Number(sheet.maxMarginPct)}%` : ""}) ·{" "}
          <span className="font-medium text-fg">sells at {money(sheet.sellPriceMinor, sheet.dealCurrency)}</span>
        </p>
      ) : null}
      {sheet?.lineEntries.length ? (
        <p className="t-sub mt-1 text-fg-3">
          Converted:{" "}
          {sheet.lineEntries
            .map((e) => `${e.line.replace("_", " ")} ${money(e.amountMinor, e.currency)} at ${Number(e.rate)}${e.asOf ? ` (${e.asOf})` : ""}`)
            .join(" · ")}
        </p>
      ) : null}
      {sheet?.needsApproval && sheet.approvalReasons.length ? (
        <Notice tone="move" title="Needs a desk manager" className="mt-3">
          <ul className="space-y-1">
            {sheet.approvalReasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </Notice>
      ) : null}
      <div className="mt-3 flex flex-wrap items-center justify-end gap-3">
        {sheet?.needsApproval ? (
          <Button variant="secondary" disabled={busy} onClick={() => void act(() => adminApi.approveCostSheet(sheet.id), "Sheet approved")}>
            Approve sheet
          </Button>
        ) : null}
        {published ? (
          <>
            <Chip tone="verified" size="sm" noIcon>
              Offer with the buyer
            </Chip>
            {quote.offerId ? (
              <Button variant="danger" disabled={busy} onClick={() => setWithdrawing(true)}>
                Withdraw offer…
              </Button>
            ) : null}
          </>
        ) : (
          <>
            <Button variant="secondary" disabled={busy} onClick={save}>
              {sheet ? "Save sheet" : "Cost this quote"}
            </Button>
            {sheet?.status === "ready" ? (
              <HoldButton tone="commit" size="md" loading={busy} onCommit={() => void act(() => adminApi.publishOffer(sheet.id), "Offer sent to the buyer")}>
                Publish offer
              </HoldButton>
            ) : null}
          </>
        )}
      </div>
      <RejectSheet
        open={withdrawing}
        onClose={() => setWithdrawing(false)}
        title="Withdraw this offer"
        description="The buyer no longer sees it. If they paid to unlock it, the credits go back to them. Your reason is kept in the audit log."
        quickReasons={WITHDRAW_REASONS}
        submitLabel="Withdraw"
        onSubmit={async (reason) => {
          if (!quote.offerId) return;
          await act(() => adminApi.withdrawOffer(quote.offerId as string, reason), "Offer withdrawn");
        }}
      />
    </li>
  );
}
