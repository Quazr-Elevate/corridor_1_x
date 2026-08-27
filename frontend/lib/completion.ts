import type { Me } from "./api";

export type ProfileSection = "primary" | "business" | "bank";

export interface ProfileStep {
  section: ProfileSection;
  /** DOM id of the input to focus */
  field: string;
  /** Deep-link URL that jumps straight to the field */
  href: string;
}

interface StepDef {
  section: ProfileSection;
  field: string;
  base: string;
  filled: (me: Me) => boolean;
}

/**
 * Ordered list of the fields that count toward "profile completion".
 * Order defines Continue-button priority: earlier steps are visited first.
 * Kept in sync with the backend's `_primary_complete` / `_business_complete`
 * / `_bank_complete` checks in app/routers/me.py.
 */
const STEPS: StepDef[] = [
  {
    section: "primary",
    field: "f-full-name",
    base: "/dashboard/profile/primary",
    filled: (m) => !!m.primary.fullName?.trim(),
  },
  {
    section: "primary",
    field: "f-email-address",
    base: "/dashboard/profile/primary",
    filled: (m) => !!m.primary.email?.trim(),
  },
  {
    section: "primary",
    field: "f-state",
    base: "/dashboard/profile/primary",
    filled: (m) => !!m.primary.state?.trim(),
  },
  {
    section: "primary",
    field: "f-pincode",
    base: "/dashboard/profile/primary",
    filled: (m) => !!m.primary.pincode?.trim(),
  },
  {
    section: "primary",
    field: "f-city",
    base: "/dashboard/profile/primary",
    filled: (m) => !!m.primary.city?.trim(),
  },
  {
    section: "primary",
    field: "f-address",
    base: "/dashboard/profile/primary",
    filled: (m) => !!m.primary.addressLine?.trim(),
  },
  {
    section: "business",
    field: "f-pan",
    base: "/dashboard/profile/business",
    filled: (m) => !!m.business.pan?.trim(),
  },
  {
    section: "business",
    field: "f-company-name",
    base: "/dashboard/profile/business",
    filled: (m) => !!m.business.companyName?.trim(),
  },
  {
    section: "bank",
    field: "f-account-number",
    base: "/dashboard/profile/bank",
    filled: (m) => !!m.bank.accountNumber?.trim(),
  },
  {
    section: "bank",
    field: "f-ifsc",
    base: "/dashboard/profile/bank",
    filled: (m) => !!m.bank.ifsc?.trim(),
  },
  {
    section: "bank",
    field: "f-account-holder-name",
    base: "/dashboard/profile/bank",
    filled: (m) => !!m.bank.holderName?.trim(),
  },
];

export function nextIncompleteStep(me: Me | null): ProfileStep | null {
  if (!me) return null;
  for (const s of STEPS) {
    if (!s.filled(me)) {
      return {
        section: s.section,
        field: s.field,
        href: `${s.base}?focus=${s.field}`,
      };
    }
  }
  return null;
}

export function completionStats(me: Me | null): {
  filled: number;
  total: number;
  pct: number;
} {
  const total = STEPS.length;
  if (!me) return { filled: 0, total, pct: 0 };
  const filled = STEPS.filter((s) => s.filled(me)).length;
  return { filled, total, pct: Math.round((filled / total) * 100) };
}
