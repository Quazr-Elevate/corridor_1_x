"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { api, type RevealedContact } from "@/lib/api";
import { RevealCard } from "./RevealCard";

type Status = "anonymous" | "unverified" | "verified" | "checking";

/**
 * 3-way "Request contact" gate for the product detail page.
 *
 * Anonymous  → CTA links to /login?next=<current url>
 * Signed-in but not admin-verified → complete-your-verification panel
 *              with deep-link to /dashboard/profile
 * Verified   → placeholder reveal card (Sprint 3 wires the real endpoint)
 *
 * Kept in one component so the product page doesn't hand-roll the logic.
 * When we build the real reveal card, only this file needs to change.
 */
export function ContactGate({
  productId,
  productName,
}: {
  productId: string;
  productName: string;
}) {
  const [status, setStatus] = useState<Status>("checking");
  const [contact, setContact] = useState<RevealedContact | null>(null);
  const [revealing, setRevealing] = useState(false);
  const [revealError, setRevealError] = useState<string | null>(null);

  const doReveal = async () => {
    setRevealing(true);
    setRevealError(null);
    try {
      const c = await api.revealContact(productId);
      setContact(c);
    } catch (err) {
      setRevealError(
        err instanceof Error ? err.message : "Could not reveal contact",
      );
    } finally {
      setRevealing(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // /auth/session tells us if we have a session cookie at all —
        // cheap probe, no DB hit.
        const s = await api.session();
        if (cancelled) return;
        if (!s.userId) {
          setStatus("anonymous");
          return;
        }
        // Have a session → check if we're verified.
        try {
          const me = await api.me();
          if (cancelled) return;
          setStatus(me.status === "verified" ? "verified" : "unverified");
        } catch {
          if (!cancelled) setStatus("anonymous");
        }
      } catch {
        if (!cancelled) setStatus("anonymous");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (status === "checking") {
    return (
      <div className="rounded-card border border-line-soft bg-ink-soft/60 p-4 text-sm text-paper-muted">
        Checking…
      </div>
    );
  }

  if (status === "anonymous") {
    const next = encodeURIComponent(`/products/${productId}?action=reveal`);
    return (
      <GatePanel
        title="Contact the seller"
        body={`Sign in to reveal ${productName}'s seller contact details. New here? Signup takes 30 seconds.`}
      >
        <Link href={`/login?next=${next}`} className="btn-primary">
          Sign in to reveal <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
        <Link href={`/signup?next=${next}`} className="btn-ghost">
          Create an account
        </Link>
      </GatePanel>
    );
  }

  if (status === "unverified") {
    return (
      <GatePanel
        title="Verify your profile to reveal contact"
        body="We only share seller contact details with admin-verified buyers. Complete your profile — it takes a few minutes."
      >
        <Link href="/dashboard/profile" className="btn-primary">
          Complete verification <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
      </GatePanel>
    );
  }

  // status === "verified"
  if (contact) {
    return <RevealCard contact={contact} />;
  }
  return (
    <GatePanel
      title="Ready to unlock"
      body={`Reveal ${productName}'s seller contact — phone, email, and full address. This is a one-time consent grant per product; you can come back later without re-verifying.`}
    >
      <Button
        variant="primary"
        onClick={doReveal}
        loading={revealing}
      >
        Reveal contact <ArrowRight className="h-4 w-4" aria-hidden />
      </Button>
      {revealError && (
        <p className="mt-2 w-full text-xs font-medium text-danger">
          {revealError}
        </p>
      )}
    </GatePanel>
  );
}

function GatePanel({
  title,
  body,
  children,
}: {
  title: string;
  body: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-card border border-line-soft bg-ink-soft/60 p-5 backdrop-blur-sm">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink-elevated ring-1 ring-line">
          <ShieldCheck aria-hidden className="h-4 w-4 text-accent" />
        </span>
        <div className="flex-1">
          <h3 className="text-sm font-medium text-paper">{title}</h3>
          <p className="mt-1 text-xs leading-relaxed text-paper-muted">{body}</p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">{children}</div>
    </div>
  );
}
