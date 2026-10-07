const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

export interface AdminMe {
  email: string;
}

export interface DashboardStats {
  totalUsers: number;
  verifiedUsers: number;
  pendingVerificationUsers: number;
  activeUsers: number;
  signedUpUsers: number;
  emailVerifiedUsers: number;
  rejectedUsers: number;
  totalProducts: number;
  recentSignups24H: number;
  stuckSignups: number;
  onboardedUsers: number;
  pendingDocs: number;
}

export interface TimelinePoint {
  date: string;
  count: number;
}

export interface StuckUser {
  userId: string;
  email: string;
  businessName: string | null;
  createdAt: string;
  hoursWaiting: number;
}

export interface VerifyDoc {
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
}

export interface PendingDocRow {
  doc: VerifyDoc;
  userId: string;
  userEmail: string;
  userBusinessName: string | null;
  userFullName: string | null;
  userCountry: string | null;
}

export interface VerifyQueueRow {
  userId: string;
  email: string;
  fullName: string | null;
  businessName: string | null;
  country: string | null;
  industry: string | null;
  tradePosition: string | null;
  operatingCountries: string[] | null;
  onboardedAt: string | null;
  submittedAt: string | null;
  createdAt: string;
  missingFields: string[];
  docs: VerifyDoc[];
}

export interface UserDetail {
  userId: string;
  email: string;
  emailVerifiedAt: string | null;
  businessName: string | null;
  status: string;
  createdAt: string;
  updatedAt: string;
  hasPassword: boolean;
  profile: Record<string, unknown> | null;
  businessProfile: Record<string, unknown> | null;
  productCount: number;
  docs: VerifyDoc[];
  verificationSubmittedAt: string | null;
  verifiedAt: string | null;
  verificationRejectedReason: string | null;
  missingMandatoryFields: string[];
}

export interface UserPatch {
  businessName?: string | null;
  profile?: Record<string, unknown>;
  businessProfile?: Record<string, unknown>;
}

export interface UserRow {
  userId: string;
  email: string;
  businessName: string | null;
  status: string;
  emailVerified: boolean;
  hasPassword: boolean;
  createdAt: string;
}

export interface UsersListOut {
  total: number;
  items: UserRow[];
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
    const msg =
      (body as { detail?: string })?.detail || `Request failed (${res.status})`;
    const err = new Error(msg) as Error & { status?: number };
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
    req<{ userId: string; status: string }>(`/admin/users/${id}/verify`, {
      method: "POST",
    }),
  rejectUser: (id: string, reason: string) =>
    req<{ userId: string; status: string }>(`/admin/users/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
};
