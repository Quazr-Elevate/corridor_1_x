export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

export interface AdminMe {
  email: string;
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

export interface VerifyDoc {
  id: string;
  certType: string;
  filename: string;
  mimeType: string;
  sizeBytes: number;
  status: DocStatus;
  rejectionReason: string | null;
  uploadedAt: string;
  reviewedAt: string | null;
  /** Authenticated, backend-relative path (e.g. /admin/docs/{id}/file). Use `docFileUrl()`. */
  url: string;
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
  country: string | null;
  industry: string | null;
  tradePosition: string | null;
  operatingCountries: string[] | null;
  submittedAt: string | null;
  createdAt: string;
  missingFields: string[];
  docs: VerifyDoc[];
}

export interface UserDetail {
  userId: string;
  businessId: string;
  role: "owner" | "admin" | "member";
  email: string;
  emailVerifiedAt: string | null;
  /** The business legal name — not patchable on its own. */
  businessName: string | null;
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
  missingMandatoryFields: string[];
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

/** Absolute URL for an authenticated document file (admin cookie is sent). */
export function docFileUrl(url: string): string {
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

export const adminApi = {
  login: (email: string, password: string) =>
    req<AdminMe>("/admin/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => req<{ ok: true }>("/admin/logout", { method: "POST" }),
  me: () => req<AdminMe>("/admin/me"),
  stats: () => req<DashboardStats>("/admin/dashboard/stats"),
  timeline: (days = 30) =>
    req<TimelinePoint[]>(`/admin/dashboard/timeline?days=${days}`),
  stuck: (limit = 10) =>
    req<StuckUser[]>(`/admin/dashboard/stuck?limit=${limit}`),
  verifyQueue: () => req<VerifyQueueRow[]>("/admin/verify/queue"),
  pendingDocs: () => req<PendingDocRow[]>("/admin/docs/pending"),
  approveDoc: (docId: string) =>
    req<{ docId: string; status: string }>(`/admin/docs/${docId}/approve`, {
      method: "POST",
    }),
  rejectDoc: (docId: string, reason: string) =>
    req<{ docId: string; status: string }>(`/admin/docs/${docId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
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
  rejectUser: (id: string, reason: string) =>
    req<{ userId: string; businessId: string; status: string }>(`/admin/users/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
};
