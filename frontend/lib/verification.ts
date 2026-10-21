// The seven mandatory profile fields that gate the Verified badge.
//
// Mirrors the backend's MANDATORY_FIELDS — the server sends camelCase keys
// over the wire (``me.verification.missing``, in this order); the frontend
// owns the human-readable labels and the deep-link anchors on the Passport
// page (/dashboard/account). Keep the two in lockstep.
//
// Order matters: the first missing entry is always "the next field".

import type { VerificationState, VerificationStatus } from "./api";

export type MandatorySection = "profile" | "company" | "business";

/** Section ids on the Passport page (``section-<id>``). */
export type AccountSection = "primary" | "company" | "business" | "certifications";

export interface MandatoryField {
  key: string;
  label: string;
  section: MandatorySection;
  /** Element id on /dashboard/account — `#<anchor>` scrolls to + focuses it. */
  anchor: string;
  /** Passport section that holds the field. */
  tab: Exclude<AccountSection, "certifications">;
}

export const MANDATORY_FIELDS: readonly MandatoryField[] = [
  { key: "fullName",           label: "Full name",           section: "profile",  tab: "primary",  anchor: "full-name" },
  { key: "position",           label: "Position / role",     section: "profile",  tab: "primary",  anchor: "position" },
  { key: "phone",              label: "Phone number",        section: "profile",  tab: "primary",  anchor: "phone" },
  { key: "legalName",          label: "Legal company name",  section: "company",  tab: "company",  anchor: "legal-name" },
  { key: "industry",           label: "Industry",            section: "company",  tab: "company",  anchor: "industry" },
  { key: "operatingCountries", label: "Operating countries", section: "company",  tab: "company",  anchor: "operating-countries" },
  { key: "tradePosition",      label: "Trade position",      section: "business", tab: "business", anchor: "trade-position" },
];

export const MANDATORY_KEYS = new Set(MANDATORY_FIELDS.map((f) => f.key));

export const PASSPORT_PATH = "/dashboard/account";

export function fieldByKey(key: string): MandatoryField | undefined {
  return MANDATORY_FIELDS.find((f) => f.key === key);
}

/** Deep link that scrolls to + focuses one field on the Passport page. */
export function fieldHref(field: MandatoryField): string {
  return `${PASSPORT_PATH}#${field.anchor}`;
}

/** Deep link to the first missing field, or the Passport page when complete. */
export function nextStepHref(missing: readonly string[]): string {
  const first = missing.length ? fieldByKey(missing[0]) : undefined;
  return first ? fieldHref(first) : PASSPORT_PATH;
}

/** Mandatory fields in one Passport section, with how many are filled. */
export function sectionProgress(
  tab: MandatoryField["tab"],
  missing: readonly string[],
): { filled: number; total: number } {
  const fields = MANDATORY_FIELDS.filter((f) => f.tab === tab);
  return { filled: fields.filter((f) => !missing.includes(f.key)).length, total: fields.length };
}

export function verificationCounts(v: VerificationState): { filled: number; total: number } {
  const total = v.mandatoryTotal || MANDATORY_FIELDS.length;
  return { filled: Math.max(0, total - v.missing.length), total };
}

/** Statuses from which the user can (re)send their profile for review. */
const SUBMITTABLE: ReadonlySet<VerificationStatus> = new Set(["draft", "rejected"]);

export function canSubmit(v: VerificationState): boolean {
  return v.missing.length === 0 && SUBMITTABLE.has(v.status);
}

/** Short status copy + chip tone, shared by the Corridor home and Passport. */
export function statusMeta(status: VerificationStatus): {
  label: string;
  tone: "verified" | "move" | "frozen" | "neutral";
} {
  switch (status) {
    case "verified":
      return { label: "Verified", tone: "verified" };
    case "pending_verification":
      return { label: "In review", tone: "move" };
    case "rejected":
      return { label: "Needs changes", tone: "frozen" };
    default:
      return { label: "Not yet sent", tone: "neutral" };
  }
}

/** "15 Oct 2026" — empty string when the value is missing or unparseable. */
export function formatDay(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
