"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi, errorMessage, type DeskCounter, type DeskDealChat, type DeskSample, type HeldMessage } from "@/lib/adminApi";
import { money } from "@/lib/trade";
import { Input } from "@/components/ui/Field";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { RejectSheet } from "@/components/admin/RejectSheet";
import { fmtAgo } from "@/components/admin/format";

const ORIGIN = { own: "Wrote", relay: "Passed on from", desk: "Corridor One X", system: "Event" } as const;

/**
 * Messages the leak filter held for a person (A-074). Releasing one passes
 * it to the other side; rejecting tells the sender why.
 */
export function HeldMessages({ onDecided }: { onDecided?: () => void }) {
  const toast = useToast();
  const [items, setItems] = useState<HeldMessage[] | null>(null);
  const [rejecting, setRejecting] = useState<HeldMessage | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await adminApi.heldMessages());
    } catch {
      setItems([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!items?.length) return null;
  const release = async (m: HeldMessage) => {
    setBusy(m.id);
    try {
      await adminApi.releaseMessage(m.id);
      toast("Passed on to the other side");
      await load();
      onDecided?.();
    } catch (e) {
      toast(errorMessage(e, "Couldn’t release it."), "frozen");
    } finally {
      setBusy(null);
    }
  };

  return (
    <section aria-labelledby="held-h" className="relief rounded-[26px] p-5">
      <h2 id="held-h" className="t-title3 text-fg">
        Messages to check · {items.length}
      </h2>
      <p className="t-sub mt-1 text-fg-3">The filter thinks these may name a company. Pass each on, or tell the sender why not.</p>
      <ul className="mt-4 space-y-3">
        {items.map((m) => (
          <li key={m.id} className="well rounded-[18px] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="t-code text-fg-2">
                {m.dealCode} · {m.side} · {m.senderCode ?? "—"}
              </p>
              <span className="t-sub text-fg-3">{fmtAgo(m.createdAt)}</span>
            </div>
            <p className="t-body mt-2 whitespace-pre-wrap break-words text-fg">{m.body}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {m.flags.map((f) => (
                <Chip key={f} tone="move" size="sm" noIcon>
                  {f}
                </Chip>
              ))}
            </div>
            <div className="mt-3 flex justify-end gap-2">
              <Button size="sm" variant="danger" disabled={busy === m.id} onClick={() => setRejecting(m)}>
                Don’t pass on…
              </Button>
              <Button size="sm" variant="secondary" loading={busy === m.id} onClick={() => void release(m)}>
                Pass on
              </Button>
            </div>
          </li>
        ))}
      </ul>
      <RejectSheet
        open={rejecting !== null}
        onClose={() => setRejecting(null)}
        title="Don’t pass this message on"
        description="The sender sees your reason under their message."
        quickReasons={["This names a company. Use your company code instead.", "This points to contact details outside Corridor One X."]}
        submitLabel="Don’t pass on"
        onSubmit={async (reason) => {
          if (!rejecting) return;
          await adminApi.rejectMessage(rejecting.id, reason);
          toast("The sender has been told why");
          await load();
          onDecided?.();
        }}
      />
    </section>
  );
}

/** Both threads of a deal in negotiation, and a box to write into either. */
export function DeskDealChatPanel({ dealCode }: { dealCode: string }) {
  const toast = useToast();
  const [chat, setChat] = useState<DeskDealChat | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    adminApi
      .dealChat(dealCode)
      .then((c) => live && setChat(c))
      .catch(() => live && setChat(null));
    return () => {
      live = false;
    };
  }, [dealCode]);

  if (!chat) return null;
  const write = async (side: "buyer" | "seller") => {
    const body = (drafts[side] ?? "").trim();
    if (!body) return;
    setBusy(true);
    try {
      setChat(await adminApi.writeToThread(dealCode, side, body));
      setDrafts((d) => ({ ...d, [side]: "" }));
    } catch (e) {
      toast(errorMessage(e, "Couldn’t send it."), "frozen");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <p className="t-label text-fg-3">Negotiation · {chat.dealStatus.toLowerCase()}</p>
      <div className="mt-2 grid gap-4 xl:grid-cols-2">
        {chat.threads.map((t) => (
          <section key={t.side} aria-label={`${t.side} thread`} className="well rounded-[20px] p-4">
            <p className="t-code text-fg-2">
              {t.side === "buyer" ? "Buyer" : "Seller"} · {t.companyCode ?? "—"}
              {t.suspended ? " · suspended" : ""}
            </p>
            <ol className="mt-3 max-h-80 space-y-2 overflow-y-auto">
              {t.messages.map((m) => (
                <li key={m.id} className={cn("rounded-[14px] px-3 py-2", m.origin === "desk" ? "bg-lime-soft" : "bg-fg/[0.04]")}>
                  <p className="t-foot text-fg-3">
                    {ORIGIN[m.origin]}
                    {m.origin === "relay" || m.origin === "own" ? ` ${m.senderCode ?? ""}` : ""} · {fmtAgo(m.createdAt)}
                    {m.status !== "delivered" ? ` · ${m.status}` : ""}
                  </p>
                  <p className="t-sub mt-0.5 whitespace-pre-wrap break-words text-fg">{m.body}</p>
                  {m.note ? <p className="t-foot mt-1 text-danger">Reason: {m.note}</p> : null}
                </li>
              ))}
            </ol>
            {chat.dealStatus === "NEGOTIATING" ? (
              <div className="mt-3">
                <Textarea
                  label={`Write to the ${t.side}`}
                  rows={2}
                  maxLength={2000}
                  value={drafts[t.side] ?? ""}
                  onChange={(e) => setDrafts((d) => ({ ...d, [t.side]: e.target.value }))}
                />
                <div className="mt-2 flex justify-end">
                  <Button size="sm" disabled={busy || !(drafts[t.side] ?? "").trim()} onClick={() => void write(t.side)}>
                    Send as Corridor One X
                  </Button>
                </div>
              </div>
            ) : null}
          </section>
        ))}
      </div>
    </div>
  );
}

/**
 * Counter-offers waiting for the desk (CX-101): what the side proposed, what
 * it means for the other side, and the margin. Pass it on (optionally at
 * another margin) or refuse it with a reason the proposer reads.
 */
export function PendingCounters() {
  const toast = useToast();
  const [items, setItems] = useState<DeskCounter[] | null>(null);
  const [margins, setMargins] = useState<Record<string, string>>({});
  const [rejecting, setRejecting] = useState<DeskCounter | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await adminApi.pendingCounters());
    } catch {
      setItems([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!items?.length) return null;
  const relay = async (c: DeskCounter) => {
    setBusy(c.id);
    try {
      await adminApi.relayCounter(c.id, margins[c.id]?.trim() || undefined);
      toast("Counter-offer passed on");
      await load();
    } catch (e) {
      toast(errorMessage(e, "Couldn’t pass it on."), "frozen");
    } finally {
      setBusy(null);
    }
  };

  return (
    <section aria-labelledby="counters-h" className="relief rounded-[26px] p-5">
      <h2 id="counters-h" className="t-title3 text-fg">
        Counter-offers to check · {items.length}
      </h2>
      <ul className="mt-4 space-y-3">
        {items.map((c) => (
          <li key={c.id} className="well rounded-[18px] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="t-code text-fg-2">
                {c.dealCode} · from the {c.side}
              </p>
              <span className="t-sub text-fg-3">{fmtAgo(c.createdAt)}</span>
            </div>
            <p className="t-body mt-2 text-fg">
              {c.side === "buyer" ? "Buyer offers" : "Seller asks"} {money(c.priceMinor, c.currency)} per unit
              {c.quantity ? ` for ${Number(c.quantity)} units` : ""} → {c.side === "buyer" ? "seller would get" : "buyer would pay"}{" "}
              <span className="font-semibold">{money(c.impliedMinor, c.impliedCurrency)}</span> at {Number(c.marginPct)}% margin.
            </p>
            {c.note ? <p className="t-sub mt-1 text-fg-2">“{c.note}”</p> : null}
            <div className="mt-3 flex flex-wrap items-end justify-end gap-2">
              <Input
                label={`Margin % (limits ${Number(c.minMarginPct)}–${c.maxMarginPct ? Number(c.maxMarginPct) : "—"})`}
                optional
                inputMode="decimal"
                value={margins[c.id] ?? ""}
                placeholder={String(Number(c.marginPct))}
                onChange={(e) => setMargins((m) => ({ ...m, [c.id]: e.target.value }))}
                className="w-48"
                inputClassName="t-code"
              />
              <Button size="sm" variant="danger" disabled={busy === c.id} onClick={() => setRejecting(c)}>
                Refuse…
              </Button>
              <Button size="sm" variant="secondary" loading={busy === c.id} onClick={() => void relay(c)}>
                Pass on
              </Button>
            </div>
          </li>
        ))}
      </ul>
      <RejectSheet
        open={rejecting !== null}
        onClose={() => setRejecting(null)}
        title="Refuse this counter-offer"
        description="The side that made it reads your reason. The other side never sees it."
        quickReasons={["The price is outside what the other side can accept.", "The quantity can't be supplied in this window."]}
        submitLabel="Refuse"
        onSubmit={async (reason) => {
          if (!rejecting) return;
          await adminApi.rejectCounter(rejecting.id, reason);
          toast("The proposer has been told why");
          await load();
        }}
      />
    </section>
  );
}

const SAMPLE_STEP: Record<DeskSample["status"], string> = {
  requested: "Waiting for the seller to send it",
  seller_dispatched: "On its way to the hub",
  at_hub: "At the hub: split and seal",
  split_sealed: "Sealed: forward to the buyer",
  forwarded: "On its way to the buyer",
  buyer_received: "With the buyer: waiting for the result",
  reviewed: "Reviewed",
};

/**
 * Samples not yet reviewed (CX-102). The desk records each hop at the hub:
 * arrived, split and sealed (two seal numbers), forwarded, delivered.
 * Forwarding is refused until both halves are sealed.
 */
export function OpenSamples() {
  const toast = useToast();
  const [items, setItems] = useState<DeskSample[] | null>(null);
  const [form, setForm] = useState<Record<string, { retained?: string; forward?: string; courier?: string }>>({});
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await adminApi.openSamples());
    } catch {
      setItems([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!items?.length) return null;
  const set = (id: string, k: "retained" | "forward" | "courier", v: string) =>
    setForm((f) => ({ ...f, [id]: { ...f[id], [k]: v } }));
  const run = async (id: string, fn: () => Promise<unknown>, done: string) => {
    setBusy(id);
    try {
      await fn();
      toast(done);
      await load();
    } catch (e) {
      toast(errorMessage(e, "Couldn’t record it."), "frozen");
    } finally {
      setBusy(null);
    }
  };

  return (
    <section aria-labelledby="samples-h" className="relief rounded-[26px] p-5">
      <h2 id="samples-h" className="t-title3 text-fg">
        Samples in progress · {items.length}
      </h2>
      <ul className="mt-4 space-y-3">
        {items.map((s) => {
          const f = form[s.id] ?? {};
          return (
            <li key={s.id} className="well rounded-[18px] p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="t-code text-fg-2">{s.dealCode}</p>
                <span className="t-sub text-fg-3">asked {fmtAgo(s.createdAt)}</span>
              </div>
              <p className="t-body mt-2 text-fg">{SAMPLE_STEP[s.status]}</p>
              <p className="t-sub t-code mt-1 text-fg-3">
                {[
                  s.sellerCourierRef && `Seller courier ${s.sellerCourierRef}`,
                  s.retainedSealNo && `Retained seal ${s.retainedSealNo}`,
                  s.forwardSealNo && `Forward seal ${s.forwardSealNo}`,
                  s.forwardCourierRef && `Our courier ${s.forwardCourierRef}`,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              <div className="mt-3 flex flex-wrap items-end justify-end gap-2">
                {s.status === "seller_dispatched" ? (
                  <Button size="sm" variant="secondary" loading={busy === s.id} onClick={() => void run(s.id, () => adminApi.sampleAtHub(s.id), "Marked as arrived")}>
                    It has arrived
                  </Button>
                ) : null}
                {s.status === "at_hub" ? (
                  <>
                    <Input label="Retained seal no." value={f.retained ?? ""} onChange={(e) => set(s.id, "retained", e.target.value)} className="w-44" inputClassName="t-code" />
                    <Input label="Forward seal no." value={f.forward ?? ""} onChange={(e) => set(s.id, "forward", e.target.value)} className="w-44" inputClassName="t-code" />
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={busy === s.id}
                      disabled={!f.retained?.trim() || !f.forward?.trim()}
                      onClick={() => void run(s.id, () => adminApi.sealSample(s.id, f.retained!.trim(), f.forward!.trim()), "Sealed")}
                    >
                      Record seals
                    </Button>
                  </>
                ) : null}
                {s.status === "split_sealed" ? (
                  <>
                    <Input label="Courier and tracking no." value={f.courier ?? ""} onChange={(e) => set(s.id, "courier", e.target.value)} className="w-56" inputClassName="t-code" />
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={busy === s.id}
                      disabled={!f.courier?.trim()}
                      onClick={() => void run(s.id, () => adminApi.forwardSample(s.id, f.courier!.trim()), "Forwarded; the buyer has been told")}
                    >
                      Forward to buyer
                    </Button>
                  </>
                ) : null}
                {s.status === "forwarded" ? (
                  <Button size="sm" variant="secondary" loading={busy === s.id} onClick={() => void run(s.id, () => adminApi.sampleReceived(s.id), "Marked as delivered")}>
                    Delivered to buyer
                  </Button>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
