/**
 * Seeding helpers for the frontend E2E suite.
 *
 * The browser specs are about the UI, so anything that is *setup* rather
 * than the thing under test (a verified seller with a lot in the market,
 * say) is created straight through the backend API with an out-of-browser
 * request context. It is the same API the UI calls.
 */
import { APIRequestContext, expect, request } from "@playwright/test";

export const API_URL = process.env.E2E_API_URL || "http://127.0.0.1:8001";
export const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "admin@cor1x.test";
export const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "admin-pass-123";

export const PASSWORD = "Sup3r-secret!";

/** A work email nobody else in the run uses (free-mail is refused). */
export function workEmail(prefix: string, domain = "kaverifoods.in"): string {
  const tag = Math.random().toString(36).slice(2, 10);
  return `${prefix}-${tag}@${domain}`;
}

/** Unique-per-run digits, for GSTIN / PAN / phone numbers. */
function serial(): string {
  return String(Math.floor(Math.random() * 9000) + 1000);
}

/** Legal names are unique across live businesses, so never reuse one. */
function companyName(): string {
  return `Kaveri Foods ${Math.random().toString(36).slice(2, 8).toUpperCase()} Pvt Ltd`;
}

/**
 * A lot name no other scenario uses.
 *
 * The suite shares one backend database, so listings pile up across tests.
 * Naming each lot uniquely keeps "exactly one result" assertions honest
 * without resetting the database between tests.
 */
export function lotName(prefix: string): string {
  return `${prefix} ${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
}

export async function apiContext(): Promise<APIRequestContext> {
  // No Origin header, so the backend's CSRF guard lets these through.
  return request.newContext({ baseURL: API_URL });
}

export interface SeededTrader {
  api: APIRequestContext;
  email: string;
  /** The registered legal name — how the ops console lists this business. */
  company: string;
  password: string;
  userId: string;
  businessId: string;
}

/** Signup → verified email → password. Ends signed in (cookie on `api`). */
export async function seedTrader(prefix: string, opts: { companyName?: string } = {}): Promise<SeededTrader> {
  const api = await apiContext();
  const email = workEmail(prefix);
  const company = opts.companyName || companyName();

  const codeRes = await api.post("/auth/signup/code", { data: { email } });
  expect(codeRes.ok(), `signup/code: ${await codeRes.text()}`).toBeTruthy();
  const { devCode } = await codeRes.json();
  expect(devCode, "the backend must run with DEBUG=true so tests can read the code").toBeTruthy();

  const verify = await api.post("/auth/signup/verify", { data: { email, code: devCode } });
  expect(verify.ok(), `signup/verify: ${await verify.text()}`).toBeTruthy();

  const complete = await api.post("/auth/signup/complete", {
    data: {
      email,
      fullName: "Asha Rao",
      companyName: company,
      password: PASSWORD,
      acceptTerms: true,
    },
  });
  expect(complete.ok(), `signup/complete: ${await complete.text()}`).toBeTruthy();
  const body = await complete.json();
  return { api, email, company, password: PASSWORD, userId: body.userId, businessId: body.businessId };
}

/** Fill every mandatory Passport field and required Indian KYB document. */
export async function fillPassport(t: SeededTrader): Promise<void> {
  const n = serial();
  const company = await t.api.post("/onboarding/company", {
    data: {
      legalName: t.company,
      industry: "Rice",
      operatingCountries: ["IN"],
      addressLine: `${n} Market Road`,
      city: "Karnal",
      country: "IN",
    },
  });
  expect(company.ok(), await company.text()).toBeTruthy();

  const contact = await t.api.post("/onboarding/contact", {
    data: { fullName: "Asha Rao", phone: `+91 98765 ${n}1`, position: "Director" },
  });
  expect(contact.ok(), await contact.text()).toBeTruthy();

  const profile = await t.api.post("/onboarding/business", { data: { tradePosition: "both" } });
  expect(profile.ok(), await profile.text()).toBeTruthy();

  const types: Array<{ code: string; id: string }> = await (await t.api.get("/kyb/document-types")).json();
  const byCode = Object.fromEntries(types.map((x) => [x.code, x.id]));
  for (const [code, value] of [
    ["gstin", `22AAAAA${n}A1Z5`],
    ["pan", `AAAAA${n}A`],
  ] as const) {
    const res = await t.api.post("/me/verification-docs", {
      multipart: { documentTypeId: byCode[code], value },
    });
    expect(res.ok(), `${code}: ${await res.text()}`).toBeTruthy();
  }
}

export async function submitForVerification(t: SeededTrader): Promise<void> {
  const res = await t.api.post("/me/submit-verification");
  expect(res.ok(), await res.text()).toBeTruthy();
}

export async function adminContext(): Promise<APIRequestContext> {
  const api = await apiContext();
  const res = await api.post("/admin/login", { data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD } });
  expect(res.ok(), `admin/login: ${await res.text()}`).toBeTruthy();
  return api;
}

export async function adminVerify(userId: string): Promise<void> {
  const admin = await adminContext();
  const res = await admin.post(`/admin/users/${userId}/verify`);
  expect(res.ok(), await res.text()).toBeTruthy();
  await admin.dispose();
}

export async function adminReject(userId: string, reason = "Address does not match the licence."): Promise<void> {
  const admin = await adminContext();
  const res = await admin.post(`/admin/users/${userId}/reject`, {
    data: { reason, failedItems: ["addressLine"] },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  await admin.dispose();
}

/** A fully verified business, ready to list or to buy. */
export async function seedVerifiedTrader(prefix: string): Promise<SeededTrader> {
  const t = await seedTrader(prefix);
  await fillPassport(t);
  await submitForVerification(t);
  await adminVerify(t.userId);
  return t;
}

/** A 4×4 PNG — real image bytes, which the backend sniffs for. */
const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAFElEQVR4nGP8z8DAwMDAxMDAwAAADAoBAV0P2kcAAAAASUVORK5CYII=",
  "base64",
);

export interface SeededLot {
  id: string;
  name: string;
}

/** Publish one listing for a verified business. */
export async function seedLot(t: SeededTrader, over: Record<string, unknown> = {}): Promise<SeededLot> {
  const upload = await t.api.post("/products/upload-photo", {
    multipart: { file: { name: "lot.png", mimeType: "image/png", buffer: TINY_PNG } },
  });
  expect(upload.ok(), `upload-photo: ${await upload.text()}`).toBeTruthy();
  const { url } = await upload.json();

  const res = await t.api.post("/products", {
    data: {
      name: "1121 Steam Basmati",
      category: "Rice",
      variety: "1121",
      originState: "Haryana",
      packaging: "Jute",
      quantity: "500",
      unit: "MT",
      moq: "25",
      pricePerUnit: "72.50",
      currency: "INR",
      description: "Aromatic long grain, sortex clean.",
      photos: [url],
      ...over,
    },
  });
  expect(res.ok(), `products: ${await res.text()}`).toBeTruthy();
  const lot = await res.json();
  return { id: lot.id, name: lot.name };
}
