// ── Shared response shapes ─────────────────────────────────────────────

export type EntityType = "proprietorship" | "partnership" | "llp" | "private_ltd" | "public_ltd";

export const ENTITY_TYPE_LABELS: Record<EntityType, string> = {
  proprietorship: "Sole proprietorship",
  partnership: "Partnership",
  llp: "Limited liability partnership",
  private_ltd: "Private limited company",
  public_ltd: "Public limited company",
};

/** Compact labels for pickers and the Passport card. */
export const ENTITY_TYPE_SHORT: Record<EntityType, string> = {
  proprietorship: "Proprietorship",
  partnership: "Partnership",
  llp: "LLP",
  private_ltd: "Private Ltd",
  public_ltd: "Public Ltd",
};

/** "private_ltd" → "Private Ltd"; unknown values pass through. */
export function entityTypeShort(value: string | null | undefined): string {
  if (!value) return "";
  return ENTITY_TYPE_SHORT[value as EntityType] ?? value;
}

/** "private_ltd" → "Private limited company"; unknown values pass through. */
export function entityTypeLabel(value: string | null | undefined): string {
  if (!value) return "";
  return ENTITY_TYPE_LABELS[value as EntityType] ?? value;
}

/** Person fields — live on the user. */
export interface PrimaryData {
  fullName?: string | null;
  phone?: string | null;
  position?: string | null;
}

/** Business fields — the business is the main entity. */
export interface BusinessData {
  // Company info
  legalName?: string | null;
  entityType?: EntityType | null;
  industry?: string | null;
  operatingCountries?: string[] | null;
  websiteUrl?: string | null;
  // Company address (country is ISO alpha-2, defaults to "IN")
  addressLine?: string | null;
  city?: string | null;
  state?: string | null;
  pincode?: string | null;
  country?: string | null;
  // Socials
  googleBusinessUrl?: string | null;
  facebookUrl?: string | null;
  // Business profile
  tradePosition?: string | null;
  sellerType?: string | null;
  exportStatus?: string | null;
  targetMarkets?: string[] | null;
  targetBuyerTypes?: string[] | null;
  companyIntroduction?: string | null;
}

// Mirrors the server's business verification status. "draft" covers
// everything before the business is sent for review.
export type VerificationStatus = "draft" | "pending_verification" | "verified" | "rejected";

export interface VerificationState {
  status: VerificationStatus;
  // camelCase keys of mandatory fields still blank. Order matches the
  // backend's MANDATORY_FIELDS tuple, so the first entry is always the
  // next field to prompt for.
  missing: string[];
  mandatoryTotal: number;
  submittedAt: string | null;
  verifiedAt: string | null;
  rejectedReason: string | null;
  /** When the admin ticked specific items on a reject — subset of the
   *  mandatory field keys plus ``doc:<slug>`` tokens. Null for drafts
   *  and verified. Shows up on the Passport card so the user sees
   *  exactly what to fix. */
  rejectedItems: string[] | null;
  /** Display name per ``doc:<slug>`` key in ``rejectedItems`` — looked up
   *  from the current catalog so the trader sees "Business registration
   *  certificate" even when they typed something else as cert_type. Field
   *  keys are NOT in this map; the frontend labels those from
   *  MANDATORY_FIELDS. Null when no rejection or no doc:* keys. */
  rejectedItemLabels: Record<string, string> | null;
}

export type MemberRole = "owner" | "admin" | "member";

export interface Me {
  userId: string;
  businessId: string;
  role: MemberRole;
  email: string;
  emailVerifiedAt: string | null;
  /** The business legal name. */
  businessName: string | null;
  /** ISO 4217 — converted prices and price filters are shown in this. */
  displayCurrency: string;
  userType: "buyer" | "seller";
  /** The business verification status. */
  status: VerificationStatus;
  verification: VerificationState;
  primary: PrimaryData;
  business: BusinessData;
}

export interface RevealedContact {
  /** The seller's business id. */
  sellerId: string;
  fullName: string | null;
  businessName: string | null;
  entityType: string | null;
  email: string | null;
  addressLine: string | null;
  city: string | null;
  state: string | null;
  pincode: string | null;
  country: string | null;
  websiteUrl: string | null;
  revealedAt: string;
}

export interface PincodeLookup {
  pincode: string;
  city: string;
  district?: string;
  state: string;
}

export interface VerificationDoc {
  id: string;
  certType: string;
  filename: string;
  mimeType: string;
  sizeBytes: number;
  status: "pending" | "approved" | "rejected";
  rejectionReason: string | null;
  uploadedAt: string;
  reviewedAt: string | null;
  url: string;
  requiredDocTypeId: string | null;
  requirementDisplayName: string | null;
  requirementSlug: string | null;
}

/** One row of the Documents tab — either a mandatory/optional slot
 *  (``requirementId`` set) or a free-form custom upload. */
export interface DocSlot {
  requirementId: string | null;
  slug: string | null;
  displayName: string;
  description: string | null;
  helpUrl: string | null;
  isMandatory: boolean;
  upload: VerificationDoc | null;
}

export interface DocRequirementsResponse {
  countryCode: string;
  required: DocSlot[];
  optional: DocSlot[];
  customUploads: VerificationDoc[];
}

export interface ProductRead {
  id: string;
  name: string;
  category: string;
  variety?: string;
  originState?: string;
  packaging?: string;
  quantity?: number | string;
  unit: string;
  moq?: number | string;
  pricePerUnit?: number | string;
  description?: string;
  photos: string[];
  currency: string;
  priceUsd?: string | null;
  priceUsdAsOf?: string | null;
}

// ── Auth flow shapes ───────────────────────────────────────────────────

export interface SignupCodeResponse {
  email: string;
  message: string;
  /** Seconds until another code may be requested. */
  resendInSec: number;
  /** Seconds the code stays valid. */
  expiresInSec: number;
  /** Only present when the backend runs with DEBUG=true. Never in production. */
  devCode?: string | null;
}

export interface SignupVerifyResponse {
  email: string;
  verified: true;
}

export interface SignupCompleteIn {
  email: string;
  fullName: string;
  position?: string;
  /** ISO 3166-1 alpha-2 — the home country of the business. */
  country: string;
  password: string;
  acceptTerms: true;
}

export interface LoginResponse {
  userId: string;
  businessId: string;
  role: MemberRole;
  email: string;
  businessName: string | null;
}

// ── Onboarding wizard shapes ───────────────────────────────────────────

export interface OnboardingStatus {
  companyInfoDone: boolean;
  primaryContactDone: boolean;
  businessProfileDone: boolean;
}

export interface CompanyInfoIn {
  legalName: string;
  industry: string;
  operatingCountries: string[];
  websiteUrl?: string;
  entityType?: EntityType | null;
  /** Company address + socials. Each is only changed when sent; "" clears. */
  addressLine?: string;
  city?: string;
  state?: string;
  pincode?: string;
  /** ISO 3166-1 alpha-2. */
  country?: string;
  googleBusinessUrl?: string;
  facebookUrl?: string;
}

export interface PrimaryContactIn {
  fullName: string;
  phone?: string;
  position?: string;
}

export interface BusinessProfileIn {
  tradePosition: string;
  sellerType?: string;
  exportStatus?: string;
  targetMarkets: string[];
  targetBuyerTypes: string[];
  companyIntroduction?: string;
}

// ── HTTP helper ────────────────────────────────────────────────────────
//
// Auth is the HttpOnly `cor1x_session` cookie only. All calls go through
// the same-origin /api proxy (next.config.mjs), so the cookie is
// first-party and sent automatically.

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

/** Turn a FastAPI error body into a readable message. */
function messageFrom(body: unknown, status: number): string {
  const b = body as { detail?: unknown; error?: string } | null;
  if (b && typeof b.detail === "string") return b.detail;
  if (b && Array.isArray(b.detail) && b.detail.length) {
    // Pydantic validation errors: [{loc, msg}]
    const first = b.detail[0] as { msg?: string; loc?: unknown[] };
    const field = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1]) : "";
    return first.msg ? `${field ? field + ": " : ""}${first.msg.replace(/^Value error, /, "")}` : `Request failed (${status})`;
  }
  if (b && typeof b.error === "string") return b.error;
  if (status === 429) return "Too many attempts. Please wait a moment and try again.";
  if (status >= 500) return "Something went wrong on our side. Please try again.";
  return `Request failed (${status})`;
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
  });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(messageFrom(body, res.status), res.status);
  return body as T;
}

/** Resolve a backend-relative asset path (photos, documents) to a URL. */
export function assetUrl(rel: string | null | undefined): string {
  if (!rel) return "";
  if (/^(https?:|data:|blob:)/.test(rel)) return rel;
  return `${API_BASE}${rel.startsWith("/") ? rel : `/${rel}`}`;
}

/** @deprecated use assetUrl */
export const photoUrl = assetUrl;

export const api = {
  // ─── Auth ───
  signupCode: (email: string) =>
    jsonFetch<SignupCodeResponse>("/auth/signup/code", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  signupVerify: (email: string, code: string) =>
    jsonFetch<SignupVerifyResponse>("/auth/signup/verify", {
      method: "POST",
      body: JSON.stringify({ email, code }),
    }),

  signupComplete: (payload: SignupCompleteIn) =>
    jsonFetch<LoginResponse>("/auth/signup/complete", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  login: (payload: { email: string; password: string }) =>
    jsonFetch<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  changePassword: (payload: { currentPassword: string; newPassword: string }) =>
    jsonFetch<{ ok: true }>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  session: () => jsonFetch<{ userId: string | null }>("/auth/session"),
  logout: () => jsonFetch<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  logoutAll: () => jsonFetch<{ ok: boolean }>("/auth/logout-all", { method: "POST" }),

  // ─── Onboarding wizard ───
  onboardingStatus: () => jsonFetch<OnboardingStatus>("/onboarding/status"),
  saveCompanyInfo: (payload: CompanyInfoIn) =>
    jsonFetch<{ ok: true; status: OnboardingStatus }>("/onboarding/company", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  savePrimaryContact: (payload: PrimaryContactIn) =>
    jsonFetch<{ ok: true; status: OnboardingStatus }>("/onboarding/contact", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  saveBusinessProfile: (payload: BusinessProfileIn) =>
    jsonFetch<{ ok: true; status: OnboardingStatus }>("/onboarding/business", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // ─── Lookups ───
  lookupPincode: (pincode: string) => jsonFetch<PincodeLookup>(`/pincode/${pincode}`),

  // ─── Me ───
  me: () => jsonFetch<Me>("/me"),
  updateMe: (payload: { displayCurrency?: string }) =>
    jsonFetch<Me>("/me", { method: "PATCH", body: JSON.stringify(payload) }),
  deleteMe: () => jsonFetch<void>("/me", { method: "DELETE" }),

  // ─── Verification docs ───
  submitForVerification: () =>
    jsonFetch<VerificationState>("/me/submit-verification", {
      method: "POST",
    }),
  listVerificationDocs: () =>
    jsonFetch<VerificationDoc[]>("/me/verification-docs"),
  uploadVerificationDoc: (
    certType: string,
    file: File,
    opts?: { requiredDocTypeId?: string | null },
  ): Promise<VerificationDoc> => {
    const form = new FormData();
    form.append("cert_type", certType);
    form.append("file", file);
    if (opts?.requiredDocTypeId) form.append("required_doc_type_id", opts.requiredDocTypeId);
    return jsonFetch<VerificationDoc>("/me/verification-docs", { method: "POST", body: form });
  },
  deleteVerificationDoc: (id: string) =>
    jsonFetch<void>(`/me/verification-docs/${id}`, { method: "DELETE" }),
  listDocRequirements: () =>
    jsonFetch<DocRequirementsResponse>("/me/verification-docs/requirements"),

  // ─── Products / reveals ───
  revealContact: (productId: string) =>
    jsonFetch<RevealedContact>(`/products/${productId}/contact-reveal`, {
      method: "POST",
    }),
  listProducts: () => jsonFetch<ProductRead[]>("/products"),
  createProduct: (payload: unknown) =>
    jsonFetch<ProductRead>("/products", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  uploadProductPhoto: (file: File): Promise<{ url: string }> => {
    const form = new FormData();
    form.append("file", file);
    return jsonFetch<{ url: string }>("/products/upload-photo", { method: "POST", body: form });
  },
};
