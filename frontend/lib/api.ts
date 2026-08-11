export interface GstinLookup {
  gstin: string;
  legalName: string;
  tradeName?: string;
  pan: string;
  businessType: string;
  natureOfBusiness?: string;
  /** Masked mobile from GST-linked OTP providers. Empty on Day-1 (user enters own). */
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

// Base URL for the FastAPI backend. Set NEXT_PUBLIC_API_BASE_URL in .env.local.
// Default targets the local uvicorn dev server.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
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
  lookupGstin: (gstin: string) => jsonFetch<GstinLookup>(`/gstin/${gstin}`),
  lookupPan: (pan: string) => jsonFetch<PanLookup>(`/pan/${pan}`),
  lookupPincode: (pincode: string) => jsonFetch<PincodeLookup>(`/pincode/${pincode}`),
  sendOtp: (payload: { channel: "phone" | "email"; value: string; purpose: "gstin" | "phone" }) =>
    jsonFetch<OtpSendResponse>("/otp/send", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  verifyOtp: (payload: { otpId: string; code: string; mobile: string }) =>
    jsonFetch<OtpVerifyResponse>("/otp/verify", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  submitSeller: (payload: unknown) =>
    jsonFetch<{ id: string; status: string }>("/sellers", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
