"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";
import { trade, type Sample, type SampleStatus } from "@/lib/trade";
import { formatDay } from "@/lib/verification";
import { Button } from "@/components/ui/Button";
import { Chip, type ChipTone } from "@/components/ui/Chip";
import { HoldButton, Segmented } from "@/components/ui/Controls";
import { Input } from "@/components/ui/Field";
import { Card } from "@/components/ui/Surface";
import { useToast } from "@/components/ui/Toast";

const LABEL: Record<SampleStatus, { buyer: string; seller: string; tone: ChipTone }> = {
  requested: { buyer: "Being prepared", seller: "Please send it", tone: "move" },
  seller_dispatched: { buyer: "Being prepared", seller: "On its way to the hub", tone: "move" },
  at_hub: { buyer: "Being prepared", seller: "At the hub", tone: "move" },
  split_sealed: { buyer: "Being prepared", seller: "At the hub", tone: "move" },
  forwarded: { buyer: "On its way to you", seller: "At the hub", tone: "move" },
  buyer_received: { buyer: "Delivered", seller: "At the hub", tone: "move" },
  reviewed: { buyer: "Reviewed", seller: "Reviewed", tone: "verified" },
};

/**
 * Samples on a deal (CX-102, A-077). The buyer asks and pays the sample fee
 * in credits; the seller sends it to Corridor One X's hub, which seals it
 * and forwards it under its own name. Each side sees only its own leg.
 */
export function DealSamples({ dealCode, side, canWrite }: { dealCode: string; side: "buyer" | "seller"; canWrite: boolean }) {
  const toast = useToast();
  const [items, setItems] = useState<Sample[] | null>(null);
  const [courier, setCourier] = useState("");
  const [verdict, setVerdict] = useState<"passed" | "failed">("passed");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [fee, setFee] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await trade.listSamples(dealCode));
    } catch {
      setItems([]);
    }
  }, [dealCode]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (side !== "buyer") return;
    api
      .getWallet()
      .then((w) => setFee(w.prices.find((p) => p.action === "SAMPLE_FEE")?.credits ?? null))
      .catch(() => undefined);
  }, [side]);

  const act = async (fn: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      toast(done, "verified");
      setCourier("");
      setNote("");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const open = items?.find((s) => s.status !== "reviewed") ?? null;

  return (
    <Card as="section" aria-labelledby="samples-title" className="rounded-[26px] p-5 sm:p-6">
      <h2 id="samples-title" className="t-title3 text-fg">
        Samples
      </h2>
      <p className="t-sub mt-1 text-fg-3">
        {side === "buyer"
          ? "Ask for a sample before you agree terms. Corridor One X receives it, seals it and sends it to you under its own name."
          : "Send the sample to Corridor One X’s hub, without your company name on the pack. The buyer never sees where it came from."}
      </p>

      {items?.length ? (
        <ul className="mt-4 space-y-3">
          {items.map((s) => {
            const l = LABEL[s.status];
            return (
              <li key={s.id} className="well rounded-[18px] p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="t-callout font-medium text-fg">Asked for on {formatDay(s.createdAt)}</p>
                  <Chip tone={s.verdict === "failed" ? "frozen" : l.tone} size="sm" noIcon>
                    {s.verdict ? (s.verdict === "passed" ? "Passed" : "Did not pass") : l[side]}
                  </Chip>
                </div>
                {s.hubAddress ? (
                  <p className="t-sub mt-2 text-fg-2">
                    Send it to: <span className="text-fg">{s.hubAddress}</span>
                  </p>
                ) : null}
                {s.courierRef ? <p className="t-sub t-code mt-1 text-fg-3">Your courier: {s.courierRef}</p> : null}
                {s.forwardCourierRef ? <p className="t-sub t-code mt-1 text-fg-3">Tracking: {s.forwardCourierRef}</p> : null}
                {s.reviewNote ? <p className="t-sub mt-1 text-fg-2">“{s.reviewNote}”</p> : null}

                {canWrite && side === "seller" && s.status === "requested" ? (
                  <div className="mt-3 flex flex-wrap items-end gap-2">
                    <Input
                      label="Courier and tracking number"
                      value={courier}
                      maxLength={100}
                      placeholder="e.g. DTDC D1234567"
                      onChange={(e) => setCourier(e.target.value)}
                      className="min-w-0 flex-1"
                      inputClassName="t-code"
                    />
                    <Button
                      loading={busy}
                      disabled={courier.trim().length < 4}
                      onClick={() => void act(() => trade.dispatchSample(dealCode, s.id, courier.trim()), "Thanks. The hub will confirm when it arrives.")}
                    >
                      I’ve sent it
                    </Button>
                  </div>
                ) : null}

                {canWrite && side === "buyer" && s.status === "buyer_received" ? (
                  <div className="mt-3 space-y-3">
                    <Segmented
                      label="Did the sample meet your specification?"
                      value={verdict}
                      onChange={(v) => setVerdict(v as "passed" | "failed")}
                      options={[
                        { value: "passed", label: "It passed" },
                        { value: "failed", label: "It did not pass" },
                      ]}
                    />
                    <Input
                      label="Note"
                      optional
                      maxLength={500}
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      hint="What you found, e.g. moisture or grain length. No names or contact details."
                    />
                    <div className="flex justify-end">
                      <Button
                        loading={busy}
                        onClick={() => void act(() => trade.reviewSample(dealCode, s.id, verdict, note.trim() || null), "Result recorded")}
                      >
                        Record the result
                      </Button>
                    </div>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}

      {error ? <p role="alert" className="t-sub mt-3 text-danger">{error}</p> : null}
      {canWrite && side === "buyer" && items && !open ? (
        <div className="mt-4 flex justify-end">
          <HoldButton tone="commit" icon="check" onCommit={() => void act(() => trade.requestSample(dealCode), "Sample asked for. The seller has been told.")}>
            Ask for a sample{fee !== null ? ` · ${fee} credits` : ""}
          </HoldButton>
        </div>
      ) : null}
    </Card>
  );
}
