/**
 * Listing completeness — computed from the real fields of a lot, the way
 * the reference "Profile 72%" bar reads on listing cards. No hidden
 * signals: every point maps to something the seller can add.
 *
 * Server-safe (no "use client").
 */

type Num = string | number | null | undefined;

export interface LotFields {
  name?: string | null;
  category?: string | null;
  variety?: string | null;
  originState?: string | null;
  packaging?: string | null;
  quantity?: Num;
  moq?: Num;
  pricePerUnit?: Num;
  description?: string | null;
  photos?: ReadonlyArray<string> | null;
}

export interface Completeness {
  /** 0–100. */
  score: number;
  /** What's missing, most valuable first (phrases for a sentence). */
  missing: string[];
  /** One line: what to add next, or that the lot is complete. */
  hint: string;
}

/** Photos beyond this many stop adding points. */
export const FULL_PHOTO_COUNT = 3;

const has = (v: Num) => v !== null && v !== undefined && String(v).trim() !== "";

/**
 * Weights (sum 100): name + category 20 (always there once published),
 * one photo 15 + three photos 10, description 15, price 8, volume 8,
 * origin 6, grade 6, minimum order 6, packing 6.
 */
export function lotCompleteness(p: LotFields): Completeness {
  const photos = p.photos?.length ?? 0;
  const parts: Array<{ ok: boolean; points: number; phrase: string }> = [
    { ok: has(p.name), points: 10, phrase: "a name" },
    { ok: has(p.category), points: 10, phrase: "a category" },
    { ok: photos >= 1, points: 15, phrase: "a photo" },
    { ok: has(p.description), points: 15, phrase: "a description" },
    { ok: photos >= FULL_PHOTO_COUNT, points: 10, phrase: photos ? "more photos" : "" },
    { ok: has(p.pricePerUnit), points: 8, phrase: "your price" },
    { ok: has(p.quantity), points: 8, phrase: "the volume" },
    { ok: has(p.originState), points: 6, phrase: "the origin state" },
    { ok: has(p.variety), points: 6, phrase: "the grade" },
    { ok: has(p.moq), points: 6, phrase: "a minimum order" },
    { ok: has(p.packaging), points: 6, phrase: "the packing" },
  ];
  const score = parts.reduce((n, x) => n + (x.ok ? x.points : 0), 0);
  const missing = parts.filter((x) => !x.ok && x.phrase).map((x) => x.phrase);
  const next = missing.slice(0, 2);
  const hint = next.length
    ? `Add ${next.join(" and ")} so buyers find and trust it.`
    : "Complete — buyers see everything they usually ask for.";
  return { score, missing, hint };
}
