/**
 * The catalogue of certifications a Cor1x user can attach to their account.
 *
 * Cor1x is a global agri import/export marketplace, so the list focuses on:
 *   - Business identity (globally relevant registrations)
 *   - Import / export paperwork
 *   - Food & agri product certifications
 *   - Quality, food safety, organic, and religious / dietary certifications
 *
 * Tax IDs (PAN, SSN, VAT number) are NOT here — they're numeric identifiers,
 * not documents a user uploads for verification. Hyper-local municipal
 * licences (shop & establishment, state-level trade licence) are also out:
 * most of our users won't carry them, and the ones who do upload something
 * similar can type a free-form name and we store it verbatim.
 *
 * Keep the list ordered by rough frequency within each group so the common
 * picks surface first when the user searches.
 */
export const CERTIFICATION_CATALOGUE: string[] = [
  // ─── Business identity ──────────────────────────────────────────
  "Certificate of Incorporation",
  "Business Registration Certificate",
  "Partnership Deed",
  "LLP Agreement",
  "Trade License",
  "Udyam / MSME Registration",

  // ─── Import / export paperwork ─────────────────────────────────
  "IEC — Import Export Code",
  "Export License",
  "Import License",
  "Customs Registration",
  "EORI Number (EU / UK)",
  "AD Code Letter (bank)",
  "RCMC — Registration-cum-Membership Certificate",
  "APEDA Registration (agri exports)",
  "DGFT Status Holder Certificate",

  // ─── Food & agri product certifications ────────────────────────
  "FSSAI License (manufacturing)",
  "FSSAI License (trader / distributor)",
  "FSSAI Basic Registration",
  "Phytosanitary Certificate",
  "Certificate of Origin",
  "Fumigation Certificate",
  "Health Certificate",
  "Spices Board Registration",
  "Tea Board Registration",
  "Coffee Board Registration",
  "Coconut Development Board Registration",
  "MPEDA Registration (marine products)",
  "Legal Metrology Certificate",

  // ─── Quality & food safety ─────────────────────────────────────
  "ISO 9001 — Quality Management",
  "ISO 22000 — Food Safety Management",
  "ISO 14001 — Environmental Management",
  "HACCP Certificate",
  "GMP — Good Manufacturing Practice",
  "BRC Food Safety",
  "SQF — Safe Quality Food",
  "IFS — International Featured Standards",
  "GlobalG.A.P.",

  // ─── Organic & sustainability ──────────────────────────────────
  "India Organic (NPOP)",
  "USDA Organic (NOP)",
  "EU Organic",
  "JAS Organic (Japan)",
  "Rainforest Alliance",
  "Fair Trade Certified",
  "UTZ Certified",
  "Non-GMO Project Verified",

  // ─── Religious / dietary ───────────────────────────────────────
  "Halal Certificate",
  "Kosher Certificate",
  "Vegan Certified",

  // ─── Product paperwork ─────────────────────────────────────────
  "Certificate of Analysis (COA)",
  "Trademark Registration",

  // ─── Escape hatch ──────────────────────────────────────────────
  "Other",
];
