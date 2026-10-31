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
  // Stable keys still needed before KYB submission, in order: profile
  // fields ("addressLine") then mandatory documents ("kyb:gstin").
  missing: string[];
  /** Human labels, same order as `missing`. */
  missingLabels: string[];
  /** Items Corridor ops flagged on the last rejection ("addressLine",
   *  "kyb:gstin", "doc:<entry id>"); cleared on resubmit. */
  rejectedItems: string[];
  /** Labels for `rejectedItems`, same order (document names from the server). */
  rejectedItemLabels: string[];
  mandatoryTotal: number;
  submittedAt: string | null;
  verifiedAt: string | null;
  rejectedReason: string | null;
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
  /** Public images of the business (dashboard hero). */
  branding: { logoUrl: string | null; bannerUrl: string | null };
  /** True until the quick tour is finished or skipped. */
  showTour: boolean;
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

/** One KYB entry: a document type (or "Other") + a number and/or a file.
 *  The number is never sent in full — only `valueMasked` ("••••F1Z5"). */
export interface VerificationDoc {
  id: string;
  documentTypeId: string | null;
  documentTypeCode: string | null;
  isOther: boolean;
  /** Display name: the type's name, or the custom name of an Other entry. */
  certType: string;
  hasValue: boolean;
  valueMasked: string | null;
  hasFile: boolean;
  filename: string | null;
  mimeType: string | null;
  sizeBytes: number | null;
  status: "pending" | "approved" | "rejected";
  rejectionReason: string | null;
  uploadedAt: string;
  updatedAt: string | null;
  reviewedAt: string | null;
  /** Authenticated file route, or null when the entry has no file. */
  url: string | null;
}

/** A country businesses can pick (set up by Corridor ops), with its address conventions. */
export interface KybCountry {
  code: string;
  name: string;
  flag: string | null;
  dialCode: string | null;
  defaultCurrency: string;
  regionLabel: string;
  postalLabel: string;
  postalPattern: string | null;
}

/** An option of the KYB dropdown (admin-defined, per country). */
export interface KybDocType {
  id: string;
  country: string;
  code: string;
  name: string;
  inputKind: "value" | "file" | "value_or_file" | "value_and_file";
  needsValue: boolean;
  needsFile: boolean;
  valuePattern: string | null;
  valuePlaceholder: string | null;
  helpText: string | null;
  isMandatory: boolean;
  sortOrder: number;
}

export interface KybEntryIn {
  documentTypeId?: string;
  customName?: string;
  value?: string;
  file?: File | null;
}

export interface KybEntryPatch {
  customName?: string;
  value?: string;
  file?: File | null;
  removeValue?: boolean;
  removeFile?: boolean;
}

export interface BusinessProfileSaveIn {
  legalName: string;
  country: string;
  addressLine?: string;
  city?: string;
  state?: string;
  pincode?: string;
  websiteUrl?: string;
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
  companyName: string;
  position?: string;
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

export interface SecurityDevice {
  createdAt: string;
  lastSeenAt: string;
  expiresAt: string;
  ipPrefix: string | null;
  userAgent: string | null;
  current: boolean;
}

export interface AuthEventRow {
  event: string;
  createdAt: string;
  ipPrefix: string | null;
  userAgent: string | null;
}

/** GET /auth/security — the one signed-in device + recent sign-in activity. */
export interface SecurityOverview {
  device: SecurityDevice | null;
  recent: AuthEventRow[];
  idleTimeoutMinutes: number;
  maxSessionDays: number;
}

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

  forgotPassword: (email: string) =>
    jsonFetch<{ message: string; expiresInSec: number; devCode?: string | null }>("/auth/password/forgot", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  resetPassword: (payload: { email: string; code: string; newPassword: string }) =>
    jsonFetch<{ ok: true }>("/auth/password/reset", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  security: () => jsonFetch<SecurityOverview>("/auth/security"),

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
  updateMe: (payload: { displayCurrency?: string; tourCompleted?: boolean }) =>
    jsonFetch<Me>("/me", { method: "PATCH", body: JSON.stringify(payload) }),
  saveBusinessProfileV2: (payload: BusinessProfileSaveIn) =>
    jsonFetch<Me>("/me/business-profile", { method: "PUT", body: JSON.stringify(payload) }),
  uploadBranding: (slot: "logo" | "banner", file: File): Promise<{ url: string }> => {
    const form = new FormData();
    form.append("file", file);
    return jsonFetch<{ url: string }>(`/me/business/${slot}`, { method: "POST", body: form });
  },
  deleteBranding: (slot: "logo" | "banner") => jsonFetch<void>(`/me/business/${slot}`, { method: "DELETE" }),
  deleteMe: () => jsonFetch<void>("/me", { method: "DELETE" }),

  // ─── Verification docs ───
  submitForVerification: () =>
    jsonFetch<VerificationState>("/me/submit-verification", {
      method: "POST",
    }),
  listVerificationDocs: () =>
    jsonFetch<VerificationDoc[]>("/me/verification-docs"),
  uploadVerificationDoc: (certType: string, file: File): Promise<VerificationDoc> => {
    const form = new FormData();
    form.append("customName", certType);
    form.append("file", file);
    return jsonFetch<VerificationDoc>("/me/verification-docs", { method: "POST", body: form });
  },
  kybCountries: () => jsonFetch<KybCountry[]>("/kyb/countries"),
  kybDocTypes: (country?: string) =>
    jsonFetch<KybDocType[]>(`/kyb/document-types${country ? `?country=${encodeURIComponent(country)}` : ""}`),
  addKybEntry: (entry: KybEntryIn): Promise<VerificationDoc> => {
    const form = new FormData();
    if (entry.documentTypeId) form.append("documentTypeId", entry.documentTypeId);
    if (entry.customName) form.append("customName", entry.customName);
    if (entry.value) form.append("value", entry.value);
    if (entry.file) form.append("file", entry.file);
    return jsonFetch<VerificationDoc>("/me/verification-docs", { method: "POST", body: form });
  },
  updateKybEntry: (id: string, patch: KybEntryPatch): Promise<VerificationDoc> => {
    const form = new FormData();
    if (patch.customName) form.append("customName", patch.customName);
    if (patch.value) form.append("value", patch.value);
    if (patch.file) form.append("file", patch.file);
    if (patch.removeValue) form.append("removeValue", "true");
    if (patch.removeFile) form.append("removeFile", "true");
    return jsonFetch<VerificationDoc>(`/me/verification-docs/${id}`, { method: "PATCH", body: form });
  },
  revealKybValue: (id: string) =>
    jsonFetch<{ id: string; certType: string; value: string }>(`/me/verification-docs/${id}/reveal`, { method: "POST" }),
  deleteVerificationDoc: (id: string) =>
    jsonFetch<void>(`/me/verification-docs/${id}`, { method: "DELETE" }),

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
