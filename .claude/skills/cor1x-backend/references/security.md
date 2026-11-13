# Security standard

Security here isn't a phase. This platform will hold passports, tax IDs, bank
details, contracts and money for businesses that are trusting Corridor One X not
to expose them, even to each other. Every PR keeps that promise or it doesn't
merge.

`docs/05_security_review.md` is the record of controls, with IDs (A1…, B1…, C1…,
D…, E…, F…). Cite those IDs in PRs. This file is how to apply them while building.

## Contents

- [The checklist for every PR](#the-checklist-for-every-pr)
- [OWASP API Top 10, applied](#owasp-api-top-10-applied)
- [Project-specific rules](#project-specific-rules)
- [Known gaps right now](#known-gaps-right-now)
- [Security in the design review](#security-in-the-design-review)
- [When you find a vulnerability](#when-you-find-a-vulnerability)

## The checklist for every PR

Paste it into the PR description and tick each item, or write why it doesn't
apply. Most items take seconds.

**Access**
- [ ] Every new route has an auth dependency, or it's deliberately public and the PR says why (B1)
- [ ] Anything a business owns is fetched with the owner in the query; a stranger gets **404**, and a test proves it (B2)
- [ ] Every new `/admin` route declares one `Can…` permission; the route-matrix test passes (B9)
- [ ] Admin actions write `record_action` (C8)

**Data**
- [ ] Responses go through explicit models; no new field leaks identity, contact, bank or KYB data (B5)
- [ ] Sensitive values are encrypted at rest, masked in lists, and revealed only by a separate, rate-limited, audited call (C1, B7)
- [ ] No passwords, codes, tokens, KYB numbers, file contents, full IPs or personal data in logs (C8)
- [ ] From M2: the response-guard test passes, and free text another user reads goes through the leak filter

**Input**
- [ ] Every field has a type, a length or range bound, and an allowed set where one applies
- [ ] Uploads are content-sniffed, size-limited, renamed, and (from CX-067) stripped of metadata
- [ ] Nothing user-supplied reaches a URL, file path, SQL string, shell or template unescaped

**Abuse and money**
- [ ] Anything that signs in, reveals, uploads, sends a message, calls a third party or costs credits is rate-limited
- [ ] From M2/M5: idempotency keys on billable and money endpoints; two distinct approvers on payouts and releases

**Supply chain**
- [ ] No new dependency without a reason in the PR; pinned; no known advisory (`pip-audit`, `npm audit`)

## OWASP API Top 10, applied

| Risk | Rule in this codebase | Status |
|---|---|---|
| **API1 Broken object-level authorization** | Owner in the `WHERE` clause, never checked after loading; 404 for strangers; a cross-business test for every owned resource | ✅ tested today (B2) |
| **API2 Broken authentication** | Server-side opaque sessions (SHA-256 stored), one active device, idle and absolute timeouts, lockout 5 → 15 min → 30 min → support unlock, generic login error, equal timing for unknown emails | ✅ (A1–A10); 2FA at the Phase B gate (CX-129, CX-031) |
| **API3 Broken object property-level authorization** | Explicit request and response models; server-owned fields never in a request schema | ✅ responses · ⚠️ unknown request fields dropped silently (proposed fix: `extra="forbid"`) |
| **API4 Unrestricted resource consumption** | Bounded `limit` on every list, upload size caps, rate limits on costly routes, timeouts on outbound calls | ⚠️ four unbounded lists (fixed in M1) · ❌ lookups unthrottled |
| **API5 Broken function-level authorization** | One permission per admin route, deny by default, route-matrix test | ✅ |
| **API6 Unrestricted access to sensitive business flows** | Rate limits plus credit costs on reveal, RFQ posting, offer unlock and sign-up; free quota per verified company, not per account | ✅ reveal 20/h per business, sign-up limited · credits from M2 |
| **API7 SSRF** | Outbound calls only to fixed hosts in code; user input validated to a strict pattern before it goes into a URL path | ✅ IFSC and pincode regex-checked |
| **API8 Security misconfiguration** | Refuse insecure defaults off-debug, security headers, strict CORS, Secure cookies, no debug output | ✅ · ❌ `/docs` and `/openapi.json` public in every environment |
| **API9 Improper inventory management** | Versioned routes, a route inventory per release (`scripts/route_inventory.py`), no forgotten test or debug routes | ❌ no versioning yet (proposed `/v1`) |
| **API10 Unsafe consumption of APIs** | Timeouts, bounded retries, validate what comes back, cache third-party lookups, never trust a webhook without verifying its signature | ✅ timeouts · ❌ lookups uncached |

## Project-specific rules

**KYB data (now).** Numbers are AES-256-GCM encrypted in the app (`core/crypto.py`)
with versioned keys from the environment, stored with a keyed hash for
uniqueness and the last 4 characters for display. Lists show `valueLast4` only.
The full value comes from a separate `POST .../reveal` that is rate-limited
(30/h per trader, 200/h per admin) and audited. Aadhaar is never accepted. Follow
this exact pattern for any new sensitive value: bank accounts (CX-020), TOTP
secrets (CX-070).

**Masking (from M2, the product promise).** Outside `modules/masking`, code holds
company **codes** (`VN-4821`), not names. Reading a real identity is a call that
checks the role and the deal assignment and writes `identity.unmasked`. Market
payloads show region, never city (CX-068). Contracts and documents for one side
never contain the other side's vault fields (CX-106). Some disclosures are legal
requirements, such as origin certificates and food labels naming the producer.
Those are documented exceptions in the plan (18.4), released only to the party
that needs them, and never a reason to loosen masking elsewhere.

**Money (from M5).**
- Funds are `CLEARED` only on the bank's final-credit confirmation, never on an
  uploaded screenshot or a user's say-so.
- Documents release only when the funding milestone is cleared, and **no code
  path, admin included, can override it** (CX-120). The test proves the absence
  of the path.
- Payouts and releases need two distinct approvers, and the approver can't be
  the maker.
- A payout goes only to a verified bank account that hasn't changed during the
  cooling-off period. Bank details change only in the app, with re-verification,
  never by email.
- Refunds return to the account the money came from.
- The ledger is append-only; a correction is a reversing entry.

**Audit.** Every admin action, every unmask, every state change on a deal
(M3 on) writes an audit row with actor, target, time and details. Phase B makes
it hash-chained and insert-only (CX-132); write rows that will survive that:
no updates, no deletes.

**Sessions and cookies.** HttpOnly always; `Secure` off-debug; trader and admin
cookies separate; no token ever reaches JavaScript. The frontend `middleware.ts`
checks only that the cookie is present. The backend validates it on every call.

**Privacy (DPDP, UAE PDPL, CERT-In).** Collect the minimum. Record consent with
its version. Support access, correction, erasure (built) and export (CX-136).
Retention gets defined and enforced by a job (CX-057). Logs keep a truncated IP
(/24, /48) and never the full one.

## Known gaps right now

Found in the audit of `main` @ `90ef21f`. Each one is in M0 or has a row.

| Gap | Risk | Where it's fixed |
|---|---|---|
| `/pincode/{pincode}` and `/ifsc/{code}` need no session, have no rate limit and no cache | Anyone can use our server as a free proxy to India Post and Razorpay and get our IP blocked (API4, API10) | Proposed for M0 |
| `/docs`, `/redoc`, `/openapi.json` are served in production | A full map of the API for anyone (API8) | Proposed for M0 |
| Unknown request fields are silently dropped | Hides client bugs; weakens the API3 guarantee | Proposed for M0 |
| Validation errors have a different shape from domain errors | Clients can't rely on one contract | Proposed for M0 |
| No route versioning | Breaking changes have nowhere to go (API9) | Proposed for M0 |
| Four bare, unbounded lists | API4 | M1 |
| Dependency advisories (FastAPI/Starlette, python-multipart, cryptography, Jinja2, Next.js, zod) | Known CVEs | CX-061, CX-062 |
| Uploads keep EXIF and GPS | Location leak against the masking promise | CX-067 |
| Seller city in the public market payload | Identifying detail | CX-068 |
| KYB files on local disk, unencrypted | Data at rest | CX-131 (Phase B) |
| No 2FA | Account takeover | CX-129, CX-031 (Phase B) |

Don't fix these in passing inside an unrelated PR. They have rows, and a fix
deserves its own review.

## Security in the design review

For every milestone, the design review has a security section that answers:

1. What new data is stored, how sensitive it is, and is it encrypted or masked?
2. Who can call each endpoint, and how is ownership enforced in the query?
3. What can be abused at volume, and what limits or costs stop it?
4. What leaves the system (emails, files, third-party calls, webhooks), and what does each contain?
5. What gets audited?
6. What's the failure mode if the slowest or least reliable dependency is down?
7. Which controls in `05_security_review.md` change status?

## When you find a vulnerability

Stop and tell the user plainly what it is, how it could be exploited, and how
bad it is. Don't bury it in a summary. If it's in the code you were asked to
change, fix it in that PR and say so. If it's elsewhere, open a tracker row
(*Postponed fix*, priority High if it touches identity, documents or money) and
don't fix it silently in an unrelated diff. Never write exploit code beyond the
minimum test that proves the fix.
