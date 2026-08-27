const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface AdminMe {
  email: string;
}

export interface DashboardStats {
  totalBuyers: number;
  totalSellers: number;
  totalVerified: number;
  signupsThisWeek: number;
  signupsPrevWeek: number;
  funnel: Record<string, number>;
  topStates: {
    buyer: { state: string; count: number }[];
    seller: { state: string; count: number }[];
  };
  duplicateAlerts: {
    kind: string;
    value: string;
    users: { user_id: string; label: string }[];
  }[];
}

export interface TimelinePoint {
  date: string;
  buyer: number;
  seller: number;
}

export interface RecentSignup {
  userId: string;
  fullName: string | null;
  userType: "buyer" | "seller";
  status: string;
  createdAt: string;
  mobile: string | null;
}

export interface UserRow {
  userId: string;
  fullName: string | null;
  userType: "buyer" | "seller";
  status: string;
  stage: string;
  mobile: string | null;
  email: string | null;
  state: string | null;
  createdAt: string;
}

export interface UsersListOut {
  total: number;
  items: UserRow[];
}

export interface UserDetail {
  userId: string;
  userType: "buyer" | "seller";
  status: string;
  stage: string;
  createdAt: string;
  updatedAt: string;
  mobile: string | null;
  hasBuyerData: boolean;
  hasSellerData: boolean;
  buyer: Record<string, string | null> | null;
  seller: Record<string, string | null> | null;
  bank: Record<string, string | null> | null;
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
  recent: (limit = 8) =>
    req<RecentSignup[]>(`/admin/dashboard/recent?limit=${limit}`),
  users: (params: {
    type?: "buyer" | "seller";
    status?: string;
    q?: string;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params.type) qs.set("type", params.type);
    if (params.status) qs.set("status", params.status);
    if (params.q) qs.set("q", params.q);
    qs.set("limit", String(params.limit ?? 50));
    qs.set("offset", String(params.offset ?? 0));
    return req<UsersListOut>(`/admin/users?${qs}`);
  },
  user: (id: string) => req<UserDetail>(`/admin/users/${id}`),
  updateUser: (
    id: string,
    patch: {
      buyer?: Record<string, string | null>;
      seller?: Record<string, string | null>;
      bank?: Record<string, string | null>;
    },
  ) =>
    req<UserDetail>(`/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
};
