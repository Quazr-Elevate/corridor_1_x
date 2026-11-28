"use client";

import { useEffect, useState } from "react";
import { money, trade, type Milestone } from "@/lib/trade";
import { formatDay } from "@/lib/verification";
import { Chip, type ChipTone } from "@/components/ui/Chip";
import { Card } from "@/components/ui/Surface";

const KIND: Record<Milestone["kind"], string> = {
  advance: "Advance",
  balance: "Balance",
  cad: "Cash against documents",
  lc_payment: "Letter of credit",
  da_payment: "Documents against acceptance",
  open_account: "Open account",
  escrow_funding: "Escrow funding",
  retention: "Retention",
};
const EVENT: Record<Milestone["dueEvent"], string> = {
  contract_effective: "the contract takes effect",
  shipment: "shipment",
  documents: "the shipping documents",
  acceptance: "you accept the goods",
};
const STATUS: Record<Milestone["status"], { label: string; tone: ChipTone }> = {
  open: { label: "Open", tone: "move" },
  cleared: { label: "Received", tone: "verified" },
  paid: { label: "Paid", tone: "verified" },
  void: { label: "Void", tone: "neutral" },
};

/**
 * The payments on this side of the deal (CX-110): for the buyer, what it
 * pays Corridor One X; for the seller, what Corridor One X pays it.
 */
export function DealPayments({ dealCode, side }: { dealCode: string; side: "buyer" | "seller" }) {
  const [items, setItems] = useState<Milestone[] | null>(null);

  useEffect(() => {
    let live = true;
    trade.listMilestones(dealCode).then((m) => live && setItems(m)).catch(() => live && setItems([]));
    return () => {
      live = false;
    };
  }, [dealCode]);

  if (!items?.length) return null;
  const event = (m: Milestone) =>
    side === "seller" && m.dueEvent === "acceptance" ? "the buyer accepts the goods" : EVENT[m.dueEvent];

  return (
    <Card as="section" aria-labelledby="pay-title" className="rounded-[26px] p-5 sm:p-6">
      <h2 id="pay-title" className="t-title3 text-fg">
        {side === "buyer" ? "Payments you make" : "Payments to you"}
      </h2>
      <p className="t-sub mt-1 text-fg-3">From the contract’s payment terms. All payments go through Corridor One X’s bank.</p>
      <ul className="mt-4 space-y-2">
        {items.map((m) => (
          <li key={m.sequence} className="well flex flex-wrap items-center justify-between gap-2 rounded-[18px] p-4">
            <div>
              <p className="t-callout font-medium text-fg">
                {KIND[m.kind]} · <span className="t-code">{money(m.amountMinor, m.currency)}</span>
              </p>
              <p className="t-sub text-fg-3">
                {m.dueAt ? `Due ${formatDay(m.dueAt)}` : m.dueDays ? `Due ${m.dueDays} days after ${event(m)}` : `Due on ${event(m)}`}
              </p>
            </div>
            <Chip tone={STATUS[m.status].tone} size="sm" noIcon>
              {STATUS[m.status].label}
            </Chip>
          </li>
        ))}
      </ul>
    </Card>
  );
}
