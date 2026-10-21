/**
 * Countries offered on the Passport (operating countries, target markets,
 * phone dial codes). The API stores ISO-3166 alpha-2 codes; names are for
 * display only. Ordered with the most common Corridor markets first.
 */
export interface Country {
  code: string;
  name: string;
  dial: string;
  flag: string;
}

export const COUNTRIES: readonly Country[] = [
  { code: "IN", name: "India", dial: "+91", flag: "🇮🇳" },
  { code: "AE", name: "United Arab Emirates", dial: "+971", flag: "🇦🇪" },
  { code: "SA", name: "Saudi Arabia", dial: "+966", flag: "🇸🇦" },
  { code: "OM", name: "Oman", dial: "+968", flag: "🇴🇲" },
  { code: "QA", name: "Qatar", dial: "+974", flag: "🇶🇦" },
  { code: "KW", name: "Kuwait", dial: "+965", flag: "🇰🇼" },
  { code: "BH", name: "Bahrain", dial: "+973", flag: "🇧🇭" },
  { code: "US", name: "United States", dial: "+1", flag: "🇺🇸" },
  { code: "GB", name: "United Kingdom", dial: "+44", flag: "🇬🇧" },
  { code: "DE", name: "Germany", dial: "+49", flag: "🇩🇪" },
  { code: "NL", name: "Netherlands", dial: "+31", flag: "🇳🇱" },
  { code: "SG", name: "Singapore", dial: "+65", flag: "🇸🇬" },
  { code: "MY", name: "Malaysia", dial: "+60", flag: "🇲🇾" },
  { code: "ID", name: "Indonesia", dial: "+62", flag: "🇮🇩" },
  { code: "TH", name: "Thailand", dial: "+66", flag: "🇹🇭" },
  { code: "VN", name: "Vietnam", dial: "+84", flag: "🇻🇳" },
  { code: "JP", name: "Japan", dial: "+81", flag: "🇯🇵" },
  { code: "CN", name: "China", dial: "+86", flag: "🇨🇳" },
  { code: "KR", name: "South Korea", dial: "+82", flag: "🇰🇷" },
  { code: "AU", name: "Australia", dial: "+61", flag: "🇦🇺" },
];

const BY_CODE = new Map(COUNTRIES.map((c) => [c.code, c]));
const BY_NAME = new Map(COUNTRIES.map((c) => [c.name.toLowerCase(), c]));

/** Display name for an ISO code (falls back to the raw value). */
export function countryName(value: string | null | undefined): string {
  if (!value) return "";
  return BY_CODE.get(value.toUpperCase())?.name ?? BY_NAME.get(value.toLowerCase())?.name ?? value;
}

/**
 * Normalise stored values to ISO codes. Older rows hold country names
 * ("India", "INDIA"); map them back to codes and drop anything the API
 * would reject (> 3 characters and not a known name).
 */
export function toCountryCodes(values: readonly string[] | null | undefined): string[] {
  const out: string[] = [];
  for (const raw of values ?? []) {
    const v = raw.trim();
    if (!v) continue;
    const code = BY_CODE.get(v.toUpperCase())?.code ?? BY_NAME.get(v.toLowerCase())?.code ?? (v.length <= 3 ? v.toUpperCase() : null);
    if (code && !out.includes(code)) out.push(code);
  }
  return out;
}

/** Split a stored phone ("+91 98765 43210") into dial code + local number. */
export function parsePhone(raw: string | null | undefined): { dial: string; rest: string } {
  if (!raw) return { dial: "+91", rest: "" };
  const trimmed = raw.trim();
  // Longest dial code wins so "+971" beats "+9…".
  const sorted = [...COUNTRIES].sort((a, b) => b.dial.length - a.dial.length);
  for (const c of sorted) {
    if (trimmed.startsWith(c.dial)) return { dial: c.dial, rest: trimmed.slice(c.dial.length).trim() };
  }
  return { dial: "+91", rest: trimmed };
}

/** Unique dial codes for the phone picker (first country per code wins). */
export const DIAL_OPTIONS: ReadonlyArray<{ value: string; label: string }> = COUNTRIES.filter(
  (c, i, all) => all.findIndex((x) => x.dial === c.dial) === i,
).map((c) => ({ value: c.dial, label: `${c.flag} ${c.dial}` }));
