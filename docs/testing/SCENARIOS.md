# Cor1x end-to-end scenario catalogue

Every scenario the automated suites cover, with a stable ID you can quote
in a bug report or a release checklist. The ID is in the test's name, so
`pytest -k ONB-100` / `npx playwright test --grep E2E-UI-370` runs exactly
one of them.

Run everything with one command:

```bash
./scripts/e2e.sh
```

| Suite | What it drives | Where |
|---|---|---|
| Backend journeys (`E2E-…`) | the real FastAPI app over HTTP, throwaway SQLite, console email, static FX | `backend/tests/e2e/` |
| Frontend journeys (`E2E-UI-…`) | a real Chromium against a built Next.js server talking to a real backend | `frontend/e2e/` |
| Backend unit/API suite | the pre-existing `backend/tests/*.py` and `backend/tests/qa/` | `backend/tests/` |

Nothing is mocked inside the stack: a scenario that says "the trader is
verified" really walked signup, Passport, KYB and an admin decision.

---

## How to run

```bash
./scripts/e2e.sh              # backend + frontend, prints a pass/fail summary
```

```bash
./scripts/e2e.sh backend      # pytest only (fast; no browser, no build)
```

```bash
./scripts/e2e.sh frontend     # Playwright only (boots its own backend + build)
```

```bash
./scripts/e2e.sh checks       # typecheck, lint, next build
```

Useful extras: `--keep` leaves the servers up, `--no-build` reuses the last
frontend build, and anything after `--` is passed to Playwright
(`./scripts/e2e.sh frontend -- --grep @market`).

Backend only, by hand:

```bash
cd backend && .venv/bin/python -m pytest tests/e2e -q
```

```bash
cd backend && .venv/bin/python -m pytest -q -m "not e2e"
```

The runner uses a throwaway database under `.e2e-run/`, an email outbox
directory instead of a mail provider, fixed FX rates and a temporary
storage dir. It never touches `backend/cor1x.db` or any real service.
The backend runs with `DEBUG=true` so the signup screen shows the emailed
code — that is how the browser scenarios complete a real signup.

---

## Backend journeys

### Onboarding — `backend/tests/e2e/test_e2e_onboarding.py`

| ID | Scenario | Expected |
|---|---|---|
| ONB-100 | Sign up, fill the Passport, attach KYB, submit, ops approves | Business goes draft → pending → verified, lands in the review queue, approval email sent, a published lot is visible in the market |
| ONB-110 | Press "Send for verification" on a verified business | 400, "already verified" |
| ONB-120 | Submit twice in a row | Idempotent — same `submittedAt`, the clock does not restart |
| ONB-200 | Ops rejects named items, trader fixes them, resubmits | Status rejected with reason and flagged items, the flagged document blocks approval, resubmitting clears the flags, second review approves |
| ONB-210 | Reject with a blank reason / an unknown item key | 422 / 400; the business stays pending |
| ONB-220 | Ops revokes a verified business, then re-approves it | Lots leave the market at once and come back on approval |
| ONB-300 | Sign up with free-mail, disposable or malformed addresses | Refused, no email sent |
| ONB-310 | Sign up again with an email that already has an account | Told to log in; never a second account |
| ONB-320 | Five wrong signup codes | The code is dead, even the right one |

### KYB and the Passport — `backend/tests/e2e/test_e2e_kyb.py`

| ID | Scenario | Expected |
|---|---|---|
| KYB-100 | Country picker | Only countries ops set up (IN, AE); anything else refused with a readable reason |
| KYB-110 | A Dubai business onboards | Asked for a trade licence (file), not a GSTIN; a number alone is refused; the journey ends verified |
| KYB-200 | Malformed GSTIN / PAN | Refused at entry; stored numbers are masked in lists and only shown by the reveal call |
| KYB-210 | Add the same document type twice | 409; editing the existing entry is the way to change it |
| KYB-220 | Upload a text file renamed to .pdf, or a 12 MB file | 415 / rejected on size |
| KYB-230 | Add and remove an "Other" certificate | Created with its free-text name, deleted cleanly, file gone |
| KYB-300 | A verified business edits its registered address | Back to review automatically; its lots leave the market until re-approved |
| KYB-310 | A verified business edits its contact person | Stays verified — contact details are not KYB data |
| KYB-320 | Ops makes another document mandatory | Verified businesses that lack it are asked for it; supplying it closes the gap |

### Market and trade — `backend/tests/e2e/test_e2e_market.py`

| ID | Scenario | Expected |
|---|---|---|
| MKT-100 | Seller publishes, anonymous visitor browses | Search, category and origin filters, facets and the detail page all agree; the seller is never named |
| MKT-110 | Draft and pending businesses | Invisible in the market; approval publishes their lots without touching the listing |
| MKT-120 | Paging through the market | Every lot exactly once; out-of-range offsets empty; bad limits 422 |
| MKT-130 | Seller withdraws a lot | Gone from their list, the market and the detail route; a second delete 404s |
| MKT-200 | Lots priced in INR, AED and USD | Each keeps its own price and gains a comparable USD value; price filters convert; facets report the USD range; unsupported currencies refused |
| MKT-210 | Display currency | Indian business starts on INR, can switch to AED, cannot pick an unsupported one |
| MKT-300 | A verified buyer unlocks a verified seller | Full contact card once; unlocking again returns the same card, not a second charge |
| MKT-310 | Anonymous / unverified buyer / revoked seller | 401 / 403 / 404 |
| MKT-320 | Unlocking your own listing, or a bad id | 400 / 404 — never a 500 |

### Sessions and account security — `backend/tests/e2e/test_e2e_auth.py`

| ID | Scenario | Expected |
|---|---|---|
| AUTH-100 | Sign in on a second device | One device per account: the first is signed out, and the security page says so |
| AUTH-110 | Logout and logout-all | Session dead server-side; signing out twice is harmless |
| AUTH-120 | Change password | This browser stays in, the old password stops working, a wrong current password is refused |
| AUTH-130 | Forgot password → code → reset | Every device signed out; only the new password works |
| AUTH-140 | Forgot password for an unknown email | Same answer either way; no email sent |
| AUTH-200 | Five wrong passwords | The fifth locks the account (423); the right password is refused while locked; the owner can see it |
| AUTH-210 | Ops unlocks a locked trader | Sign-in works again |
| AUTH-220 | Ops signs a trader out | The trader's next call 401s |
| AUTH-300 | Trader closes their account | Session dead, email can't sign in, the company's lots leave the market |
| AUTH-400 | Every private route without a session | 401 (the frontend's redirect depends on it); `/auth/session` answers with `userId: null` |
| AUTH-410 | A hand-edited session cookie | 401 |

### Ops console — `backend/tests/e2e/test_e2e_admin.py`

| ID | Scenario | Expected |
|---|---|---|
| ADM-100 | Bootstrap super admin signs in | Every console view answers 200; permissions listed |
| ADM-110 | No admin cookie, or a trader's cookie | 401 everywhere; wrong password refused |
| ADM-120 | Super admin creates a reviewer | One-time password, must be changed on first sign-in, work blocked until it is, the temporary password is then spent |
| ADM-130 | Reviewer tries admin-only work | Review views allowed; managing admins or the document catalogue 403 |
| ADM-140 | An admin account is disabled | Access ends immediately, and they cannot sign back in |
| ADM-200 | Dashboard counters | Move with the queue; the timeline is one point per day |
| ADM-210 | Document review | Pending list, reveal, reject with reason (trader emailed), replace file, approve — all audited, and the audit never stores the number |
| ADM-220 | Approve / reject a business | Both written to `admin_actions` with the reason and flagged items |
| ADM-230 | Ops corrects a business field | The trader sees the change; the edit is on the record |
| ADM-240 | Stuck signups | A brand-new draft is not chased; one sitting 24h+ is |

### Promises about other people's data — `backend/tests/e2e/test_e2e_security.py`

| ID | Scenario | Expected |
|---|---|---|
| SEC-100 | Business A's ids used by business B | Lots, KYB entries, files and numbers all 404 for B |
| SEC-110 | KYB documents | No public URL; the owner's download is `private, no-store`; anonymous gets 401/404 |
| SEC-120 | The anonymous market | No seller email, person, address, company name or ID numbers in any public response |
| SEC-130 | Product photo uploads | Sniffed by content, not filename; served with the right type, `nosniff`, `inline`; no path traversal |
| SEC-140 | Lot photos | Only URLs that were actually uploaded; remote and invented paths refused |
| SEC-200 | Cross-site writes with a stolen cookie | 403 on POST/PATCH/DELETE; reads fine; the real frontend origin accepted |
| SEC-210 | Cross-site writes to `/admin` | 403, session untouched |
| SEC-300 | Hammering "resend code" | 429 with `Retry-After` |
| SEC-310 | Looping the KYB reveal endpoint | Capped (429) |
| SEC-400 | Error shapes | `{"detail": …}` plus a request id; no stack traces, no SQL |
| SEC-410 | Signed-in responses | `no-store`, `nosniff`, request id |
| SEC-420 | `GET /health` | Public, `{"status": "ok"}` |

---

## Frontend journeys (Playwright)

Tags let you run a slice: `--grep @public`, `@auth`, `@dashboard`,
`@admin`, `@responsive`.

### The open corridor — `frontend/e2e/public.spec.ts`

| ID | Scenario | Expected |
|---|---|---|
| UI-100 | Landing page | Renders with a heading, sign-in link, and the market link works |
| UI-110 | Unknown URL | 404 page, not a crash |
| UI-120 | `/privacy`, `/terms` | Reachable, each with a heading |
| UI-130 | A verified seller's lots | Listed; search narrows to the match; a search with no hits says so |
| UI-140 | Lot page as a stranger | Seller masked behind the gate; "Sign in to contact" keeps the return path |
| UI-150 | A lot id that does not exist | 404 page |

### Signing up and in — `frontend/e2e/auth.spec.ts`

| ID | Scenario | Expected |
|---|---|---|
| UI-200 | The whole signup, in the browser | Name/company/email → emailed code typed in → password + terms → dashboard |
| UI-210 | Free-mail address | Refused on screen; never reaches the code step |
| UI-220 | Wrong code | Error shown, stays on the code screen |
| UI-230 | Sign in | Reaches the dashboard and a private page |
| UI-240 | Wrong password | "That email and password don't match", still on /login |
| UI-250 | A private page while signed out | Redirected to `/login?next=…`, then returned there after signing in |
| UI-260 | Forgot password | The screen accepts an email and confirms |
| UI-270 | Signing in on a second browser | The first browser's session ends; its next private page bounces to login |

### The trader's corridor — `frontend/e2e/dashboard.spec.ts`

| ID | Scenario | Expected |
|---|---|---|
| UI-300 | A fresh account's Passport | "Still needed" list, progress meter, submit disabled |
| UI-310 | A complete Passport | "Profile and documents are in", submit enabled, nothing outstanding |
| UI-320 | After submitting | Reads "In review" with the ops explanation |
| UI-330 | After approval | The verified panel |
| UI-340 | After rejection | "Needs changes" with the reason, and a resubmit button |
| UI-350 | A seller's own lots | Listed in the dashboard and on the market page, where their own listing offers nothing to reveal |
| UI-360 | An unverified buyer on a lot page | Gate explains why; no reveal control |
| UI-370 | A verified buyer holds "Reveal contact" | The seller's email appears — and was not on the page before |
| UI-380 | Signing out | The session is gone; the dashboard redirects to login |

### Ops console — `frontend/e2e/admin.spec.ts`

| ID | Scenario | Expected |
|---|---|---|
| UI-400 | `/admin` without a session | The tower login, not the console |
| UI-410 | Wrong admin credentials | Error shown, still on the admin login |
| UI-420 | Admin signs in | The tower renders with live numbers, no error state |
| UI-430 | A submitted company | Appears in the review queue by legal name |
| UI-440 | Ops holds "Approve company" | The decision reaches the backend: the trader reads as verified |
| UI-450 | Every day-to-day admin page | Tower, reviews, directory, docs, doc types, admins all render |

### Layout and markup — `frontend/e2e/responsive.spec.ts` (desktop **and** a phone viewport)

| ID | Scenario | Expected |
|---|---|---|
| UI-500 | Public pages | No sideways scrolling at either size |
| UI-510 | Public pages | Exactly one `h1` each |
| UI-520 | Login, signup, forgot-password | Every field has a label |
| UI-530 | Landing and market | Every image has an `alt` attribute |
| UI-540 | Market and lot page on a phone | Render and fit |
| UI-550 | Dashboard on a phone | Renders and fits |
| UI-560 | Keyboard | Tab moves focus into the page |

---

## Notes for whoever runs this next

* **Shared database.** The frontend suite runs its scenarios one at a time
  against one backend, and seeded data piles up. Scenarios therefore name
  their own lots and companies uniquely rather than assuming an empty
  market; keep that up when adding tests.
* **The ops admin is shared.** Five wrong passwords lock it for the whole
  run, so negative sign-in scenarios use an address that was never an
  admin.
* **Hydration.** Next streams the HTML before React attaches; typing in
  that window is silently dropped. `frontend/e2e/support/ui.ts` has the
  helpers (`gotoReady`, `fillField`, `submitForm`) that deal with it —
  use them instead of raw `page.fill`.
* **Reference data.** A local SQLite database built by `init_local_db.py`
  is stamped past the migrations that insert countries and KYB document
  types, so run `scripts/seed_reference_data.py` after it (the E2E runner
  does). Without those rows signup fails with a misleading "account
  already exists".
* **Where to look after a failure.** `.e2e-run/logs/` for the servers,
  `frontend/e2e-results/html/index.html` for the Playwright report, and
  `frontend/e2e-results/artifacts/` for failure screenshots.
