"use client";

import { useCallback, useEffect, useState } from "react";
import { adminApi, errorMessage, type DeskDealChat, type HeldMessage } from "@/lib/adminApi";
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
