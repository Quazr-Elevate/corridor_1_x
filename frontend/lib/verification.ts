// The seven mandatory profile fields that gate the Verified badge.
//
// Mirrors ``backend/app/verification.py`` — the backend sends the camelCase
// keys over the wire (via ``Me.verification.missing``), the frontend owns
// the human-readable labels and the deep-link routes. The two must stay in
// lockstep: if you add a field here, add it in Python too, and vice versa.
//
// Order matters — the progress card uses the first missing entry as its
// "Finish →" target, so the quickest wins (name, position) are up top.

export type MandatorySection = "profile" | "company" | "business";

export interface MandatoryField {
  key: string;
  label: string;
  section: MandatorySection;
  // URL fragment on /dashboard/account that scrolls this field into view.
  anchor: string;
  // Which account-page tab the field lives on. Deep-link format matches
  // the account page's existing `?tab=&doc=` convention.
  tab: "primary" | "company" | "business";
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

export function fieldByKey(key: string): MandatoryField | undefined {
  return MANDATORY_FIELDS.find((f) => f.key === key);
}

/**
 * Build the deep-link to the first missing field (or the primary tab if
 * all fields are filled). Used by the progress card's "Finish →" CTA.
 */
export function nextStepHref(missing: readonly string[]): string {
  if (missing.length === 0) return "/dashboard/account?tab=primary";
  const first = fieldByKey(missing[0]);
  if (!first) return "/dashboard/account?tab=primary";
  return `/dashboard/account?tab=${first.tab}#${first.anchor}`;
}
