export interface GstinLookup {
  gstin: string;
  legalName: string;
  tradeName?: string;
  pan: string;
  businessType: string;
  natureOfBusiness?: string;
  maskedMobile: string;
  address: {
    building?: string;
    city: string;
    district?: string;
    state: string;
    pincode: string;
  };
}

export interface PanLookup {
  pan: string;
  name: string;
}

export interface OtpSendResponse {
  otpId: string;
  destination: string;
  expiresInSec: number;
  devHint?: string;
}

export interface OtpVerifyResponse {
  ok: boolean;
  error?: string;
}

export interface PincodeLookup {
  pincode: string;
  city: string;
  district?: string;
  state: string;
}

// ── Dashboard shapes ────────────────────────────────────────────────────────

export interface Completion {
  primary: boolean;
  business: boolean;
  bank: boolean;
  seller: boolean;
}

export interface PrimaryData {
  fullName?: string | null;
  email?: string | null;
  emailVerifiedAt?: string | null;
  addressLine?: string | null;
  city?: string | null;
  state?: string | null;
  pincode?: string | null;
  altMobile?: string | null;
  altMobileVerifiedAt?: string | null;
  altEmail?: string | null;
  altEmailVerifiedAt?: string | null;
  businessEmail?: string | null;
  businessEmailVerifiedAt?: string | null;
  websiteUrl?: string | null;
  googleBusinessUrl?: string | null;
  facebookUrl?: string | null;
}

export interface BusinessData {
  gstin?: string | null;
  gstinVerifiedAt?: string | null;
  pan?: string | null;
  panVerifiedAt?: string | null;
  companyName?: string | null;
}

export interface BankData {
  accountNumber?: string | null;
  ifsc?: string | null;
  ifscVerifiedAt?: string | null;
  holderName?: string | null;
  branchName?: string | null;
  bankName?: string | null;
}

export interface SellerData {
  udyam?: string | null;
  aadhaar?: string | null;
  tan?: string | null;
}

export interface Me {
  userId: string;
  userType: "buyer" | "seller";
  status: string;
  mobile: string;
  fullName: string | null;
  completion: Completion;
  primary: PrimaryData;
  business: BusinessData;
  bank: BankData;
  seller: SellerData;
}

export interface OtpVerifyResponse {
  ok: boolean;
  error?: string;
  // Phone-channel verify only. See routers/otp.py.
  isNew?: boolean;
  userId?: string;
}

export interface RevealedContact {
  sellerId: string;
  fullName: string | null;
  companyName: string | null;
  businessType: string | null;
  mobile: string | null;
  email: string | null;
  businessEmail: string | null;
  addressLine: string | null;
  city: string | null;
  state: string | null;
  pincode: string | null;
  country: string | null;
  websiteUrl: string | null;
  revealedAt: string;
}

export interface IfscLookup {
  ifsc: string;
  bank: string;
  branch: string;
  city?: string;
  state?: string;
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
}

/** Prepend API base to a relative photo URL like `/uploads/products/xxx.jpg`. */
export function photoUrl(rel: string): string {
  if (!rel) return rel;
  if (rel.startsWith("http")) return rel;
  return `${API_BASE}${rel}`;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
const USER_ID_KEY = "cor1x.userId";
const SESSION_EXPIRES_KEY = "cor1x.sessionExpiresAt";
export const SESSION_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

export function getStoredUserId(): string | null {
  if (typeof window === "undefined") return null;
  const uid = window.localStorage.getItem(USER_ID_KEY);
  if (!uid) return null;
  // If we recorded an expiry and it's in the past, treat the session as gone.
  const expStr = window.localStorage.getItem(SESSION_EXPIRES_KEY);
  if (expStr) {
    const exp = Number(expStr);
    if (Number.isFinite(exp) && Date.now() >= exp) {
      clearUserId();
      return null;
    }
  }
  return uid;
}

export function storeUserId(id: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(USER_ID_KEY, id);
  window.localStorage.setItem(
    SESSION_EXPIRES_KEY,
    String(Date.now() + SESSION_TTL_MS),
  );
}

export function clearUserId() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(USER_ID_KEY);
  window.localStorage.removeItem(SESSION_EXPIRES_KEY);
}

export function sessionExpiresAt(): number | null {
  if (typeof window === "undefined") return null;
  const s = window.localStorage.getItem(SESSION_EXPIRES_KEY);
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const userId = getStoredUserId();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    // Include cookies so cor1x_session (login/signup) + cor1x_verified_phone
    // (signup bridge) flow with every call. Requires CORS allow_credentials
    // + a concrete origin (not *) on the backend — already set.
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      // Legacy header — kept while pulled dashboard code still reads
      // userId from localStorage. Cookie auth takes precedence on backend.
      ...(userId ? { "X-User-Id": userId } : {}),
      ...(init?.headers ?? {}),
    },
  });
  // 204 No Content (e.g. DELETE /me) has no body to parse.
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg =
      (body as { error?: string; detail?: string })?.error ||
      (body as { detail?: string })?.detail ||
      `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return body as T;
}

export const api = {
  // Public (no auth header needed, but harmless if sent)
  lookupGstin: (gstin: string) => jsonFetch<GstinLookup>(`/gstin/${gstin}`),
  lookupPan: (pan: string) => jsonFetch<PanLookup>(`/pan/${pan}`),
  lookupPincode: (pincode: string) => jsonFetch<PincodeLookup>(`/pincode/${pincode}`),
  lookupIfsc: (ifsc: string) => jsonFetch<IfscLookup>(`/ifsc/${ifsc}`),
  sendOtp: (payload: {
    channel: "phone" | "email";
    value: string;
    purpose: "gstin" | "phone" | "email";
    // 'signup' → 409 if mobile already registered; 'login' → 409 if not.
    // Prevents burning an SMS on a mobile whose state doesn't match intent.
    mode?: "signup" | "login";
  }) =>
    jsonFetch<OtpSendResponse>("/otp/send", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  // Phone-channel /otp/verify sets one of two cookies on success:
  //   isNew=false → cor1x_session (login done, dashboard-ready)
  //   isNew=true  → cor1x_verified_phone (10-min bridge to /auth/signup)
  verifyOtp: (payload: {
    otpId: string;
    code: string;
    channel?: "phone" | "email";
    mobile?: string;
    email?: string;
    mode?: "signup" | "login";
  }) =>
    jsonFetch<OtpVerifyResponse>("/otp/verify", {
      method: "POST",
      body: JSON.stringify({ channel: "phone", ...payload }),
    }),

  // Complete signup — reads the cor1x_verified_phone cookie set moments
  // ago by /otp/verify, creates User + Identity + Profile atomically,
  // swaps to a durable cor1x_session cookie.
  signup: (payload: {
    fullName: string;
    consent: boolean;
    consentVersion?: string;
  }) =>
    jsonFetch<{ userId: string; isNew: boolean }>("/auth/signup", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Atomic OTP-verify + write for a profile contact field. Server checks
  // the code and stamps *_verified_at in one commit — /profile/primary no
  // longer accepts these fields directly, so this is the only writer.
  verifyContact: (payload: {
    target: "email" | "altMobile" | "altEmail" | "businessEmail";
    value: string;
    code: string;
  }) =>
    jsonFetch<{ ok: boolean; verifiedAt: string }>("/verify/contact", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Atomic Masters India lookup + write for GSTIN. Returns the lookup so
  // the form can auto-fill company_name / business_type / nature.
  verifyGstin: (value: string) =>
    jsonFetch<{ ok: boolean; verifiedAt: string; lookup: GstinLookup }>(
      "/verify/gstin",
      { method: "POST", body: JSON.stringify({ value }) },
    ),

  verifyPan: (value: string) =>
    jsonFetch<{ ok: boolean; verifiedAt: string; pan: string; name: string }>(
      "/verify/pan",
      { method: "POST", body: JSON.stringify({ value }) },
    ),

  verifyIfsc: (value: string) =>
    jsonFetch<{
      ok: boolean;
      verifiedAt: string;
      ifsc: string;
      bank: string;
      branch: string;
    }>("/verify/ifsc", { method: "POST", body: JSON.stringify({ value }) }),

  // Cheap probe used by middleware and page loaders — returns
  // { userId: "..." } if a valid session cookie is present, else null.
  session: () => jsonFetch<{ userId: string | null }>("/auth/session"),

  logout: () =>
    jsonFetch<{ ok: boolean }>("/auth/logout", { method: "POST" }),

  deleteMe: () =>
    jsonFetch<void>("/me", { method: "DELETE" }),

  // Verified-only. Idempotent — second call for the same product returns
  // the same card with the original revealed_at.
  revealContact: (productId: string) =>
    jsonFetch<RevealedContact>(`/products/${productId}/contact-reveal`, {
      method: "POST",
    }),

  // Dashboard — authenticated
  me: () => jsonFetch<Me>("/me"),
  saveProfilePrimary: (payload: unknown) =>
    jsonFetch<{ ok: true }>("/profile/primary", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  saveProfileBusiness: (payload: unknown) =>
    jsonFetch<{ ok: true }>("/profile/business", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  saveProfileBank: (payload: unknown) =>
    jsonFetch<{ ok: true }>("/profile/bank", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  saveProfileSeller: (payload: unknown) =>
    jsonFetch<{ ok: true }>("/profile/seller", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listProducts: () => jsonFetch<ProductRead[]>("/products"),
  createProduct: (payload: unknown) =>
    jsonFetch<ProductRead>("/products", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  uploadProductPhoto: async (file: File): Promise<{ url: string }> => {
    const userId = getStoredUserId();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/products/upload-photo`, {
      method: "POST",
      body: form,
      // Don't set Content-Type — the browser adds the multipart boundary.
      headers: userId ? { "X-User-Id": userId } : {},
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg =
        (body as { detail?: string }).detail || `Upload failed (${res.status})`;
      throw new Error(msg);
    }
    return body as { url: string };
  },
};
