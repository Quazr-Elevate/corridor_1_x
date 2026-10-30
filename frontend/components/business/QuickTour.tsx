"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import { PASSPORT_PATH } from "@/lib/verification";
import { Button } from "@/components/ui/Button";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Sheet } from "@/components/ui/Sheet";

const STEPS: ReadonlyArray<{ icon: IconName; title: string; body: string; href?: string; cta?: string }> = [
  {
    icon: "corridor",
    title: "This is your corridor",
    body: "Your home shows your business, the moves waiting on you and the latest lots. Everything starts here.",
  },
  {
    icon: "building",
    title: "Complete your business profile",
    body: "Add your company address, logo and banner, and the documents Corridor ops needs to verify you.",
    href: PASSPORT_PATH,
    cta: "Open business profile",
  },
  {
    icon: "shield",
    title: "Get verified",
    body: "Send your profile for review. Once Corridor ops verifies you, your lots go live and buyers can reach you.",
  },
  {
    icon: "grain",
    title: "List lots and browse the market",
    body: "Add the commodities you sell under Listings, and find verified sellers in the Market.",
    href: "/dashboard/products/new",
    cta: "Create a listing",
  },
];

/**
 * First-run tour, shown until the user finishes or skips it
 * (``me.showTour``; ``PATCH /me {tourCompleted}``). "Later" only closes it
 * for this visit.
 */
export function QuickTour() {
  const { me, refetch } = useMe();
  const router = useRouter();
  const [open, setOpen] = useState(true);
  const [i, setI] = useState(0);
  const [saving, setSaving] = useState(false);

  if (!me?.showTour) return null;
  const step = STEPS[i];
  const last = i === STEPS.length - 1;

  async function finish(href?: string) {
    setSaving(true);
    try {
      await api.updateMe({ tourCompleted: true });
      await refetch();
    } catch {
      // Not critical — the tour simply shows again next time.
    }
    setSaving(false);
    setOpen(false);
    if (href) router.push(href);
  }

  return (
    <Sheet
      open={open}
      onClose={() => setOpen(false)}
      size="sm"
      title={step.title}
      description={`Quick tour · ${i + 1} of ${STEPS.length}`}
      footer={
        <>
          <Button variant="quiet" onClick={() => void finish()} disabled={saving}>
            Skip tour
          </Button>
          {i > 0 ? (
            <Button variant="secondary" onClick={() => setI(i - 1)}>
              Back
            </Button>
          ) : null}
          {last ? (
            <Button loading={saving} onClick={() => void finish()}>
              Done
            </Button>
          ) : (
            <Button iconRight="arrow-right" onClick={() => setI(i + 1)}>
              Next
            </Button>
          )}
        </>
      }
    >
      <div className="flex items-start gap-4">
        <span className="grid size-12 shrink-0 place-items-center rounded-full bg-lime-soft text-accent">
          <Icon name={step.icon} size={22} />
        </span>
        <p className="t-body text-fg-2">{step.body}</p>
      </div>
      <div className="mt-6 flex items-center justify-between gap-3">
        <div className="flex gap-1.5" aria-hidden="true">
          {STEPS.map((_, k) => (
            <span key={k} className={k === i ? "h-1.5 w-6 rounded-full bg-fg" : "h-1.5 w-1.5 rounded-full bg-fg/20"} />
          ))}
        </div>
        {step.href ? (
          <button type="button" className="t-sub font-medium text-fg underline-offset-4 hover:underline" onClick={() => void finish(step.href)}>
            {step.cta}
          </button>
        ) : null}
      </div>
    </Sheet>
  );
}
