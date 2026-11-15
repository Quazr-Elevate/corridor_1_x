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
| A-008 | Sessions: traders 12 h idle / 7 days; admins 30 min idle / 8 h; one active device; lockout 5 → 15 min → 30 min → support unlock | 31 Oct 2026 | Built |
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
| CX-083 | Retire contact reveal | **Only if CX-077 confirms the masked trading desk** |

## Waiting on someone outside the team

| Row | Question | Who answers | How to build meanwhile |
|---|---|---|---|
| **CX-077** | Is Cor1x the counterparty on both sides (masked trading desk, plan 05–16) or an introduction marketplace (current code, contact reveal)? | Client | **Blocks M2–M6.** Don't start masking-vault, deal or payment work until it's answered. M0–M1 are safe either way |
| **CX-078** | LC outlay cap for merchanting deals: four months or six? The 2025 circular says six; the unamended LC clause says four | AD bank, in writing | Build the validator to **4** months as a configuration value (CX-110) |
| **CX-137** | Hosting location and cross-border transfer basis (India, UAE, Railway Singapore today) | Counsel | Decides where the identity vault lives (CX-079, S4) |
| CX-109 | Contract value above which legal review is required, and which clauses count as non-standard | Client and lawyer | Make the threshold configuration; the non-standard list a data table |
| CX-020 | Collect bank details at KYB, or at the first payout? | Client | Payouts (CX-121) need verified accounts either way |
| CX-019, CX-024, CX-026 | Trader team accounts, buy/sell mode switch, Google sign-in | Client | Backlog (Phase C); don't build |
| Plan open questions | 29 questions across 13 plan sections (claim windows, retention %, credit prices, matching hard rules…) | Client, mostly | Make each one configuration with a sensible default, and list it in the milestone's design review |
