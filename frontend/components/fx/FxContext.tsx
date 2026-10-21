"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { approxPrice, type FxRatesLike } from "@/components/products/format";
import { cn } from "@/lib/cn";
import { publicApi, type FxRates } from "@/lib/publicApi";
import { useMe } from "@/lib/useMe";

/** Currencies a viewer can see prices / type filters in (backend FX_SUPPORTED_CURRENCIES). */
export const DISPLAY_CURRENCIES = ["INR", "AED", "USD"] as const;
export type DisplayCurrency = (typeof DISPLAY_CURRENCIES)[number];

export function isDisplayCurrency(v: string | null | undefined): v is DisplayCurrency {
  return !!v && (DISPLAY_CURRENCIES as readonly string[]).includes(v.toUpperCase());
}

// One request per page load, shared by every card / filter / detail view.
// The backend only reads its table (rates refresh daily), so no polling.
let ratesPromise: Promise<FxRates | null> | null = null;

function loadRates(): Promise<FxRates | null> {
  if (!ratesPromise) {
    ratesPromise = publicApi.fxRates().catch(() => {
      ratesPromise = null; // retry on the next mount
      return null;
    });
  }
  return ratesPromise;
}

interface FxValue {
  /** Latest USD rates, null until loaded (or when unavailable). */
  rates: FxRatesLike | null;
  /** The viewer's currency: their saved choice, else the guest pick (URL), else USD. */
  displayCurrency: DisplayCurrency;
  /** False while the session is still loading — hold conversions until then. */
  ready: boolean;
  signedIn: boolean;
  /** Signed-out viewers pick a currency in the market filters (kept in the URL). */
  setGuestCurrency: (c: string | null | undefined) => void;
}

const FxContext = createContext<FxValue>({
  rates: null,
  displayCurrency: "USD",
  ready: false,
  signedIn: false,
  setGuestCurrency: () => {},
});

export function FxProvider({ children }: { children: ReactNode }) {
  const { me, loading } = useMe();
  const [rates, setRates] = useState<FxRates | null>(null);
  const [guest, setGuest] = useState<DisplayCurrency>("USD");

  useEffect(() => {
    let alive = true;
    void loadRates().then((r) => {
      if (alive) setRates(r);
    });
    return () => {
      alive = false;
    };
  }, []);

  const value = useMemo<FxValue>(() => {
    const saved = me?.displayCurrency?.toUpperCase();
    return {
      rates,
      displayCurrency: me ? (isDisplayCurrency(saved) ? saved : "USD") : guest,
      ready: !loading,
      signedIn: !!me,
      setGuestCurrency: (c) => setGuest(isDisplayCurrency(c) ? (c.toUpperCase() as DisplayCurrency) : "USD"),
    };
  }, [me, loading, rates, guest]);

  return <FxContext.Provider value={value}>{children}</FxContext.Provider>;
}

export function useFx(): FxValue {
  return useContext(FxContext);
}

/**
 * The indicative conversion of a listing price into the viewer's display
 * currency, or nothing when they match / rates are missing.
 *   inline → " · ≈ ₹13,451" (follows the price on the same line)
 *   line   → "≈ ₹13,451" on its own small line (cards)
 */
export function ApproxPrice({
  amount,
  currency,
  variant = "inline",
  className,
}: {
  amount: string | number | null | undefined;
  currency: string | null | undefined;
  variant?: "inline" | "line";
  className?: string;
}) {
  const { rates, displayCurrency, ready } = useFx();
  const approx = ready ? approxPrice(amount, currency, displayCurrency, rates) : null;
  if (!approx) return null;
  if (variant === "line") {
    return (
      <span title={approx.title} className={cn("t-foot tabular mt-0.5 block truncate text-fg-3", className)}>
        {approx.text}
      </span>
    );
  }
  return (
    <span title={approx.title} className={cn("font-normal text-fg-3", className)}>
      {" · "}
      {approx.text}
    </span>
  );
}
