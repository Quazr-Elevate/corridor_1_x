import type { IconName } from "@/components/ui/Icon";

/**
 * Display helpers shared by the market and the Listings page.
 * The backend serialises Decimals as strings ("500.00"), so everything
 * here accepts string | number | null.
 */

type Num = string | number | null | undefined;

function toNumber(v: Num): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

const fmt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

/** "500 MT" · null when unknown. */
export function formatQty(v: Num, unit: string): string | null {
  const n = toNumber(v);
  return n === null ? null : `${fmt.format(n)} ${unit}`;
}

/** Currencies a seller can price a listing in (backend: ISO 4217, default INR). */
export const LISTING_CURRENCIES = ["INR", "AED", "USD"] as const;
export type ListingCurrency = (typeof LISTING_CURRENCIES)[number];

const moneyFmts = new Map<string, Intl.NumberFormat>();

/** "₹42,000" · "AED 520" · "$480" — Intl-formatted in the listing's currency. */
export function formatMoney(n: number, currency: string | null | undefined = "INR"): string {
  const code = (currency || "INR").toUpperCase();
  let f = moneyFmts.get(code);
  if (!f) {
    try {
      f = new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: code,
        currencyDisplay: "narrowSymbol",
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      });
    } catch {
      // Unknown code — fall back to "XYZ 1,234".
      return `${code} ${fmt.format(n)}`;
    }
    moneyFmts.set(code, f);
  }
  return f.format(n);
}

/** "₹" · "AED" · "$" — the currency's display mark, for input adornments. */
export function currencySymbol(currency: string | null | undefined = "INR"): string {
  const parts = new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: (currency || "INR").toUpperCase(),
    currencyDisplay: "narrowSymbol",
  }).formatToParts(0);
  return parts.find((x) => x.type === "currency")?.value ?? (currency || "INR");
}

/** "₹42,000 / MT" · "AED 520 / MT" · "On request" when unpriced. */
export function formatPrice(v: Num, unit: string, currency?: string | null): string {
  const n = toNumber(v);
  return n === null ? "On request" : `${formatMoney(n, currency)} / ${unit}`;
}

/** "₹72/MT" · "$480/MT" · "On request" — compact, for the large card figures. */
export function priceFigure(v: Num, unit: string, currency?: string | null): string {
  const n = toNumber(v);
  return n === null ? "On request" : `${formatMoney(n, currency)}/${unit}`;
}

// ── Indicative conversions ───────────────────────────────────────────
// A listing's price is always shown as the seller entered it. When the
// viewer's display currency differs, an indicative conversion follows:
// "AED 520 / MT · ≈ ₹13,451" (rate date on hover).

/** USD-based rates: 1 USD = rates[code] × code (GET /public/fx/rates). */
export interface FxRatesLike {
  asOf: string | null;
  rates: Record<string, number>;
}

/** `n` in `from` → `to`, or null when either rate is unknown. */
export function convertAmount(n: number, from: string, to: string, fx: FxRatesLike | null): number | null {
  if (!fx) return null;
  const a = fx.rates[from.toUpperCase()];
  const b = fx.rates[to.toUpperCase()];
  if (!a || !b) return null;
  return (n / a) * b;
}

/** Whole units from 10 up ("₹13,451", "AED 20"), cents below ("$1.42"). */
export function formatApproxMoney(n: number, currency: string): string {
  const rounded = n >= 10 ? Math.round(n) : Math.round(n * 100) / 100;
  return formatMoney(rounded, currency);
}

/** "17 Oct 2026" from "2026-10-17". */
export function rateDateLabel(asOf: string | null | undefined): string | null {
  if (!asOf) return null;
  const d = new Date(`${asOf}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return asOf;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

export interface Approx {
  /** "≈ ₹13,451" */
  text: string;
  /** "Indicative, rate of 17 Oct 2026" — for the title tooltip. */
  title: string;
}

/**
 * The indicative conversion of a listing price into the viewer's display
 * currency — null when unpriced, when the currencies match, or when a rate
 * is missing.
 */
export function approxPrice(
  v: Num,
  currency: string | null | undefined,
  displayCurrency: string | null | undefined,
  fx: FxRatesLike | null,
): Approx | null {
  const n = toNumber(v);
  const from = (currency || "INR").toUpperCase();
  const to = (displayCurrency || "").toUpperCase();
  if (n === null || !to || from === to) return null;
  const converted = convertAmount(n, from, to, fx);
  if (converted === null) return null;
  const date = rateDateLabel(fx?.asOf);
  return {
    text: `≈ ${formatApproxMoney(converted, to)}`,
    title: date ? `Indicative, rate of ${date}` : "Indicative",
  };
}

/** "AED 520 / MT · ≈ ₹13,451" — the price, plus the conversion when it applies. */
export function withApprox(price: string, approx: Approx | null): string {
  return approx ? `${price} · ${approx.text}` : price;
}

/** Short, human-readable listing code: L-1A2B3C. */
export function listingCode(id: string): string {
  return `L-${id.replace(/-/g, "").slice(0, 6).toUpperCase()}`;
}

/** "jute packing", "PP woven packing", "HDPE packing", "bulk" — for origin lines. */
export function packingLabel(packaging: string | null | undefined): string | null {
  if (!packaging) return null;
  const p = packaging.trim();
  if (/^bulk$/i.test(p)) return "bulk";
  // Keep acronyms (PP, HDPE) as written; lower-case plain words.
  const words = p.split(/\s+/).map((w) => (/^[A-Z]{2,}$/.test(w) ? w : w.toLowerCase()));
  return `${words.join(" ")} packing`;
}

/** Join the non-empty parts with a middot. */
export function joinDot(...parts: Array<string | null | undefined>): string {
  return parts.filter(Boolean).join(" · ");
}

/** Drawn glyph per commodity for photo-less tiles. */
export function commodityIcon(category: string | null | undefined): IconName {
  switch ((category || "").toLowerCase()) {
    case "sugar":
    case "pulses":
    case "spices":
    case "cotton":
      return "sack";
    default:
      return "grain";
  }
}
