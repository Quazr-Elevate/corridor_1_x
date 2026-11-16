import type { ItemList, ProductRead } from "./api";
import { versioned } from "./apiBase";
import type { CertificateType, SpecParameter } from "./publicApi";

export const API_BASE = versioned(process.env.NEXT_PUBLIC_API_BASE_URL || "/api");

export type AdminRole = "super_admin" | "reviewer";

export type AdminPermission =
  | "dashboard.view"
  | "users.view"
  | "users.edit"
  | "kyb.review"
  | "kyb.sensitive_view"
  | "catalog.view"
  | "catalog.manage"
  | "listings.review"
  | "accounts.security"
  | "admins.manage";

export interface AdminMe {
  id: string;
  email: string;
  fullName: string;
  role: AdminRole;
  permissions: AdminPermission[];
  mustChangePassword: boolean;
}

export const ADMIN_ROLE_LABEL: Record<AdminRole, string> = {
  super_admin: "Super admin",
  reviewer: "Reviewer",
};

export type LockState = "none" | "temporary" | "support";

export interface AdminAccount {
  id: string;
  email: string;
  fullName: string;
  role: AdminRole;
  status: "active" | "disabled";
  mustChangePassword: boolean;
  lockState: LockState;
  lastLoginAt: string | null;
  createdBy: string;
  createdAt: string;
}

export interface AdminWithPassword {
  admin: AdminAccount;
  /** Shown once; never stored in plain form. */
  temporaryPassword: string;
}

export interface AccountSecurity {
  lockState: LockState;
  lockedUntil: string | null;
  failedLoginCount: number;
  activeSession: { createdAt: string; lastSeenAt: string; ipPrefix: string | null; userAgent: string | null } | null;
  lastLoginAt: string | null;
}

export interface DashboardStats {
  totalUsers: number;
  totalBusinesses: number;
  draftBusinesses: number;
  pendingVerificationBusinesses: number;
  verifiedBusinesses: number;
  rejectedBusinesses: number;
  totalProducts: number;
  recentSignups24H: number;
  /** Businesses still in draft 24h+ after signup. */
  stuckSignups: number;
  pendingDocs: number;
}

export interface TimelinePoint {
  date: string;
  count: number;
}

export interface StuckUser {
  userId: string;
  businessId: string;
  email: string;
  businessName: string | null;
  createdAt: string;
  hoursWaiting: number;
}

export type DocStatus = "pending" | "approved" | "rejected";

/** A KYB entry under review: a document type (or Other) + a number and/or a file. */
export interface VerifyDoc {
  id: string;
  documentTypeId: string | null;
  documentTypeCode: string | null;
  isOther: boolean;
  certType: string;
  hasValue: boolean;
  /** "••••F1Z5" — the full number only via `adminApi.revealDocValue` (audited). */
  valueMasked: string | null;
  hasFile: boolean;
  filename: string | null;
  mimeType: string | null;
  sizeBytes: number | null;
  status: DocStatus;
  rejectionReason: string | null;
  uploadedAt: string;
  reviewedAt: string | null;
  /** Backend-relative path (e.g. /admin/docs/{id}/file) for `adminApi.docFile`, or null without a file. */
  url: string | null;
}

export type KybInputKind = "value" | "file" | "value_or_file" | "value_and_file";

export interface AdminKybDocType {
  id: string;
  country: string;
  code: string;
  name: string;
  inputKind: KybInputKind;
  needsValue: boolean;
  needsFile: boolean;
  valuePattern: string | null;
  valuePlaceholder: string | null;
  helpText: string | null;
  isMandatory: boolean;
  isUnique: boolean;
  sortOrder: number;
  active: boolean;
}

/** A country in the admin list (open or paused) with counts. */
export interface AdminCountry {
  code: string;
  name: string;
  flag: string | null;
  dialCode: string | null;
  defaultCurrency: string;
  regionLabel: string;
  postalLabel: string;
  postalPattern: string | null;
  active: boolean;
  documents: number;
  requiredDocuments: number;
  businesses: number;
}

export interface AdminCountryFields {
  name?: string | null;
  flag?: string | null;
  dialCode?: string | null;
  defaultCurrency?: "INR" | "AED" | "USD" | null;
  regionLabel?: string | null;
  postalLabel?: string | null;
  postalPattern?: string | null;
}

export interface AdminKybDocTypeIn {
  country: string;
  code: string;
  name: string;
  inputKind: KybInputKind;
  valuePattern?: string | null;
  valuePlaceholder?: string | null;
  helpText?: string | null;
  isMandatory?: boolean;
  isUnique?: boolean;
  sortOrder?: number;
  active?: boolean;
}

export interface PendingDocRow {
  doc: VerifyDoc;
  userId: string;
  businessId: string;
  userEmail: string;
  userBusinessName: string | null;
  userFullName: string | null;
  userCountry: string | null;
}

export interface VerifyQueueRow {
  userId: string;
  businessId: string;
  email: string;
  fullName: string | null;
  businessName: string | null;
  /** Masked company code; null until the business is verified. */
  companyCode: string | null;
  country: string | null;
  industry: string | null;
  tradePosition: string | null;
  operatingCountries: string[] | null;
  submittedAt: string | null;
  createdAt: string;
  missingFields: string[];
  docs: VerifyDoc[];
  /** "submitted" — sent for KYB; "documents" — a verified business added documents. */
  reviewKind: "submitted" | "documents";
  status: string;
}

export interface UserDetail {
  userId: string;
  businessId: string;
  role: "owner" | "admin" | "member";
  email: string;
  emailVerifiedAt: string | null;
  /** The business legal name — not patchable on its own. */
  businessName: string | null;
  /** Masked company code; null until the business is verified. */
  companyCode: string | null;
  /** The business verification status. */
  status: string;
  createdAt: string;
  updatedAt: string;
  profile: Record<string, unknown> | null;
  businessProfile: Record<string, unknown> | null;
  productCount: number;
  docs: VerifyDoc[];
  verificationSubmittedAt: string | null;
  verifiedAt: string | null;
  verificationRejectedReason: string | null;
  verificationRejectedItems: string[];
  missingMandatoryFields: string[];
  security?: AccountSecurity | null;
}

/* ── Patch keys — mirror the backend's editable whitelists exactly. ── */

export const PROFILE_PATCH_KEYS = [
  "fullName",
  "phone",
  "position",
] as const;
export type ProfilePatchKey = (typeof PROFILE_PATCH_KEYS)[number];

/** Business keys whose value is a list of strings; everything else is a string. */
export const BUSINESS_LIST_KEYS = ["operatingCountries", "targetMarkets", "targetBuyerTypes"] as const;
export type BusinessListKey = (typeof BUSINESS_LIST_KEYS)[number];

export const BUSINESS_PATCH_KEYS = [
  "legalName",
  "entityType",
  "industry",
  "operatingCountries",
  "websiteUrl",
  "addressLine",
  "city",
  "state",
  "pincode",
  "country",
  "googleBusinessUrl",
  "facebookUrl",
  "tradePosition",
  "sellerType",
  "exportStatus",
  "targetMarkets",
  "targetBuyerTypes",
  "companyIntroduction",
] as const;
export type BusinessPatchKey = (typeof BUSINESS_PATCH_KEYS)[number];
export type BusinessStringKey = Exclude<BusinessPatchKey, BusinessListKey>;

export type ProfilePatch = Partial<Record<ProfilePatchKey, string>>;
export type BusinessPatch = Partial<Record<Exclude<BusinessStringKey, "entityType">, string>> & {
  entityType?: string | null;
} &
  Partial<Record<BusinessListKey, string[]>>;

export interface UserPatch {
  profile?: ProfilePatch;
  businessProfile?: BusinessPatch;
}

export function isBusinessListKey(k: string): k is BusinessListKey {
  return (BUSINESS_LIST_KEYS as readonly string[]).includes(k);
}

/* ── Users ── */

export const USER_STATUSES = [
  "draft",
  "pending_verification",
  "verified",
  "rejected",
] as const;
export type UserStatus = (typeof USER_STATUSES)[number];

export const USER_STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  pending_verification: "In review",
  verified: "Verified",
  rejected: "Rejected",
};

export interface UserRow {
  userId: string;
  businessId: string;
  email: string;
  businessName: string | null;
  /** Masked company code; null until the business is verified. */
  companyCode: string | null;
  fullName: string | null;
  /** The business verification status. */
  status: string;
  emailVerified: boolean;
  createdAt: string;
}

export interface UsersListOut {
  total: number;
  items: UserRow[];
}

/* ── Errors ── */

export interface AdminError extends Error {
  status?: number;
}

/** Human message from a thrown admin API error (or anything else). */
export function errorMessage(e: unknown, fallback = "Something went wrong."): string {
  if (e instanceof Error && e.message) return e.message;
  return fallback;
}

export function errorStatus(e: unknown): number | undefined {
  return (e as AdminError | null)?.status;
}

/** Absolute URL of a document file route. Fetch it with `adminApi.docFile` (a reason is required). */
export function docFileUrl(url: string | null): string {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_BASE}${url.startsWith("/") ? "" : "/"}${url}`;
}

function detailToMessage(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail) return detail;
  // FastAPI validation errors: [{ loc, msg, type }, …]
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d) => {
        const item = d as { msg?: string; loc?: unknown[] };
        const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : null;
        return field && typeof field === "string" ? `${field}: ${item.msg ?? "invalid"}` : item.msg ?? "Invalid value";
      })
      .join(" · ");
  }
  return `Request failed (${status})`;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(detailToMessage((body as { detail?: unknown })?.detail, res.status)) as AdminError;
    err.status = res.status;
    throw err;
  }
  return body as T;
}

// ── Listings (review queue) ──────────────────────────────────────────

export interface ListingSeller {
  businessId: string;
companyCode: string | null;
    legalName: string | null;
  state: string | null;
  country: string | null;
  verified: boolean;
}

export interface AdminListingRow {
  id: string;
  name: string;
  category: string;
  status: ProductRead["status"];
  /** "new" — a submitted listing; "revision" — edits to a published one. */
  reviewKind: "new" | "revision" | null;
  waitingSince: string | null;
  photo: string | null;
  seller: ListingSeller;
}

export interface RevisionChange {
  field: string;
  current: unknown;
  proposed: unknown;
}

export interface AdminListingDetail {
  listing: ProductRead;
  reviewKind: "new" | "revision" | null;
  seller: ListingSeller;
  changes: RevisionChange[];
}

export interface ListingStatusChanged {
  id: string;
  status: ProductRead["status"];
  hasPendingRevision: boolean;
}

export type SpecParameterIn = Pick<SpecParameter, "category" | "code" | "name"> &
  Partial<Pick<SpecParameter, "valueType" | "unit" | "defaultOperator" | "testMethod" | "isRequired" | "sortOrder">>;
export type SpecParameterPatch = Partial<
  Pick<SpecParameter, "name" | "unit" | "defaultOperator" | "testMethod" | "isRequired" | "sortOrder" | "active">
>;
export type CertificateTypeIn = Pick<CertificateType, "category" | "code" | "name"> &
  Partial<Pick<CertificateType, "helpText" | "isRequired" | "sortOrder">>;
export type CertificateTypePatch = Partial<Pick<CertificateType, "name" | "helpText" | "isRequired" | "sortOrder" | "active">>;

export const adminApi = {
  login: (email: string, password: string) =>
    req<AdminMe>("/admin/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => req<{ ok: true }>("/admin/logout", { method: "POST" }),
  me: () => req<AdminMe>("/admin/me"),
  changePassword: (currentPassword: string, newPassword: string) =>
    req<AdminMe>("/admin/change-password", {
      method: "POST",
      body: JSON.stringify({ currentPassword, newPassword }),
    }),
  admins: () => req<ItemList<AdminAccount>>("/admin/admins").then((r) => r.items),
  createAdmin: (payload: { email: string; fullName: string; role: AdminRole }) =>
    req<AdminWithPassword>("/admin/admins", { method: "POST", body: JSON.stringify(payload) }),
  updateAdmin: (id: string, patch: { fullName?: string; role?: AdminRole; status?: "active" | "disabled" }) =>
    req<AdminAccount>(`/admin/admins/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  resetAdminPassword: (id: string) =>
    req<AdminWithPassword>(`/admin/admins/${id}/reset-password`, { method: "POST" }),
  unlockAdmin: (id: string) => req<AdminAccount>(`/admin/admins/${id}/unlock`, { method: "POST" }),
  signOutAdmin: (id: string) => req<{ ok: true }>(`/admin/admins/${id}/sign-out`, { method: "POST" }),
  unlockUser: (id: string) => req<{ ok: true }>(`/admin/users/${id}/unlock`, { method: "POST" }),
  signOutUser: (id: string) => req<{ ok: true }>(`/admin/users/${id}/sign-out`, { method: "POST" }),
  stats: () => req<DashboardStats>("/admin/dashboard/stats"),
  timeline: (days = 30) =>
    req<TimelinePoint[]>(`/admin/dashboard/timeline?days=${days}`),
  stuck: (limit = 10) =>
    req<ItemList<StuckUser>>(`/admin/dashboard/stuck?limit=${limit}`).then((r) => r.items),
  verifyQueue: () => req<ItemList<VerifyQueueRow>>("/admin/verify/queue").then((r) => r.items),
  pendingDocs: () => req<ItemList<PendingDocRow>>("/admin/docs/pending").then((r) => r.items),
  approveDoc: (docId: string) =>
    req<{ docId: string; status: string }>(`/admin/docs/${docId}/approve`, {
      method: "POST",
    }),
  rejectDoc: (docId: string, reason: string) =>
    req<{ docId: string; status: string }>(`/admin/docs/${docId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  /** Both calls are refused without a reason; it is stored on the audit row. */
  revealDocValue: (docId: string, reason: string) =>
    req<{ id: string; certType: string; value: string }>(`/admin/docs/${docId}/reveal`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  docFile: async (url: string, reason: string): Promise<Blob> => {
    const res = await fetch(docFileUrl(url), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const err = new Error(detailToMessage((body as { detail?: unknown })?.detail, res.status)) as AdminError;
      err.status = res.status;
      throw err;
    }
    return res.blob();
  },
  kybTypes: (country?: string) =>
    req<ItemList<AdminKybDocType>>(
      `/admin/kyb/document-types${country ? `?country=${encodeURIComponent(country)}` : ""}`,
    ).then((r) => r.items),
  createKybType: (payload: AdminKybDocTypeIn) =>
    req<AdminKybDocType>("/admin/kyb/document-types", { method: "POST", body: JSON.stringify(payload) }),
  updateKybType: (id: string, patch: Partial<Omit<AdminKybDocTypeIn, "country" | "code">>) =>
    req<AdminKybDocType>(`/admin/kyb/document-types/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  user: (id: string) => req<UserDetail>(`/admin/users/${id}`),
  patchUser: (id: string, patch: UserPatch) =>
    req<UserDetail>(`/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  users: (params: {
    status?: string;
    q?: string;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status", params.status);
    if (params.q) qs.set("q", params.q);
    qs.set("limit", String(params.limit ?? 50));
    qs.set("offset", String(params.offset ?? 0));
    return req<UsersListOut>(`/admin/users?${qs}`);
  },
  verifyUser: (id: string) =>
    req<{ userId: string; businessId: string; status: string }>(`/admin/users/${id}/verify`, {
      method: "POST",
    }),
  rejectUser: (id: string, reason: string, failedItems: string[] = []) =>
    req<{ userId: string; businessId: string; status: string }>(`/admin/users/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason, failedItems }),
    }),
  kybCountries: () => req<ItemList<AdminCountry>>("/admin/kyb/countries").then((r) => r.items),
  createKybCountry: (
    country: string,
    documents: Array<Omit<AdminKybDocTypeIn, "country">>,
    details: AdminCountryFields = {},
  ) =>
    req<AdminKybDocType[]>("/admin/kyb/countries", {
      method: "POST",
      body: JSON.stringify({ country, ...details, documents }),
    }),
  updateKybCountry: (code: string, patch: AdminCountryFields & { active?: boolean }) =>
    req<AdminCountry>(`/admin/kyb/countries/${code}`, { method: "PATCH", body: JSON.stringify(patch) }),

  // ─── Listings ───
  listings: (params: { queue?: "pending" | "all"; status?: string; q?: string } = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v) qs.set(k, v);
    return req<ItemList<AdminListingRow>>(`/admin/listings${qs.size ? `?${qs}` : ""}`);
  },
  listing: (id: string) => req<AdminListingDetail>(`/admin/listings/${id}`),
  approveListing: (id: string) => req<ListingStatusChanged>(`/admin/listings/${id}/approve`, { method: "POST" }),
  rejectListing: (id: string, reason: string) =>
    req<ListingStatusChanged>(`/admin/listings/${id}/reject`, { method: "POST", body: JSON.stringify({ reason }) }),
  setCertificateVisibility: (listingId: string, certificateId: string, visibility: "internal" | "downloadable") =>
    req<{ id: string; visibility: string }>(`/admin/listings/${listingId}/certificates/${certificateId}/visibility`, {
      method: "POST",
      body: JSON.stringify({ visibility }),
    }),

  // ─── Listing templates ───
  specParameters: (category?: string) =>
    req<ItemList<SpecParameter>>(
      `/admin/listing-templates/spec-parameters${category ? `?category=${encodeURIComponent(category)}` : ""}`,
    ).then((r) => r.items),
  createSpecParameter: (payload: SpecParameterIn) =>
    req<SpecParameter>("/admin/listing-templates/spec-parameters", { method: "POST", body: JSON.stringify(payload) }),
  updateSpecParameter: (id: string, patch: SpecParameterPatch) =>
    req<SpecParameter>(`/admin/listing-templates/spec-parameters/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  certificateTypes: (category?: string) =>
    req<ItemList<CertificateType>>(
      `/admin/listing-templates/certificate-types${category ? `?category=${encodeURIComponent(category)}` : ""}`,
    ).then((r) => r.items),
  createCertificateType: (payload: CertificateTypeIn) =>
    req<CertificateType>("/admin/listing-templates/certificate-types", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateCertificateType: (id: string, patch: CertificateTypePatch) =>
    req<CertificateType>(`/admin/listing-templates/certificate-types/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
};
