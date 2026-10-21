/** Formatting helpers for the Control Tower. Pure, no React. */

const HOUR = 3_600_000;
const DAY = 24 * HOUR;

/** KYB review target, from submission. */
export const SLA_MS = 24 * HOUR;

export function parseDate(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function fmtDate(iso: string | null | undefined): string {
  const d = parseDate(iso);
  return d ? d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "—";
}

export function fmtDateTime(iso: string | null | undefined): string {
  const d = parseDate(iso);
  return d
    ? d.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
    : "—";
}

/** "40 min", "6 hours", "3 days" — always positive. */
export function fmtSpan(ms: number): string {
  const abs = Math.abs(ms);
  if (abs < HOUR) {
    const m = Math.max(1, Math.round(abs / 60_000));
    return `${m} min`;
  }
  if (abs < 2 * DAY) {
    const h = Math.round(abs / HOUR);
    return `${h} hour${h === 1 ? "" : "s"}`;
  }
  const d = Math.round(abs / DAY);
  return `${d} days`;
}

/** "3 hours ago" / "just now". */
export function fmtAgo(iso: string | null | undefined, now = Date.now()): string {
  const d = parseDate(iso);
  if (!d) return "—";
  const ms = now - d.getTime();
  if (ms < 60_000) return "just now";
  return `${fmtSpan(ms)} ago`;
}

/** SLA state for something submitted at `iso`. */
export function dueState(iso: string | null | undefined, now = Date.now()) {
  const d = parseDate(iso);
  if (!d) return { over: false, label: "not submitted" };
  const left = d.getTime() + SLA_MS - now;
  return left < 0
    ? { over: true, label: `${fmtSpan(left)} over` }
    : { over: false, label: `due in ${fmtSpan(left)}` };
}

export function fmtBytes(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return "0 KB";
  if (n < 1024 * 1024) return `${Math.max(1, Math.round(n / 1024))} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

/** "KYB-3F9A" style operator-facing reference. */
export function refId(prefix: string, id: string): string {
  return `${prefix}-${id.replace(/-/g, "").slice(0, 4).toUpperCase()}`;
}

const TRADE: Record<string, string> = {
  buyer: "Buyer",
  seller: "Seller",
  both: "Buyer & seller",
};

export function tradeLabel(v: string | null | undefined): string | null {
  if (!v) return null;
  return TRADE[v] ?? v.charAt(0).toUpperCase() + v.slice(1);
}

/** "ruban.k@x.com" → "Ruban". */
export function nameFromEmail(email: string | null | undefined): string {
  if (!email) return "there";
  const local = email.split("@")[0]?.split(/[._+\-\d]/).find(Boolean) ?? "";
  if (!local) return "there";
  return local.charAt(0).toUpperCase() + local.slice(1).toLowerCase();
}

export function greeting(d = new Date()): string {
  const h = d.getHours();
  if (h < 5) return "Good evening";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** Display value for an unknown profile field. */
export function displayValue(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (Array.isArray(v)) return v.filter(Boolean).join(", ");
  return String(v);
}
