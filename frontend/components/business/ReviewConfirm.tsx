"use client";

import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Sheet } from "@/components/ui/Sheet";

type Ask = (what: string) => Promise<boolean>;

const Ctx = createContext<Ask>(async () => true);

/**
 * A verified business changing something KYB checked (company name,
 * address, country, a required document) goes back to review — and its
 * listings leave the market until Corridor ops re-approves. Ask first.
 *
 * `const confirmReview = useReviewConfirm(); if (!(await confirmReview("your GSTIN"))) return;`
 */
export function ReviewConfirmProvider({ verified, children }: { verified: boolean; children: ReactNode }) {
  const [what, setWhat] = useState<string | null>(null);
  const resolver = useRef<((ok: boolean) => void) | null>(null);

  const ask = useCallback<Ask>(
    (w) => {
      if (!verified) return Promise.resolve(true);
      setWhat(w);
      return new Promise<boolean>((resolve) => {
        resolver.current = resolve;
      });
    },
    [verified],
  );

  const close = (ok: boolean) => {
    resolver.current?.(ok);
    resolver.current = null;
    setWhat(null);
  };

  return (
    <Ctx.Provider value={ask}>
      {children}
      <Sheet
        open={what !== null}
        onClose={() => close(false)}
        size="sm"
        title="Send your business back for review?"
        description={`Changing ${what ?? "this"} means Corridor ops checks your business again.`}
        footer={
          <>
            <Button variant="quiet" onClick={() => close(false)}>
              Cancel
            </Button>
            <Button onClick={() => close(true)}>Save and re-review</Button>
          </>
        }
      >
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-full bg-amber-soft text-amber">
            <Icon name="alert" size={18} />
          </span>
          <p className="t-callout text-fg-2">
            Your Verified badge is paused and your lots leave the market until Corridor ops approves the change —
            usually within a day.
          </p>
        </div>
      </Sheet>
    </Ctx.Provider>
  );
}

export function useReviewConfirm(): Ask {
  return useContext(Ctx);
}
