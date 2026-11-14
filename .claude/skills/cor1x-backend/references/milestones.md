# Milestones and sprints

The plan as of 13 Nov 2026. **The tracker is the source of truth.** If a row
moved, was added, or is done, `docs/tracker/cor1x-tracker.xlsx` wins over this
file. Read the row there (its **Done when** especially) before starting it.

## Contents

- [How a milestone runs](#how-a-milestone-runs)
- [How a sprint runs](#how-a-sprint-runs)
- [Phases](#phases)
- [Epics](#epics)
- [M0 Stabilise](#m0-stabilise)
- [M1 Phase A close-out](#m1-phase-a-close-out)
- [M2 Masking and credits foundation](#m2-masking-and-credits-foundation)
- [M3 RFQ to offer](#m3-rfq-to-offer)
- [M4 Negotiation to contract](#m4-negotiation-to-contract)
- [M5 Money and execution](#m5-money-and-execution)
- [M6 Disputes and close](#m6-disputes-and-close)
- [M7 Phase B gate and launch](#m7-phase-b-gate-and-launch)
- [Backlog (Phase C)](#backlog-phase-c)

## How a milestone runs

1. **Design review.** Copy `assets/design-review-template.md` and fill it in for
   the milestone: schemas, every endpoint with request, response, errors and
   auth, state machines, migrations, the security section, the test plan, and
   the open questions. Present it to the user **in the conversation**, in plain
   language — they read it there, not by opening files. Tables first, then the
   decisions needed, each with a recommendation. The review lives in the
   session: don't write it to a file (decision A-017).
2. **Approval.** The user approves, changes or defers each part. Don't start
   building on a part that's still open.
3. **Record.** Update `references/decisions.md`, and add, split or move
   tracker rows to match what was agreed. No design file is written.
4. **Build** sprint by sprint (below).
5. **Exit gate.** Check every line of the milestone's exit gate against `main`,
   with evidence. A milestone with one open exit item is not done. Say which
   item and move on only if the user agrees.

## How a sprint runs

- Two weeks, Monday to Friday. Rows are worked in the order the sprint lists
  them, unless one blocks another.
- **Start a row:** Status → *In progress*, Owner set. One branch per row:
  `feat/cx-071-listing-review`, `fix/cx-067-exif`, `chore/cx-061-deps`.
- **Finish a row:** PR merged, CI green, every **Done when** line evidenced,
  Status → *Done*, commit hash in Notes.
- **Sprint review:** reconcile every row in the sprint against `main`. Unfinished
  rows move to the next sprint in the tracker, with a note saying why. The
  demo is the sprint's *Exit gate / sprint demo* on the Roadmap sheet.
- **After S2:** recalibrate the Roadmap dates using real velocity. The current
  dates assume today's team size.

## Phases

| Phase | Means | Rule of thumb |
|---|---|---|
| **Now** | Can't wait for a phase boundary | Known vulnerabilities, broken builds |
| **A** | Build and test with test data | The working system |
| **B** | **Before launch**: a release gate | If it only matters once real data exists, it's B (2FA, encrypted file storage, data purge) |
| **C** | After launch | Hardening that needs live traffic to matter |

Phase B items can be built early (the ops lane runs from S4). The phase says
which gate a row belongs to; the sprint says when it's done.

## Epics

Between a milestone and its rows sit **epics**, E01–E25: each is the group of
rows that together deliver one capability (E05 *Listing v2 & review*, E06
*Masking service & identity vault*, E14 *Payments & ledger*). A decision row
sits in the epic it gates. Every row with a milestone has an epic in the
tracker's *Epic* column; the Roadmap sheet (Kind = Epic) holds each epic's
goal and what it depends on. An epic is done when all its rows are Done.

---

## M0 Stabilise

**Sprint:** S1 (16–27 Nov 2026) · **Phase:** Now
**Goal:** clear the security advisories and prove the current build deploys
cleanly before adding scope.
**Exit gate:** no critical or high advisories; CI runs tests on every PR;
production build and Postgres migrations verified; tracker reconciled.

| Row | Work |
|---|---|
| CX-061 | Backend dependency upgrades: FastAPI/Starlette, python-multipart ≥ 0.0.31, cryptography ≥ 50, Jinja2 ≥ 3.1.6, python-dotenv ≥ 1.2.2 |
| CX-062 | Frontend dependency upgrades: Next.js patched line, zod (with CX-016, drop lucide-react) |
| CX-063 | CI: pytest, `tsc --noEmit`, `next lint` on every PR; protect `main` |
| CX-008 | Verify a production build (`next build`) |
| CX-003 | Run every migration through `0024` on a Postgres copy |
| CX-002 | Set `RATE_LIMIT_TRUSTED_PROXIES` on Railway |
| CX-064 | Delete stale branches `work/pegan-2026-10-21`, `work/pegan-products` |

**Proposed additions, awaiting approval** (`decisions.md` D-001 … D-005): `/v1`
prefix, the uniform error contract, strict request bodies, OpenAPI docs hidden
in production, sign-in plus rate limit plus cache on the pincode and IFSC lookups.

**Design notes:** no new tables. Upgrades go one PR per side, with the test suite
as the safety net. Read the FastAPI and Starlette changelogs for breaking changes
before bumping, and say in the PR what you checked.

## M1 Phase A close-out

**Sprints:** S2 (30 Nov–11 Dec), S3 (14–25 Dec) · **Phase:** A · **Plan:** 01, 03, 04
**Goal:** finish the identity, KYB and listing core; align the code with the
plan where they contradict; take the product-model decision.
**Exit gate:** Phase A security remainder done; listing review and specs live;
contradictions closed; CX-077 decided.

**S2 — Phase A remainder and quick alignments**

| Row | Work |
|---|---|
| CX-066 | Reason required before an admin reveals a number or opens a file; stored on the audit row |
| CX-067 | Strip EXIF/XMP/GPS from every uploaded image (re-encode on write) |
| CX-068 | Public market shows region, never city |
| CX-069 | Accept free-mail sign-ups, store `email_domain_class`, flag for KYB review |
| CX-070 | Nullable `totp_secret` (encrypted) and `backup_codes` on users and admin users; no behaviour |
| CX-034 | Email alert on password change and new-device sign-in |
| CX-017 | Browser-test the signed-out currency selector |

**S3 — Listing v2 and the model decision**

| Row | Work |
|---|---|
| CX-071 | Listing review workflow: `products.status` draft / under_review / published / rejected, action routes, live version stays during re-review |
| CX-072 | Admin listing review queue (frontend) |
| CX-073 | Category templates and spec parameters (name, unit, MIN/MAX/EQ, test method) |
| CX-074 | Listing commercial fields: HS code, grade, incoterms, price range, validity, lead time, capacity, port of loading |
| CX-075 | Listing certificates with approved-only downloads |
| CX-076 | Listing form v2 with template-driven specs and a "what buyers see" preview (frontend) |
| CX-023 | Edit and archive listings (delivered by CX-071) |
| CX-007 | Finish the photography redesign (frontend) |
| CX-077 | **Decision:** masked trading desk or introduction marketplace. Blocks M2–M6 |
| CX-078 | **Decision:** LC outlay cap, four months or six. Ask the AD bank now; needed by S10 |
| CX-137 | **Decision:** hosting location and cross-border transfer. Places the vault in S4 |

Also in M1: the four bare lists move to the `{items, total}` envelope, and
`version`-based concurrency starts on listings.

**Design review must settle:** the listing state machine and who may trigger each
move; where a pending revision of a published listing is stored; the minimum
fields to publish (plan 3.7 open question); whether the price band is public
(plan 4 open question); the template admin API.

## M2 Masking and credits foundation

**Sprints:** S4 (28 Dec–8 Jan), S5 (11–22 Jan) · **Phase:** A · **Plan:** 17, 18
**Depends on:** CX-077 decided as "masked trading desk", and CX-137 answered.
**Goal:** the masking service and the credit wallet every trade feature depends on.
**Exit gate:** no vault field reachable from any external response
(test-enforced); codes everywhere; audited unmask; wallet live; contact reveal
retired.

| Sprint | Rows |
|---|---|
| S4 | CX-079 masking service and identity vault · CX-080 masked company codes `{ISO2}-{random}` · CX-081 audited, scoped unmask with bulk-access alerts · CX-082 response-guard test · CX-083 retire contact reveal · *ops lane:* CX-053 DB private network, CX-054 least-privilege DB user |
| S5 | CX-084 credit wallet, ledger, free-RFQ quota per verified company · CX-085 plan purchase and renewal via checkout webhook · CX-086 price-on-button and wallet screens · CX-087 shared leak filter · CX-088 notification template lint · *ops lane:* CX-013 Postgres TLS, CX-028 connection pool sizing |

**Design review must settle:** the vault schema and the DB role that can read
it; the unmask API and its audit shape; how existing data migrates; the credit
ledger types and prices; the idempotency-key store.

## M3 RFQ to offer

**Sprints:** S6 (25 Jan–5 Feb), S7 (8–19 Feb) · **Phase:** A · **Plan:** 05, 06, 20
**Goal:** buyer demand reaches matched sellers and comes back as priced, masked offers.
**Exit gate:** RFQ → match → quote → cost sheet → offer → unlock end to end;
Deal state machine enforced.

| Sprint | Rows |
|---|---|
| S6 | CX-089 Deal entity and state machine · CX-090 RFQ model and submission API · CX-091 RFQ form and workspace · CX-092 matching: hard-rule filter, desk confirms · CX-093 desk RFQ triage queue · CX-094 admin roles: trade desk, quality, finance, logistics, legal · CX-025 umbrella · *ops lane:* CX-009 Redis rate limiter |
| S7 | CX-095 seller quote API · CX-096 cost sheet with stored FX and margin approval · CX-097 offer publish, unlock and expiry · CX-098 quote and offer-compare screens · *ops lane:* CX-134 security scanning in CI |

**Design review must settle:** the full Deal transition table (the state
diagram in `docs/07_development_flow.md` §8 is the starting point); which spec
fields are hard filters; the cost sheet fields and FX buffer; the three records
Quote / CostSheet / Offer and exactly which fields each audience sees.

## M4 Negotiation to contract

**Sprints:** S8 (22 Feb–5 Mar), S9 (8–19 Mar) · **Phase:** A · **Plan:** 07, 08, 09
**Goal:** agreed terms become two signed, mirrored contracts.
**Exit gate:** filtered chat; immutable term sheet; both LOIs and both contracts
signed in one transaction; the mirror validator enforces remedy *amounts*;
templates approved by a lawyer.

| Sprint | Rows |
|---|---|
| S8 | CX-099 two-thread chat relay through the leak filter · CX-100 chat screens and held-message review · CX-101 structured counter-offers · CX-102 sample chain of custody · CX-103 versioned term sheet · *ops lane:* CX-059 KMS, CX-035 key rotation |
| S9 | CX-104 dual LOIs with consistency check and lapse timer · CX-105 mirrored contracts and the full mirror validator · CX-106 contract render lint · CX-107 signing screens · CX-108 templates approved by a trade lawyer · CX-109 **decision:** legal-review threshold · *ops lane:* CX-055 backups with a tested restore |

**Design review must settle:** chat message schema and filter outcomes; the term
sheet versioning model; the ten mirror rules as code, with the penalty-amount
test (232,200 / 216,000); the signing record (document hash, signer authority).

## M5 Money and execution

**Sprints:** S10 (22 Mar–2 Apr), S11 (5–16 Apr), S12 (19–30 Apr) · **Phase:** A · **Plan:** 10–14
**Depends on:** CX-078 answered (until then the LC outlay cap is 4 months in config).
**Goal:** move money and goods with every release gate enforced.
**Exit gate:** payment terms generate milestones; each deal reconciles to zero;
no release on uncleared funds by any path; two-person payouts; merchanting
clocks live.

| Sprint | Rows |
|---|---|
| S10 | CX-110 payment terms, milestone generator, validator · CX-111 double-entry ledger with matched pairs · CX-112 bank statement ingestion and matching · CX-113 escrow flow · CX-114 merchanting clocks and default counter · CX-020 bank details · *ops lane:* CX-056 180-day logs, CX-046 unusual-activity alerts |
| S11 | CX-115 production updates · CX-116 pre-shipment inspection · CX-117 shipment and B/L validator · CX-118 bank-presentable document pack · CX-119 deal timeline screens · *ops lane:* CX-133 WAF |
| S12 | CX-120 release gate · CX-121 payouts with two-person approval · CX-122 claim window, acceptance, fail-closed settlement · CX-123 finance console |

**Design review must settle:** the ledger account chart and entry shape; the
money type (integer minor units) end to end; the idempotency and approval
records; the bank statement format; every gate as a test that proves no path
around it.

## M6 Disputes and close

**Sprint:** S13 (3–14 May) · **Phase:** A · **Plan:** 15, 16, 19, 21

| Rows |
|---|
| CX-124 claims ladder with pass-through child claims · CX-125 claims screens · CX-126 close job, ratings, sample release · CX-127 bypass watch and reporting credit · CX-128 compliance calendar · *ops lane:* CX-057 retention periods, CX-015 deleted-account file cleanup |

**Exit gate:** claims with parent and child pass-through and payout holds;
fail-closed close job; ratings on masked codes; bypass watch; compliance calendar.

## M7 Phase B gate and launch

**Sprints:** S14 (17–28 May), S15 (31 May–11 Jun 2027), plus the ops lane from S4 · **Phase:** B · **Plan:** 22

| Sprint | Rows |
|---|---|
| S14 | CX-129 mandatory 2FA for traders · CX-031 2FA for admins · CX-130 admin IP allowlist on · CX-131 encrypted file storage with malware scanning (closes CX-004, CX-010) · CX-132 hash-chained, insert-only audit log · CX-060 external penetration test |
| S15 | CX-135 production data purge and real reference data (closes CX-018) · CX-027 live FX with fallback · CX-006 privacy and terms text · CX-058 breach runbook · CX-136 data export · CX-138 launch gate review |

**Exit gate:** every Phase B row Done with evidence; suite green on production
configuration; a restore rehearsed; go/no-go signed.

## Backlog (Phase C)

CX-011 FX refresh outside the API process · CX-014 market text-search index ·
CX-019 trader team accounts · CX-024 selling/buying mode switch · CX-026 Google
sign-in · CX-036 passkeys · CX-037 token login for mobile apps.
