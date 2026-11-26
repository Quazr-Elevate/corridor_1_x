/**
 * Requests for quotation, quotes and offers (M3). Prices are integers in the
 * currency's minor unit, per unit, exactly as the API sends them: format with
 * `money()` and never do float arithmetic on them.
 */
import { API_BASE, ApiError } from "@/lib/api";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (body as { detail?: unknown }).detail;
    throw new ApiError(typeof detail === "string" ? detail : "Something went wrong. Try again.", res.status);
  }
  return body as T;
}

export type PaymentTerms = "advance" | "lc_sight" | "lc_usance" | "advance_balance_docs" | "open_account";
export const PAYMENT_TERMS: ReadonlyArray<{ value: PaymentTerms; label: string }> = [
  { value: "advance", label: "Advance payment" },
  { value: "lc_sight", label: "Letter of credit at sight" },
  { value: "lc_usance", label: "Usance letter of credit" },
  { value: "advance_balance_docs", label: "Advance, balance against documents" },
  { value: "open_account", label: "Open account" },
];
export const paymentLabel = (v: string) => PAYMENT_TERMS.find((t) => t.value === v)?.label ?? v;
export const INCOTERMS = ["EXW", "FOB", "CIF", "CFR", "DAP", "DDP"] as const;
export const DEAL_CURRENCIES = ["INR", "AED", "USD"] as const;

/** A minor-unit amount as money: 7200000 INR → ₹72,000.00. */
export function money(minor: number | null | undefined, currency: string | null | undefined): string {
  if (minor == null || !currency) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 2 }).format(minor / 100);
}

/** "72000" or "72000.50" typed by a person → minor units, or null when it is not a price. */
export function toMinor(input: string): number | null {
  const clean = input.replace(/,/g, "").trim();
  if (!/^\d+(\.\d{1,2})?$/.test(clean)) return null;
  const [whole, frac = ""] = clean.split(".");
  return Number(whole) * 100 + Number(frac.padEnd(2, "0"));
}

export const fromMinor = (minor: number | null | undefined): string => (minor == null ? "" : (minor / 100).toString());

export interface SpecLimit {
  parameterId: string;
  code: string;
  name: string;
  unit: string | null;
  value: string;
  operator: "MIN" | "MAX" | "EQ";
}

/** What a matched seller reads. No target price and no buyer name. */
export interface RfqSellerView {
  id: string;
  dealCode: string | null;
  buyerCode: string | null;
  buyerCountry: string | null;
  category: string;
  productName: string;
  variety: string | null;
  grade: string | null;
  specs: SpecLimit[];
  quantity: string | null;
  unit: string;
  packaging: string | null;
  certificates: { certificateTypeId: string; name: string }[];
  incoterms: string[];
  paymentTerms: PaymentTerms | null;
  deliveryCountry: string | null;
  destinationPort: string | null;
  deliveryFrom: string | null;
  deliveryTo: string | null;
  notes: string | null;
  expiresAt: string | null;
}

export type RfqTracking = "draft" | "awaiting" | "quoted" | "expired" | "rejected" | "unmatched" | "cancelled";

export interface Rfq extends RfqSellerView {
  kind: "listing" | "open";
  listingId: string | null;
  status: string;
  tracking: RfqTracking;
  targetPriceMin: number | null;
  targetPriceMax: number | null;
  currency: string | null;
  missing: string[];
  rejectionReason: string | null;
  submittedAt: string | null;
  createdAt: string;
}

export interface RfqInput {
  kind?: "listing" | "open";
  listingId?: string;
  category?: string;
  productName?: string;
  variety?: string | null;
  grade?: string | null;
  specs?: { parameterId: string; value: string; operator?: string }[];
  quantity?: string | null;
  unit?: string;
  packaging?: string | null;
  certificateTypeIds?: string[];
  targetPriceMin?: number | null;
  targetPriceMax?: number | null;
  currency?: string | null;
  incoterms?: string[];
  paymentTerms?: PaymentTerms | null;
  deliveryCountry?: string | null;
  destinationPort?: string | null;
  deliveryFrom?: string | null;
  deliveryTo?: string | null;
  notes?: string | null;
}

export interface MatchedRfqRow {
  id: string;
  category: string;
  productName: string;
  quantity: string | null;
  unit: string;
  deliveryCountry: string | null;
  deliveryTo: string | null;
  expiresAt: string | null;
  opened: boolean;
  openCost: number;
  matchedAt: string | null;
}

export interface SpecAnswer {
  parameterId: string;
  name: string;
  meets: boolean;
  value: string | null;
}

export interface Quote {
  id: string;
  rfqId: string;
  priceMinor: number;
  currency: string;
  quantity: string;
  unit: string;
  incoterm: string;
  portOfLoading: string | null;
  leadTimeDays: number;
  paymentTerms: PaymentTerms[];
  validUntil: string;
  specs: SpecAnswer[];
  notes: string | null;
  editable: boolean;
  updatedAt: string;
}

export interface QuoteInput {
  priceMinor: number;
  currency: string;
  quantity: string;
  unit: string;
  incoterm: string;
  portOfLoading: string | null;
  leadTimeDays: number;
  paymentTerms: PaymentTerms[];
  validUntil: string | null;
  /** The value only: whether it meets the buyer's limit is worked out by the server. */
  specs: { parameterId: string; value: string | null }[];
  notes: string | null;
}

/** An offer. The second block is null until the buyer unlocks it. */
export interface Offer {
  id: string;
  sellerCode: string | null;
  sellerState: string | null;
  incoterm: string;
  leadTimeDays: number;
  specsMet: number;
  specsTotal: number;
  validUntil: string;
  status: "published" | "expired" | "withdrawn" | "not_chosen";
  unlocked: boolean;
  unlockCost: number;
  priceMinor: number | null;
  currency: string | null;
  quantity: string | null;
  unit: string | null;
  portOfLoading: string | null;
  paymentTerms: PaymentTerms[] | null;
}

/** One line of a deal's chat as this side sees it (A-074). */
export interface ChatMessage {
  id: string;
  /** you · the other side (by company code) · Corridor One X · an event line */
  author: "you" | "counterparty" | "corridor" | "system";
  senderCode: string | null;
  body: string;
  /** held: waiting for Corridor One X; rejected: not passed on (see note) */
  status: "delivered" | "held" | "rejected";
  note: string | null;
  createdAt: string;
}

export interface DealChat {
  dealCode: string;
  dealStatus: string;
  side: "buyer" | "seller";
  counterpartyCode: string | null;
  canWrite: boolean;
  suspended: boolean;
  messages: ChatMessage[];
}

/** A counter-offer as one side sees it (CX-101): always in that side's own currency. */
export interface Counter {
  id: string;
  /** false: the other side's, passed on by Corridor One X */
  mine: boolean;
  priceMinor: number;
  currency: string;
  quantity: string | null;
  note: string | null;
  status: "pending_desk" | "relayed" | "accepted" | "declined" | "rejected" | "superseded";
  decisionNote: string | null;
  createdAt: string;
}

export const trade = {
  listRfqs: () => call<{ total: number; items: Rfq[] }>("/rfqs"),
  getRfq: (id: string) => call<Rfq>(`/rfqs/${id}`),
  createRfq: (body: RfqInput) => call<Rfq>("/rfqs", { method: "POST", body: JSON.stringify(body) }),
  updateRfq: (id: string, body: RfqInput) => call<Rfq>(`/rfqs/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteRfq: (id: string) => call<void>(`/rfqs/${id}`, { method: "DELETE" }),
  submitRfq: (id: string) => call<Rfq>(`/rfqs/${id}/submit`, { method: "POST" }),
  sellerPreview: (id: string) => call<RfqSellerView>(`/rfqs/${id}/seller-preview`),
  listOffers: (rfqId: string) => call<{ total: number; items: Offer[] }>(`/rfqs/${rfqId}/offers`),
  unlockOffer: (offerId: string) => call<Offer>(`/offers/${offerId}/unlock`, { method: "POST" }),
  chooseOffer: (dealCode: string, offerId: string) =>
    call<{ dealCode: string; dealStatus: string; chosenOfferId: string }>(`/deals/${dealCode}/choose`, {
      method: "POST",
      body: JSON.stringify({ offerId }),
    }),
  /** 404 until an offer is chosen on the deal, and for anyone outside it. */
  dealChat: (dealCode: string) => call<DealChat>(`/deals/${dealCode}/chat`),
  listCounters: (dealCode: string) => call<{ items: Counter[] }>(`/deals/${dealCode}/counters`).then((r) => r.items),
  proposeCounter: (dealCode: string, body: { priceMinor: number; quantity?: string | null; note?: string | null }) =>
    call<Counter>(`/deals/${dealCode}/counters`, { method: "POST", body: JSON.stringify(body) }),
  answerCounter: (dealCode: string, counterId: string, accept: boolean) =>
    call<Counter>(`/deals/${dealCode}/counters/${counterId}/answer`, { method: "POST", body: JSON.stringify({ accept }) }),
  sendDealMessage: (dealCode: string, body: string) =>
    call<ChatMessage>(`/deals/${dealCode}/chat`, { method: "POST", body: JSON.stringify({ body }) }),

  listMatched: () => call<{ total: number; items: MatchedRfqRow[] }>("/matched-rfqs"),
  openMatched: (rfqId: string) => call<RfqSellerView>(`/matched-rfqs/${rfqId}/open`, { method: "POST" }),
  getQuote: (rfqId: string) => call<Quote>(`/matched-rfqs/${rfqId}/quote`),
  saveQuote: (rfqId: string, body: QuoteInput) =>
    call<Quote>(`/matched-rfqs/${rfqId}/quote`, { method: "PUT", body: JSON.stringify(body) }),
};
