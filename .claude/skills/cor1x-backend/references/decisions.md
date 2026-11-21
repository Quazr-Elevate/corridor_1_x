# Decisions log

What has been decided, what is only proposed, and what is waiting on someone
outside the team. Check here before building anything a standard touches.

- **Adopted**: build to it.
- **Proposed**: the intended direction, not approved. Don't implement it on your
  own initiative. If the user asks for it directly, that request is the
  approval: do it, and move the entry to Adopted with the date and their words.
- **Waiting**: needs an answer from the client, the bank, counsel or a lawyer.
  Don't guess. Build around it the way the entry says.

When a decision is taken, record it here **and** in the tracker row: Status Done
for a *Discuss later* row, the outcome in Notes, and any rows it adds or removes.
If it changes the build plan's scope, say so to the user.

## Adopted

| ID | Decision | Date | Source |
|---|---|---|---|
| A-001 | Four phases: **Now**, **A** build and test, **B** before launch (a release gate), **C** after launch. Same names as `docs/05_security_review.md` | 13 Nov 2026 | User |
| A-002 | 2FA (TOTP) is **Phase B**: not needed for development and testing, mandatory before launch. Build the columns in Phase A (CX-070) | 13 Nov 2026 | User |
| A-003 | Before launch, **sample and test data is removed** from production and real reference data is loaded (CX-135) | 13 Nov 2026 | User confirmed |
| A-004 | Work runs milestone by milestone, M0–M7, in two-week sprints S1–S15, as laid out in the tracker's Roadmap sheet | 13 Nov 2026 | User |
| A-005 | **Every milestone starts with a design review** (schemas, endpoints with input and output, errors, security, tests) that the user approves before code | 13 Nov 2026 | User |
| A-006 | **REST API design and security are maintained in every milestone** (`api-standard.md`, `security.md`) | 13 Nov 2026 | User |
| A-007 | Admin access is deny-by-default: one permission per `/admin` route, enforced by the route-matrix test | 31 Oct 2026 | Built (`0024_identity_access`) |
| A-008 | Sessions: traders 12 h idle / 7 days; admins 30 min idle / 8 h; one active device (traders: superseded by A-044); lockout 5 → 15 min → 30 min → support unlock | 31 Oct 2026 | Built |
| A-009 | KYB values are encrypted in the app, masked to the last 4 in lists, revealed by a separate rate-limited audited call; Aadhaar is never accepted | before 31 Oct 2026 | Built |
| A-010 | Listings keep the API resource name `products` | current code | Convention, to avoid churn |
| A-011 | Every route under `/v1/...` except `/health` (was D-001). Built in M0 | 15 Nov 2026 | User, M0 design review |
| A-012 | One error shape: `{detail, code, fields?}`, including validation errors (was D-002). Built in M0 | 15 Nov 2026 | User, M0 design review |
| A-013 | Unknown request fields are rejected: a `RequestModel` base with `extra="forbid"` → 422 `request.unknown_field` (was D-003). Built in M0; first to move to S2 if the sprint runs short | 15 Nov 2026 | User, M0 design review |
| A-014 | `/docs`, `/redoc`, `/openapi.json` are served only when `DEBUG=true`; the OpenAPI file is a CI artifact (was D-004). Built in M0 | 15 Nov 2026 | User, M0 design review |
| A-015 | `/pincode/{pincode}` and `/ifsc/{code}` require a trader or admin session, are limited to 30/min per principal, and are cached for 24 h (was D-005). Built in M0 | 15 Nov 2026 | User, M0 design review |
| A-016 | CX-062 moves Next.js to the **latest major** release, not the smallest patched one | 15 Nov 2026 | User, M0 design review |
| A-017 | Design reviews happen in the working session; no `docs/milestones/Mx_design.md` file is written. Approved outcomes are recorded here and in the tracker | 15 Nov 2026 | User |
| A-019 | **Sign-up accepts work email only.** Free-mail (Gmail, Yahoo and similar) and disposable domains stay refused; CX-069 is closed without a code change and build plan 1.1 is the part to update | 15 Nov 2026 | User, M1 design review |
| A-020 | CX-066: the console asks for an access reason **once per business** and reuses it; the API requires and stores a reason on every reveal and file open | 15 Nov 2026 | User, M1 design review |
| A-021 | Listings: on a published listing, **price range, price validity, quantity and MOQ change immediately**; any other edit goes back to admin review while the published version stays live | 15 Nov 2026 | User, M1 design review |
| A-022 | The listing **price range is shown to signed-in verified businesses only**; guests and unverified accounts see "Price on request" | 15 Nov 2026 | User, M1 design review |
| A-023 | **Minimum to submit a listing** = the plan's candidate set: name, category, description, grade, origin country and state; MOQ, monthly capacity, lead time; price range, currency, price validity, one incoterm; one photo; the category's required specs and certificates | 15 Nov 2026 | User, M1 design review |
| A-024 | Every list endpoint returns `{items, total}` (was D-006), converted in M1 | 15 Nov 2026 | User, M1 design review |
| A-025 | CX-007 (photography redesign) is done as the last M1 step, after the listing features | 15 Nov 2026 | User, M1 design review |
| A-018 | All milestones are built on **one development branch**; no branch per row or per milestone. A milestone goes to `main` only when it is finished and tested | 15 Nov 2026 | User |
| A-026 | **CX-077 decided: Cor1x is the masked trading desk**, the counterparty on both sides with identities hidden through delivery. Plan sections 05–16 are built; M2–M6 are unblocked | 16 Nov 2026 | User, M2 design review |
| A-027 | CX-137 is still with counsel. Until it is answered the identity vault is built as its own tables in the **same database**, so it can be moved later; hosting stays a Phase B gate | 16 Nov 2026 | User, M2 design review |
| A-028 | **Vault scope:** the company's legal name, address line, city, PIN code, website and social links, and the owner's name, email and phone. State and country stay outside for the market | 16 Nov 2026 | User, M2 design review |
| A-029 | **Company code:** `{ISO2}-{6 random digits}` (e.g. `IN-482913`), issued when the business is verified, stable for life, never reused | 16 Nov 2026 | User, M2 design review |
| A-030 | CX-083: contact reveal is **turned off behind a setting in S4** and its code removed one sprint later; `contact_reveals` rows are kept | 16 Nov 2026 | User, M2 design review |
| A-031 | Credit and plan prices are **configuration an admin can edit**, seeded with marked placeholder values until the client sets them (plan 17.5). Free quota: 10 RFQs per verified company | 16 Nov 2026 | User, M2 design review |
| A-032 | CX-085: the payment processor for plans and top-ups is **Razorpay**, behind a provider interface with a signed test provider | 16 Nov 2026 | User, M2 design review |
| A-033 | M3: the build plan is not in the repository, so the RFQ, quote, cost sheet and offer **fields are proposed in the design review** and approved there before code | 16 Nov 2026 | User, M3 design review |
| A-034 | CX-089: the **whole deal transition table** in `docs/07_development_flow.md` §8 is encoded in M3, with a test per edge; M3 itself uses RFQ_OPEN, QUOTED and CANCELLED | 16 Nov 2026 | User, M3 design review |
| A-035 | CX-092 hard rules: same category, monthly capacity ≥ RFQ quantity, every required spec within the buyer's limit, lead time inside the delivery window. Everything else only ranks | 16 Nov 2026 | User, M3 design review |
| A-036 | CX-094: two roles added in M3, **trade desk** and **desk manager**. The manager approves a below-floor margin and cannot approve their own cost sheet. Quality, finance, logistics and legal arrive with their features | 16 Nov 2026 | User, M3 design review |
| A-037 | CX-096: minimum margin percent and FX buffer percent are **admin-editable settings seeded with marked placeholders** until the client sets them | 16 Nov 2026 | User, M3 design review |
| A-038 | An RFQ the desk rejects, or closes with no match, is **refunded automatically** by a REVERSAL ledger line (credits or the free RFQ) | 16 Nov 2026 | User, M3 design review |
| A-039 | CX-090 sanctions check: an **admin-managed list of held countries**, empty at first; an RFQ touching one goes to a desk hold with the reason. The list's contents come from the client's compliance contact | 16 Nov 2026 | User, M3 design review |
| A-040 | An RFQ stays open **14 days** and a quote is valid **7 days** unless the seller sets a date; both are settings marked as placeholders. An RFQ with no offer at expiry becomes CANCELLED with reason `expired` | 16 Nov 2026 | User, M3 design review |
| A-041 | M3 fields approved as proposed, **plus packaging and required certificates on the RFQ** (16 fields). Quote, cost sheet and offer fields approved as proposed | 16 Nov 2026 | User, M3 design review |
| A-042 | A locked offer shows lead time, incoterm and specs met; **the price and terms open with OFFER_UNLOCK**. The purchase price never reaches a buyer | 16 Nov 2026 | User, M3 design review |
| A-043 | CX-149 (user name, email and phone into the vault) is **approved for M3**. It is built after the offer flow, with its own design note, because it changes sign-in | 16 Nov 2026 | User, M3 design review |
| A-044 | **Traders keep up to 5 sessions** per login; the 6th sign-in signs out the oldest. Admins stay at one. Settings lists devices with sign-out per device. Replaces the one-device part of A-008 (CX-155) | 21 Nov 2026 | User, M0–M3 walkthrough review |
| A-045 | A password reset by emailed code **also clears the support lock**: the code proves control of the email (CX-156) | 21 Nov 2026 | User, M0–M3 walkthrough review |
| A-046 | Sign-up **does not check the company name**; a duplicate name is a flag in the KYB review queue instead (CX-157) | 21 Nov 2026 | User, M0–M3 walkthrough review |
| A-047 | Cross-checks between KYB documents are **admin-defined rules per country** ('characters x–y of document A equal document B'), not code. India ships with GSTIN 3–12 = PAN (CX-158) | 21 Nov 2026 | User, M0–M3 walkthrough review |
| A-048 | Duplicate refusals are **neutral**: they say the value can't be used, never that another business holds it (CX-159) | 21 Nov 2026 | User, M0–M3 walkthrough review |
| A-049 | Specification templates and required documents for Sugar, Wheat, Oilseeds, Cotton, Millets, Tea, Coffee and Other **approved as drafted** in the review; required documents are set **per category** (CX-164) | 21 Nov 2026 | User, M0–M3 walkthrough review |
| A-050 | **Only verified companies can buy credits** (CX-172) | 21 Nov 2026 | User, M0–M3 walkthrough review |
| A-051 | **Plan credits expire** at the end of the plan; top-up credits do not (CX-173) | 21 Nov 2026 | User, M0–M3 walkthrough review |
| A-052 | The free-RFQ quota is keyed on a **per-country document**: in India each GSTIN is its own company, and a shared PAN only flags related companies in KYB review. Other countries choose their document through configuration (CX-174) | 21 Nov 2026 | User, M0–M3 walkthrough review |
| A-053 | A matched RFQ that **expires with no quote is refunded**; one that had quotes but no offer is not (CX-179) | 21 Nov 2026 | User, M0–M3 walkthrough review |
| A-054 | The KYB **approve button stays disabled until the reviewer has opened every required document** (CX-161) | 21 Nov 2026 | User, M0–M3 walkthrough review |
| A-055 | The **GST check stays manual** for India; no automated registry lookup for now | 21 Nov 2026 | User, M0–M3 walkthrough review |
| A-056 | **PDF metadata is stripped** from uploads, and certificate downloads are renamed to the company code (CX-166) | 21 Nov 2026 | User, M0–M3 walkthrough review |
| A-057 | With DEBUG=false the app **refuses the console mailer, SQLite, COOKIE_SECURE=false and disabled rate limiting**, and compares PAYMENT_PROVIDER without case. `TEST_HARNESS` exempts only the first three, for the test suite (CX-151) | 21 Nov 2026 | User, M0–M3 walkthrough review |
| A-058 | A listing the leak filter flagged is approved only with a reason and the new **`listings.override`** permission (super admin only); the reason is kept on the audit row (CX-165) | 21 Nov 2026 | Built in PR-2 from the approved change list |
| A-059 | Opening an account in the console is **`POST /admin/users/{id}/open` with a reason**; the GET is removed. Staff list pages that show names write an **`identity.listed`** row with the count (CX-168, CX-169) | 21 Nov 2026 | Built in PR-2 from the approved change list |

## Proposed: awaiting approval

D-001 … D-005 were approved on 15 Nov 2026 and are now A-011 … A-015; D-006 is A-024. Nothing is waiting.

| ID | Proposal | Recommendation | Why |
|---|---|---|---|

## Planned with a milestone: confirmed at that milestone's design review

These are tracker rows that change today's behaviour to match the build plan.
They're scheduled, but the milestone's design review is where they're confirmed.

| Row | Change | Note |
|---|---|---|
| CX-068 | Public market shows region, never city | Masking promise |
| CX-071 | Listings go through review before the market (code currently publishes on verification) | — |
| CX-083 | Retire contact reveal | Confirmed by A-026; done as A-030 |

## Waiting on someone outside the team

| Row | Question | Who answers | How to build meanwhile |
|---|---|---|---|
| **CX-078** | LC outlay cap for merchanting deals: four months or six? The 2025 circular says six; the unamended LC clause says four | AD bank, in writing | Build the validator to **4** months as a configuration value (CX-110) |
| **CX-137** | Hosting location and cross-border transfer basis (India, UAE, Railway Singapore today) | Counsel | The vault is built in the same database meanwhile (A-027); it moves when counsel answers |
| CX-109 | Contract value above which legal review is required, and which clauses count as non-standard | Client and lawyer | Make the threshold configuration; the non-standard list a data table |
| CX-020 | Collect bank details at KYB, or at the first payout? | Client | Payouts (CX-121) need verified accounts either way |
| CX-019, CX-024, CX-026 | Trader team accounts, buy/sell mode switch, Google sign-in | Client | Backlog (Phase C); don't build |
| CX-084, CX-085 | Credit cost per action and plan prices (plan 17.5) | Client | Placeholder values in configuration (A-031) |
| CX-147 | Tax invoice for plan purchases: GST registration, rate, place of supply, layout | Accountant | An invoice number is stored per paid purchase; the document is not built. No real payments until answered |
| CX-096 | Minimum margin percent and FX buffer percent | Client | Placeholder settings (A-037) |
| CX-090 | Which countries are held for sanctions review | Client's compliance contact | Empty admin-managed list; nothing is held until it is filled (A-039) |
| Plan open questions | 29 questions across 13 plan sections (claim windows, retention %, credit prices, matching hard rules…) | Client, mostly | Make each one configuration with a sensible default, and list it in the milestone's design review |
