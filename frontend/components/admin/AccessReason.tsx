"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";

export const ACCESS_REASON_MIN = 5;
export const ACCESS_REASON_MAX = 500;

const QUICK_REASONS = [
  "KYB review of this business",
  "Re-check after a rejected document",
  "Support request from the business",
  "Compliance or audit check",
] as const;

/** Thrown by `ask()` when the admin closes the sheet without a reason. */
export class AccessReasonCancelled extends Error {
  constructor() {
    super("No reason given.");
  }
}

interface AccessReasonApi {
  /** The reason for this scope: remembered, or asked for once. */
  ask: (scope: string) => Promise<string>;
  /** The remembered reason, if the admin already gave one for this scope. */
  known: (scope: string) => string | null;
  /** Reuse a reason the admin already gave for another scope of the same business. */
  remember: (scope: string, reason: string) => void;
}

const ReasonContext = createContext<AccessReasonApi | null>(null);
const ScopeContext = createContext<string>("console");

interface Waiting {
  scope: string;
  resolve: (reason: string) => void;
  reject: (error: Error) => void;
}

/**
 * Opening a KYB file or showing a full number needs a stated reason; the API
 * stores it on the audit row. The console asks once per scope (a business)
 * and reuses the answer until the admin leaves the console pages.
 */
export function AccessReasonProvider({ children }: { children: ReactNode }) {
  const reasons = useRef(new Map<string, string>());
  const [waiting, setWaiting] = useState<Waiting | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  const api = useMemo<AccessReasonApi>(
    () => ({
      known: (scope) => reasons.current.get(scope) ?? null,
      remember: (scope, reason) => {
        reasons.current.set(scope, reason);
      },
      ask: (scope) => {
        const have = reasons.current.get(scope);
        if (have) return Promise.resolve(have);
        return new Promise<string>((resolve, reject) => {
          setDraft("");
          setError(null);
          setWaiting((cur) => {
            // A second control asked while the sheet was open: the first one gives up.
            cur?.reject(new AccessReasonCancelled());
            return { scope, resolve, reject };
          });
        });
      },
    }),
    [],
  );

  const cancel = useCallback(() => {
    setWaiting((cur) => {
      cur?.reject(new AccessReasonCancelled());
      return null;
    });
  }, []);

  const confirm = () => {
    const reason = draft.trim();
    if (reason.length < ACCESS_REASON_MIN) {
      setError("Say briefly why you need to see this.");
      return;
    }
    if (!waiting) return;
    reasons.current.set(waiting.scope, reason);
    waiting.resolve(reason);
    setWaiting(null);
  };

  return (
    <ReasonContext.Provider value={api}>
      {children}
      <Sheet
        open={waiting !== null}
        onClose={cancel}
        size="sm"
        title="Why do you need this?"
        description="Full numbers and files are sensitive. Your reason is saved in the audit log with your name."
        footer={
          <>
            <Button variant="quiet" onClick={cancel}>
              Cancel
            </Button>
            <Button onClick={confirm} disabled={draft.trim().length < ACCESS_REASON_MIN}>
              Continue
            </Button>
          </>
        }
      >
        <Textarea
          label="Reason"
          required
          counter
          maxLength={ACCESS_REASON_MAX}
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            if (error) setError(null);
          }}
          placeholder="For example: KYB review of this business"
          error={error}
          hint="Asked once per business while you stay in the console."
        />
        <div className="mt-5">
          <p className="t-label text-fg-3">Quick picks</p>
          <div className="mt-2.5 flex flex-wrap gap-2">
            {QUICK_REASONS.map((q) => {
              const on = draft === q;
              return (
                <button
                  key={q}
                  type="button"
                  aria-pressed={on}
                  onClick={() => {
                    setDraft(q);
                    setError(null);
                  }}
                  className={cn(
                    "rounded-[14px] px-3 py-2 text-left text-[13px] leading-snug transition-[box-shadow,color] duration-300 ease-expo",
                    on ? "solid" : "relief-sm text-fg-2 hover:text-fg",
                  )}
                >
                  {q}
                </button>
              );
            })}
          </div>
        </div>
      </Sheet>
    </ReasonContext.Provider>
  );
}

/** Marks everything inside as belonging to one business, so one reason covers it. */
export function AccessScope({ id, children }: { id: string; children: ReactNode }) {
  return <ScopeContext.Provider value={id}>{children}</ScopeContext.Provider>;
}

/** ``scope`` overrides the surrounding AccessScope, for code above it (a page opening an account). */
export function useAccessReason(scope?: string): {
  ask: () => Promise<string>;
  known: () => string | null;
  remember: (otherScope: string, reason: string) => void;
} {
  const api = useContext(ReasonContext);
  const inherited = useContext(ScopeContext);
  if (!api) throw new Error("useAccessReason needs an AccessReasonProvider above it.");
  const which = scope ?? inherited;
  return useMemo(
    () => ({ ask: () => api.ask(which), known: () => api.known(which), remember: api.remember }),
    [api, which],
  );
}
