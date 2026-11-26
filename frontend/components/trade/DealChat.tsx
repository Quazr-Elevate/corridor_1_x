"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { trade, type ChatMessage, type DealChat as Chat } from "@/lib/trade";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Textarea } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { Notice } from "@/components/ui/Surface";

const REFRESH_MS = 15_000;

function time(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/**
 * A deal's chat, as one side sees it (A-074). The trader talks to Corridor
 * One X; the other side's messages arrive by company code once the leak
 * filter has passed them. Refreshes every 15 seconds while open.
 */
export function DealChat({ chat: initial }: { chat: Chat }) {
  const [chat, setChat] = useState<Chat>(initial);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLOListElement>(null);

  const refresh = useCallback(async () => {
    try {
      setChat(await trade.dealChat(initial.dealCode));
    } catch {
      /* keep what is on screen; the next tick tries again */
    }
  }, [initial.dealCode]);

  useEffect(() => {
    const t = window.setInterval(() => void refresh(), REFRESH_MS);
    return () => window.clearInterval(t);
  }, [refresh]);

  useEffect(() => {
    listRef.current?.lastElementChild?.scrollIntoView({ block: "nearest" });
  }, [chat.messages.length]);

  const send = async () => {
    const body = draft.trim();
    if (!body) return;
    setSending(true);
    setError(null);
    try {
      await trade.sendDealMessage(chat.dealCode, body);
      setDraft("");
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn’t send the message.");
      await refresh();
    } finally {
      setSending(false);
    }
  };

  return (
    <section aria-labelledby="chat-title" className="relief rounded-[26px] p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="chat-title" className="t-title3 text-fg">
          Negotiation
        </h2>
        <p className="t-code text-fg-3">
          {chat.dealCode}
          {chat.counterpartyCode ? ` · with ${chat.counterpartyCode}` : ""}
        </p>
      </div>
      <p className="t-sub mt-1 text-fg-3">
        You talk to Corridor One X. The other side sees only your company code. Messages with phone numbers, emails,
        links or company names are refused.
      </p>

      <ol ref={listRef} className="mt-5 max-h-[28rem] space-y-3 overflow-y-auto pr-1" aria-live="polite">
        {chat.messages.map((m) => (
          <Line key={m.id} m={m} />
        ))}
      </ol>

      {chat.suspended ? (
        <Notice tone="frozen" title="Your company can’t send messages right now" className="mt-5">
          Three messages were blocked for contact details. Contact support to have the suspension reviewed.
        </Notice>
      ) : chat.canWrite ? (
        <div className="mt-5">
          <Textarea
            label="Message"
            value={draft}
            maxLength={2000}
            counter
            rows={3}
            error={error}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void send();
            }}
          />
          <div className="mt-3 flex items-center justify-end gap-3">
            <span className="t-sub text-fg-3">Ctrl + Enter to send</span>
            <Button icon="arrow-right" loading={sending} disabled={!draft.trim()} onClick={() => void send()}>
              Send
            </Button>
          </div>
        </div>
      ) : (
        <p className="t-sub mt-5 text-fg-3">This conversation is closed.</p>
      )}
    </section>
  );
}

function Line({ m }: { m: ChatMessage }) {
  if (m.author === "system") {
    return (
      <li className="t-sub flex items-start gap-2 rounded-[16px] px-3 py-2 text-fg-3">
        <Icon name="info" size={14} className="mt-0.5 shrink-0" />
        <span>{m.body}</span>
      </li>
    );
  }
  const mine = m.author === "you";
  const who = mine ? "You" : m.author === "corridor" ? "Corridor One X" : (m.senderCode ?? "The other side");
  return (
    <li className={cn("flex", mine ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-[18px] px-4 py-3",
          mine ? "bg-ink text-cream" : m.author === "corridor" ? "bg-lime-soft text-fg" : "well text-fg",
        )}
      >
        <p className={cn("t-foot font-semibold", mine ? "text-cream/70" : "text-fg-3")}>
          {who} · {time(m.createdAt)}
        </p>
        <p className="t-body mt-1 whitespace-pre-wrap break-words">{m.body}</p>
        {m.status === "held" ? (
          <Chip tone="move" size="sm" noIcon className="mt-2">
            Waiting for Corridor One X to check it
          </Chip>
        ) : m.status === "rejected" ? (
          <p className={cn("t-sub mt-2", mine ? "text-cream/80" : "text-danger")}>Not passed on: {m.note}</p>
        ) : null}
      </div>
    </li>
  );
}
