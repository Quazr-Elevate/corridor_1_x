"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { money, paymentLabel, trade, type TermSheet } from "@/lib/trade";
import { formatDay } from "@/lib/verification";
import { Button } from "@/components/ui/Button";
import { Chip, type ChipTone } from "@/components/ui/Chip";
import { HoldButton } from "@/components/ui/Controls";
import { KeyValueList } from "@/components/ui/Data";
import { Textarea } from "@/components/ui/Field";
import { Card, Notice, SolidPanel } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";

const STATUS: Record<TermSheet["status"], { label: string; tone: ChipTone }> = {
  issued: { label: "Your move", tone: "move" },
  agreed: { label: "Agreed", tone: "verified" },
  declined: { label: "Declined", tone: "frozen" },
  withdrawn: { label: "Withdrawn", tone: "neutral" },
  superseded: { label: "Replaced", tone: "neutral" },
};

function delivery(t: TermSheet): string | null {
  if (!t.deliveryFrom && !t.deliveryTo) return null;
  return `${formatDay(t.deliveryFrom) || "—"} to ${formatDay(t.deliveryTo) || "—"}`;
}

function Terms({ t }: { t: TermSheet }) {
  return (
    <KeyValueList
      items={[
        { label: "Product", value: t.product },
        { label: "Quality", value: t.quality },
        { label: "Packaging", value: t.packaging },
        { label: "Quantity", value: `${Number(t.quantity)} ${t.unit}`, mono: true },
        { label: "Your price", value: `${money(t.priceMinor, t.currency)} per ${t.unit}`, mono: true },
        { label: "Payment", value: paymentLabel(t.paymentTerms) },
        { label: "Incoterm", value: t.incoterm, mono: true },
        { label: "Port of loading", value: t.portOfLoading },
        { label: "Destination port", value: t.destinationPort },
        { label: "Delivery", value: delivery(t) },
        { label: "Notes", value: t.notes },
        { label: "Reference", value: t.contentSha256.slice(0, 12), mono: true, hint: "Identifies this exact version." },
      ]}
    />
  );
}

/**
 * The deal's term sheet (CX-103, A-076). Corridor One X drafts each version;
 * both sides accept the exact text they read, and then it can't change.
 * Prices are always this side's own; change them with a counter-offer.
 */
export function DealTermSheet({ dealCode, canWrite }: { dealCode: string; canWrite: boolean }) {
  const toast = useToast();
  const [items, setItems] = useState<TermSheet[] | null>(null);
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setItems(await trade.listTermSheets(dealCode));
    } catch {
      setItems([]);
    }
  }, [dealCode]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!items?.length) return null;
  const [latest, ...older] = items;

  const accept = async () => {
    setError(null);
    try {
      const t = await trade.acceptTermSheet(dealCode, latest.version, latest.contentSha256);
      toast(t.status === "agreed" ? "Agreed. The terms are now fixed." : "Accepted. Waiting for the other side.", "verified");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn’t accept it. Try again.");
      await load();
    }
  };

  const decline = async () => {
    setBusy(true);
    setError(null);
    try {
      await trade.declineTermSheet(dealCode, latest.version, reason.trim());
      toast("Corridor One X has your reason and will send a new version.");
      setDeclining(false);
      setReason("");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn’t send it. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const s = STATUS[latest.status];
  const open = latest.status === "issued" && canWrite && !latest.youAccepted;

  return (
    <Card as="section" aria-labelledby="terms-title" className="rounded-[26px] p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="terms-title" className="t-title3 text-fg">
          Term sheet · version {latest.version}
        </h2>
        <Chip tone={s.tone} size="sm" noIcon>
          {latest.status === "issued" && latest.youAccepted ? "Waiting for the other side" : s.label}
        </Chip>
      </div>
      <p className="t-sub mt-1 text-fg-3">
        The terms Corridor One X will put in the letter of intent and the contract. To change the price, send a counter-offer.
      </p>

      {latest.status === "agreed" ? (
        <SolidPanel className="mt-4 p-5">
          <p className="t-label text-fg-2">Agreed {formatDay(latest.agreedAt)}</p>
          <div className="mt-3">
            <Terms t={latest} />
          </div>
        </SolidPanel>
      ) : (
        <div className="well mt-4 rounded-[18px] p-4">
          <Terms t={latest} />
        </div>
      )}

      {latest.status === "issued" && latest.otherAccepted && !latest.youAccepted ? (
        <Notice tone="move" className="mt-4">The other side has accepted this version.</Notice>
      ) : null}
      {latest.declineNote ? <p className="t-sub mt-3 text-fg-2">You declined: “{latest.declineNote}”</p> : null}
      {error ? <p role="alert" className="t-sub mt-3 text-danger">{error}</p> : null}

      {open && !declining ? (
        <div className="mt-4 flex flex-wrap justify-end gap-2">
          <Button variant="quiet" onClick={() => setDeclining(true)}>
            Something needs to change
          </Button>
          <HoldButton tone="commit" icon="check" onCommit={() => void accept()}>
            Accept version {latest.version}
          </HoldButton>
        </div>
      ) : null}
      {open && declining ? (
        <div className="mt-4 space-y-3">
          <Textarea
            label="What needs to change"
            counter
            maxLength={500}
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            hint="Corridor One X reads this. No names or contact details."
          />
          <div className="flex justify-end gap-2">
            <Button variant="quiet" onClick={() => setDeclining(false)}>
              Cancel
            </Button>
            <Button loading={busy} disabled={reason.trim().length < 10} onClick={() => void decline()}>
              Send to Corridor One X
            </Button>
          </div>
        </div>
      ) : null}

      {older.length ? (
        <details className="mt-4">
          <summary className="t-sub cursor-pointer text-fg-3">Earlier versions · {older.length}</summary>
          <ul className="mt-2 space-y-1">
            {older.map((t) => (
              <li key={t.version} className="t-sub flex justify-between gap-2 text-fg-2">
                <span>
                  Version {t.version} · {money(t.priceMinor, t.currency)} per {t.unit} · {Number(t.quantity)} {t.unit}
                </span>
                <span>{STATUS[t.status].label}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </Card>
  );
}
