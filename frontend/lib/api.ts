// ── Shared response shapes ─────────────────────────────────────────────

export interface Completion {
  primary: boolean;
  business: boolean;
  bank: boolean;
}

export interface PrimaryData {
  fullName?: string | null;
  phone?: string | null;
  department?: string | null;
  position?: string | null;
  addressLine?: string | null;
  city?: string | null;
  state?: string | null;
  pincode?: string | null;
  country?: string | null;
  websiteUrl?: string | null;
  googleBusinessUrl?: string | null;
  facebookUrl?: string | null;
}

export interface BusinessData {
  // Company info
  legalName?: string | null;
  industry?: string | null;
  operatingCountries?: string[] | null;
  websiteUrl?: string | null;
  // Business profile
  tradePosition?: string | null;
  sellerType?: string | null;
  businessRole?: string | null;
  exportStatus?: string | null;
  targetMarkets?: string[] | null;
  targetBuyerTypes?: string[] | null;
  mainObjective?: string | null;
  companyIntroduction?: string | null;
  // Free-text extras
  businessType?: string | null;
  natureOfBusiness?: string | null;
  udyam?: string | null;
}

export interface BankData {
  accountNumber?: string | null;
  ifsc?: string | null;
  ifscVerifiedAt?: string | null;
  holderName?: string | null;
  branchName?: string | null;
  bankName?: string | null;
}

// Mirrors the server's UserStatus enum. "pending_verification" lands
// here between "active" and "verified": the user has filled all seven
// mandatory profile fields and is waiting on an admin decision.
export type VerificationStatus =
  | "signed_up"
  | "email_verified"
  | "active"
  | "pending_verification"
  | "verified"
  | "rejected";

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
}

export interface Me {
  userId: string;
  email: string;
  emailVerifiedAt: string | null;
  businessName: string | null;
  userType: "buyer" | "seller";
  status: string;
  /** True until the user replaces their temp credential with a real password. */
  mustChangePassword: boolean;
  completion: Completion;
  verification: VerificationState;
  primary: PrimaryData;
  business: BusinessData;
  bank: BankData;
}

export interface RevealedContact {
  sellerId: string;
  fullName: string | null;
  businessName: string | null;
  businessType: string | null;
  email: string | null;
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

// ── Auth flow shapes ───────────────────────────────────────────────────

export interface SignupResponse {
  email: string;
  message: string;
  /**
   * Only populated when the backend is running with debug=true — the
   * literal temp password that was emailed, and the magic-login URL.
   * Lets the "check your inbox" screen show both without the user
   * having to open the .eml file. Never present in production.
   */
  devTempPassword?: string | null;
  devMagicUrl?: string | null;
}

export interface LoginResponse {
  userId: string;
  email: string;
  businessName: string | null;
  // True when the login used the temp credential. The frontend must
  // route the user to /dashboard/settings/password and gate every
  // other protected page behind it until a real password is set.
  mustChangePassword: boolean;
}

// ── Onboarding wizard shapes ───────────────────────────────────────────

export interface OnboardingStatus {
  companyInfoDone: boolean;
  primaryContactDone: boolean;
  businessProfileDone: boolean;
  onboardedAt: string | null;
}

export interface CompanyInfoIn {
  legalName: string;
  industry: string;
  operatingCountries: string[];
  websiteUrl?: string;
}

export interface PrimaryContactIn {
  fullName: string;
  phone?: string;
  department?: string;
  position?: string;
}

export interface BusinessProfileIn {
  tradePosition: string;
  sellerType?: string;
  businessRole?: string;
  exportStatus?: string;
  targetMarkets: string[];
  targetBuyerTypes: string[];
  mainObjective?: string;
  companyIntroduction?: string;
}

// ── HTTP helper ────────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
const USER_ID_KEY = "cor1x.userId";
const SESSION_EXPIRES_KEY = "cor1x.sessionExpiresAt";
export const SESSION_TTL_MS = 24 * 60 * 60 * 1000;

export function getStoredUserId(): string | null {
  if (typeof window === "undefined") return null;
  const uid = window.localStorage.getItem(USER_ID_KEY);
  if (!uid) return null;
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

/** Prepend API base to a relative photo URL like `/uploads/products/xxx.jpg`. */
export function photoUrl(rel: string): string {
  if (!rel) return rel;
  if (rel.startsWith("http")) return rel;
  return `${API_BASE}${rel}`;
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const userId = getStoredUserId();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(userId ? { "X-User-Id": userId } : {}),
      ...(init?.headers ?? {}),
    },
  });
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
  // ─── Auth ───
  signup: (payload: {
    email: string;
    firstName: string;
    lastName: string;
    countryOfResidence: string;
  }) =>
    jsonFetch<SignupResponse>("/auth/signup", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  signupResend: (email: string) =>
    jsonFetch<SignupResponse>("/auth/signup/resend", {
      method: "POST",
      body: JSON.stringify({ email }),
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

  // ─── Field-verify (still needed for IFSC) ───
  lookupPincode: (pincode: string) => jsonFetch<PincodeLookup>(`/pincode/${pincode}`),
  lookupIfsc: (ifsc: string) => jsonFetch<IfscLookup>(`/ifsc/${ifsc}`),

  // ─── Me ───
  me: () => jsonFetch<Me>("/me"),
  deleteMe: () => jsonFetch<void>("/me", { method: "DELETE" }),

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

  // ─── Verification docs ───
  submitForVerification: () =>
    jsonFetch<VerificationState>("/me/submit-verification", {
      method: "POST",
    }),
  listVerificationDocs: () =>
    jsonFetch<VerificationDoc[]>("/me/verification-docs"),
  uploadVerificationDoc: async (
    certType: string,
    file: File,
  ): Promise<VerificationDoc> => {
    const userId = getStoredUserId();
    const form = new FormData();
    form.append("cert_type", certType);
    form.append("file", file);
    const res = await fetch(`${API_BASE}/me/verification-docs`, {
      method: "POST",
      body: form,
      credentials: "include",
      headers: userId ? { "X-User-Id": userId } : {},
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg =
        (body as { detail?: string }).detail || `Upload failed (${res.status})`;
      throw new Error(msg);
    }
    return body as VerificationDoc;
  },
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
  uploadProductPhoto: async (file: File): Promise<{ url: string }> => {
    const userId = getStoredUserId();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/products/upload-photo`, {
      method: "POST",
      body: form,
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
