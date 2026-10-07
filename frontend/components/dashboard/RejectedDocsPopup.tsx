"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, ArrowRight, X } from "lucide-react";
import { api, type VerificationDoc } from "@/lib/api";
import { useMe } from "@/lib/useMe";

/**
 * On dashboard mount, fetch the user's docs. For any rejected doc the user
 * hasn't acknowledged yet (tracked in localStorage), queue a popup.
 *
 * Acknowledgements are keyed per **user** so that signing in as a different
 * account doesn't inherit the previous person's dismissals (and a single
 * person on a shared machine doesn't miss their own popups because
 * someone else dismissed one earlier). Within a user, the set is still
 * keyed by doc id — a brand new rejection on a replacement upload shows
 * because the id is different.
 */

const ACK_KEY_PREFIX = "cor1x.rejectedDocsAcknowledged.";

function ackKey(userId: string): string {
  return `${ACK_KEY_PREFIX}${userId}`;
}

function loadAcknowledged(userId: string): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(ackKey(userId));
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

function saveAcknowledged(userId: string, ids: Set<string>) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(ackKey(userId), JSON.stringify(Array.from(ids)));
  } catch {
    // localStorage can throw in private windows — silently ignore.
  }
}

export function RejectedDocsPopup() {
  const router = useRouter();
  const { me } = useMe();
  const [queue, setQueue] = useState<VerificationDoc[]>([]);
  const [acknowledged, setAcknowledged] = useState<Set<string>>(new Set());

  // Re-run whenever the signed-in user changes. On a fresh session the
  // first render has ``me === null``; the effect fires again once
  // useMe() resolves.
  useEffect(() => {
    if (!me) return;
    const userId = me.userId;
    const ack = loadAcknowledged(userId);
    setAcknowledged(ack);

    let cancelled = false;
    (async () => {
      try {
        const docs = await api.listVerificationDocs();
        if (cancelled) return;
        const rejected = docs.filter(
          (d) => d.status === "rejected" && !ack.has(d.id),
        );
        setQueue(rejected);
      } catch {
        // Not fatal — just means we skip the popup this time.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [me?.userId]);

  const current = queue[0];
  if (!current || !me) return null;

  function dismiss() {
    const next = new Set(acknowledged);
    next.add(current!.id);
    setAcknowledged(next);
    saveAcknowledged(me!.userId, next);
    setQueue((q) => q.slice(1));
  }

  function goToUpload() {
    dismiss();
    router.push(`/dashboard/account?tab=business&doc=${current!.id}`);
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={dismiss}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-card border border-danger/40 bg-ink-soft shadow-card overflow-hidden"
      >
        <div className="flex items-start gap-3 p-5 border-b border-line-soft">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-danger/15 text-danger">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold text-paper">
              Document rejected
            </h2>
            <p className="mt-0.5 text-xs text-paper-muted">
              {current.certType}
            </p>
          </div>
          <button
            type="button"
            onClick={dismiss}
            aria-label="Dismiss"
            className="rounded-full p-1.5 text-paper-muted hover:bg-ink-elevated hover:text-paper transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-paper-muted mb-2">
            Admin&apos;s note
          </p>
          <div className="rounded-field border border-danger/30 bg-danger/5 p-3">
            <p className="text-sm text-paper leading-relaxed">
              {current.rejectionReason || "No reason provided."}
            </p>
          </div>
          <p className="mt-4 text-xs text-paper-muted leading-relaxed">
            Delete the rejected entry and upload a replacement to re-submit.
          </p>
          {queue.length > 1 && (
            <p className="mt-2 text-[11px] text-paper-muted/80">
              + {queue.length - 1} more rejected document
              {queue.length - 1 === 1 ? "" : "s"} to review after this.
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-line-soft">
          <button
            type="button"
            onClick={dismiss}
            className="rounded-field border border-line-soft bg-transparent px-3 py-2 text-xs font-semibold text-paper-muted hover:text-paper transition"
          >
            Later
          </button>
          <button
            type="button"
            onClick={goToUpload}
            className="inline-flex items-center gap-1.5 rounded-field bg-accent px-4 py-2 text-xs font-semibold text-accent-fg shadow-cta hover:bg-accent-hover transition"
          >
            Go to document
            <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          </button>
        </div>
      </div>
    </div>
  );
}
