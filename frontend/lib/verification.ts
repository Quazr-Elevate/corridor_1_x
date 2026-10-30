// What a business still needs before it can send its profile for KYB.
//
// The server reports it as ordered keys (``me.verification.missing``) with
// matching labels (``missingLabels``):
//   * profile fields — legalName, addressLine, city, country
//   * mandatory documents of the business's country — ``kyb:<code>``
//     (``kyb:gstin``), defined by admins per country.
// The frontend owns the deep links into the Business profile page
// (/dashboard/business). Order matters: the first entry is "the next step".

import type { VerificationState, VerificationStatus } from "./api";

export type MandatorySection = "profile" | "company" | "business" | "documents";

/** Section ids on the older Passport page (``section-<id>``). */
export type AccountSection = "primary" | "company" | "business" | "certifications";

export interface MandatoryField {
  key: string;
  label: string;
  section: MandatorySection;
  /** Element id on /dashboard/business — `#<anchor>` scrolls to + focuses it. */
  anchor: string;
  /** Passport section that holds the field (older Passport page). */
  tab: Exclude<AccountSection, "certifications">;
}

/** The profile fields that gate KYB submission (documents come from the server). */
export const MANDATORY_FIELDS: readonly MandatoryField[] = [
  { key: "legalName",   label: "Company name",       section: "company", tab: "company", anchor: "legal-name" },
  { key: "addressLine", label: "Registered address", section: "company", tab: "company", anchor: "address-line" },
  { key: "city",        label: "City",               section: "company", tab: "company", anchor: "city" },
  { key: "country",     label: "Country",            section: "company", tab: "company", anchor: "country" },
];

export const MANDATORY_KEYS = new Set(MANDATORY_FIELDS.map((f) => f.key));

/** The Business profile page — company, branding and KYB documents. */
export const PASSPORT_PATH = "/dashboard/business";
/** The older, longer Passport page (trade profile, contact details). */
export const DETAILS_PATH = "/dashboard/account";

const KYB_PREFIX = "kyb:";

export function isDocumentKey(key: string): boolean {
  return key.startsWith(KYB_PREFIX);
}

/** Field (or document requirement) for a server key; ``label`` overrides. */
export function fieldByKey(key: string, label?: string): MandatoryField | undefined {
  const known = MANDATORY_FIELDS.find((f) => f.key === key);
  if (known) return label ? { ...known, label } : known;
  if (isDocumentKey(key)) {
    const code = key.slice(KYB_PREFIX.length);
    return {
      key,
      label: label ?? code.replace(/_/g, " ").toUpperCase(),
      section: "documents",
      tab: "company",
      anchor: `kyb-${code}`,
    };
  }
  return undefined;
}

/** Everything still missing, labelled with the server's labels. */
export function missingItems(v: VerificationState): MandatoryField[] {
  return v.missing
    .map((key, i) => fieldByKey(key, v.missingLabels?.[i]))
    .filter((f): f is MandatoryField => Boolean(f));
}

/** The next thing to do, or undefined when nothing is missing. */
export function nextMissing(v: VerificationState): MandatoryField | undefined {
  return missingItems(v)[0];
}

/** Deep link that scrolls to + focuses one field on the Business profile. */
export function fieldHref(field: MandatoryField): string {
  return `${PASSPORT_PATH}#${field.anchor}`;
}

/** Deep link to the first missing item, or the Business profile when complete. */
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
