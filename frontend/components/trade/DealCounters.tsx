"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { money, toMinor, trade, type Counter } from "@/lib/trade";
import { Button } from "@/components/ui/Button";
import { Chip, type ChipTone } from "@/components/ui/Chip";
import { HoldButton } from "@/components/ui/Controls";
import { Input } from "@/components/ui/Field";
import { Card } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";

const STATUS: Record<Counter["status"], { mine: string; theirs: string; tone: ChipTone }> = {
  pending_desk: { mine: "With Corridor One X", theirs: "", tone: "move" },
  relayed: { mine: "Sent to the other side", theirs: "Waiting for your answer", tone: "move" },
  accepted: { mine: "Accepted", theirs: "You accepted", tone: "verified" },
  declined: { mine: "Declined", theirs: "You declined", tone: "neutral" },
  rejected: { mine: "Not passed on", theirs: "", tone: "frozen" },
  superseded: { mine: "Replaced", theirs: "Replaced", tone: "neutral" },
};

/**
 * Counter-offers on a deal (CX-101). Prices are always in this side's own
 * currency; Corridor One X checks each before the other side sees it.
 */
export function DealCounters({ dealCode, currency, canWrite }: { dealCode: string; currency: string | null; canWrite: boolean }) {
  const toast = useToast();
  const [items, setItems] = useState<Counter[] | null>(null);
  const [price, setPrice] = useState("");
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setItems(await trade.listCounters(dealCode));
    } catch {
      setItems([]);
    }
  }, [dealCode]);

  useEffect(() => {
    void load();
  }, [load]);

  const propose = async () => {
    const minor = toMinor(price);
    if (!minor) return setError("Enter a price per unit, e.g. 820.50.");
    setBusy(true);
    setError(null);
    try {
      await trade.proposeCounter(dealCode, { priceMinor: minor, quantity: quantity.trim() || null, note: note.trim() || null });
      setPrice("");
      setQuantity("");
      setNote("");
      toast("Counter-offer sent to Corridor One X");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn’t send the counter-offer.");
    } finally {
      setBusy(false);
    }
  };

  const answer = async (c: Counter, accept: boolean) => {
    try {
      await trade.answerCounter(dealCode, c.id, accept);
      toast(accept ? "Accepted. Corridor One X will prepare the term sheet." : "Declined");
      await load();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Couldn’t answer it.");
    }
  };

  return (
    <Card as="section" aria-labelledby="counters-title" className="rounded-[26px] p-5 sm:p-6">
      <h2 id="counters-title" className="t-title3 text-fg">
        Counter-offers
      </h2>
      <p className="t-sub mt-1 text-fg-3">
        Change the price here, not in the chat. Corridor One X checks each counter-offer before the other side sees it,
        in their own currency.
      </p>

      {items?.length ? (
        <ul className="mt-4 space-y-3">
          {items.map((c) => {
            const s = STATUS[c.status];
            const label = c.mine ? s.mine : s.theirs;
            return (
              <li key={c.id} className="well rounded-[18px] p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="t-callout font-medium text-fg">
                    {c.mine ? "You proposed" : "The other side proposes"} {money(c.priceMinor, c.currency)} per unit
                    {c.quantity ? ` · ${Number(c.quantity)} units` : ""}
                  </p>
                  {label ? (
                    <Chip tone={s.tone} size="sm" noIcon>
                      {label}
                    </Chip>
                  ) : null}
                </div>
                {c.note ? <p className="t-sub mt-1 text-fg-2">“{c.note}”</p> : null}
                {c.decisionNote ? <p className="t-sub mt-1 text-danger">Corridor One X: {c.decisionNote}</p> : null}
                {!c.mine && c.status === "relayed" && canWrite ? (
                  <div className="mt-3 flex flex-wrap justify-end gap-2">
                    <Button size="sm" variant="quiet" onClick={() => void answer(c, false)}>
                      Decline
                    </Button>
                    <HoldButton size="sm" tone="commit" icon="check" onCommit={() => void answer(c, true)}>
                      Accept
                    </HoldButton>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}

      {canWrite ? (
        <div className="mt-5 grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <Input
            label={`Your price per unit${currency ? ` (${currency})` : ""}`}
            inputMode="decimal"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            inputClassName="t-code"
          />
          <Input label="Quantity" optional inputMode="decimal" value={quantity} onChange={(e) => setQuantity(e.target.value)} inputClassName="t-code" />
          <Input
            label="Note"
            optional
            maxLength={500}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="sm:col-span-2"
            hint="No names or contact details; they are refused."
          />
          {error ? <p role="alert" className="t-sub text-danger sm:col-span-2">{error}</p> : null}
          <div className="flex justify-end sm:col-span-2">
            <Button loading={busy} disabled={!price.trim()} onClick={() => void propose()}>
              Send counter-offer
            </Button>
          </div>
        </div>
      ) : null}
    </Card>
  );
}
