/**
 * Display helpers for the trader surface (Corridor home, Passport).
 * Server-safe. The backend serialises Decimals as strings ("500.00"),
 * so number helpers accept string | number | null.
 */
import { priceFigure } from "@/components/products/format";
import type { Me } from "@/lib/api";

type Num = string | number | null | undefined;

function toNumber(v: Num): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

const fmt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

/** "500 MT" · null when unknown. */
export function qty(v: Num, unit: string): string | null {
  const n = toNumber(v);
  return n === null ? null : `${fmt.format(n)} ${unit}`;
}

/** "₹42,000/MT" · "AED 520/MT" · "On request" when unpriced. */
export function price(v: Num, unit: string, currency?: string | null): string {
  return priceFigure(v, unit, currency);
}

/** Short listing code, same shape as the Listings page: L-1A2B3C. */
export function lotCode(id: string): string {
  return `L-${id.replace(/-/g, "").slice(0, 6).toUpperCase()}`;
}

/** Short member code from the account id: C1X-175A12. */
export function memberCode(userId: string): string {
  return `C1X-${userId.replace(/-/g, "").slice(0, 6).toUpperCase()}`;
}

/** Join the non-empty parts with a middot. */
export function dot(...parts: Array<string | null | undefined | false>): string {
  return parts.filter(Boolean).join(" · ");
}

/** What the trader does on Corridor, from the business profile. */
export function roleLabel(me: Me): string {
  switch (me.business.tradePosition) {
    case "seller":
      return "Seller";
    case "buyer":
      return "Buyer";
    case "both":
      return "Seller & buyer";
    default:
      return me.userType === "seller" ? "Seller" : "Buyer";
  }
}

/** "Ahmedabad, Gujarat" — empty when neither is set. */
export function placeLine(me: Me): string {
  return [me.business.city, me.business.state].filter(Boolean).join(", ");
}

/** "member since Oct 2026" — empty when unknown. */
export function memberSince(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `member since ${d.toLocaleDateString(undefined, { month: "short", year: "numeric" })}`;
}

/** Two-letter initials for the avatar. */
export function initials(me: Me): string {
  const name = me.primary.fullName || me.email;
  const parts = name.split(/[\s@.]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "C";
}
