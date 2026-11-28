# Corridor One X — Feature catalogue

**Living document.** Every feature is added here when it is built, in plain
language for Corridor One X (the customer). At hand-over it becomes the
customer's *Platform features & security* document (exported to PDF).

Last updated: 27 November 2026 · Status key: ✅ built and tested · 🔜 planned (phase noted)

---

## 1. Traders (buyers and sellers)

### 1.1 Sign-up
- ✅ Sign-up asks only for **name, company name, work email and password**.
- ✅ **Work email proof**: a 6-digit code is emailed (valid 10 minutes, 5 tries, one use). Free-mail and disposable addresses are refused.
- ✅ The account is created only after the code is confirmed; acceptance of the Terms and Privacy Policy is recorded with date and version.
- ✅ One company name can be registered only once.
- ✅ A **quick tour** after sign-up (can be skipped).

### 1.2 Signing in and account security
- ✅ Email + password sign-in with a generic error (it never reveals whether an email has an account).
- ✅ **One device at a time** — signing in on a new device signs the previous one out, wherever it is.
- ✅ Automatic sign-out after **12 hours without activity**, and after **7 days** in any case.
- ✅ **Lockout**: 5 wrong passwords → locked 15 minutes; again → 30 minutes; a third time → locked until Corridor support unlocks it.
- ✅ **Forgot password**: emailed 6-digit code; resetting signs the account out everywhere.
- ✅ **Change password** (current password required).
- ✅ **Sign-in & security** panel: the signed-in device, its network and recent sign-in activity (successful sign-ins, wrong passwords, lockouts, password changes).
- ✅ **Delete my account** (DPDP right to erasure): personal data erased, KYB documents removed, signed out.
- 🔜 Two-factor authentication with an authenticator app (Phase B, before launch).

### 1.3 Business profile & KYB (verification)
- ✅ Business profile with **company name, logo, banner**, address, industry, operating countries, website and introduction; country is chosen on the profile (only countries Corridor has opened).
- ✅ **Documents per country** — the list (e.g. GSTIN, PAN, IEC, FSSAI for India) is set by Corridor admins; each row takes a **number, a file, or both**; "Other" documents can be added.
- ✅ Format checks on numbers; duplicates across businesses refused where a number must be unique.
- ✅ **Sensitive numbers are encrypted** and shown masked (last 4 characters); the owner can reveal the full number on purpose.
- ✅ Aadhaar is never accepted.
- ✅ Files: PDF / JPG / PNG / WEBP, checked by content (not by name), size-limited; previewed in the app.
- ✅ **Submit for review** once all required items are present; the app shows what's missing.
- ✅ After a rejection the trader sees the reason and **exactly which items were flagged**; flagged items must be replaced before resubmitting.
- ✅ A verified business goes back to review automatically if its KYB details change (company name, address, city, country, required documents).
- ✅ **Verified badge** on the dashboard and in the market; email when approved or rejected.

### 1.4 Products & market
- ✅ Product listings: name, category, grade, variety, HS code, origin country and state, packaging, quantity, unit, minimum order (MOQ), monthly capacity, lead time, a **price range** with currency and validity date, accepted incoterms, port of loading, description, 1–5 photos.
- ✅ **Listing review (M1):** a listing starts as a draft, is submitted once the checklist is met and the business is verified, and reaches the market only when a reviewer approves it. The seller sees the reviewer's reason on a rejection, and can withdraw, pause, resume or delete a listing.
- ✅ **Editing a published listing (M1):** price range, price validity, quantity and MOQ change at once; any other change waits for a reviewer while the published version stays live.
- ✅ **Specifications (M1):** each category has a template of specification rows (Rice, Spices and Pulses to start); the seller states a value, whether it is a minimum, maximum or exact, and optionally the test method.
- ✅ **Listing documents (M1):** certificate of analysis, quality test report and product certificate; internal until a reviewer approves one for download by verified buyers. Every download is logged.
- ✅ **Who sees prices (M1):** the price range and price filters are for signed-in, verified businesses; everyone else sees "On request". The market shows the seller's state, never the city.
- ✅ Public **market** (no sign-in needed) with search and filters (category, variety, origin, price range, MOQ).
- ✅ **Display currency** (INR / AED / USD) with indicative conversion from daily exchange rates.
- ✅ Seller identity is **masked** in the market: a company code such as `IN-482913`, the state and the verified badge. Never the name, the city or a contact.
- ✅ **Company code (M2):** each business gets its code when it is first verified and keeps it for life.
- ✅ **Listing text is checked (M2):** a phone number, email, web address or messaging handle in a listing is refused with a message saying what to remove. Text that only looks doubtful is saved and flagged to the reviewer.
- ⛔ **Contact reveal is retired (M2).** Corridor One X is the counterparty for both sides, so a buyer is no longer handed the seller's name and email.

### 1.5 Credits (M2)
- ✅ **Wallet:** one credit balance per company, with every movement listed.
- ✅ **Free RFQs:** ten per verified company, tied to its registration number.
- ✅ **Plans and top-ups:** bought by card or UPI through Razorpay. Credits arrive when the payment is confirmed. A plan that runs out keeps its benefits for seven days, then the company is on the Free plan; bought credits are kept.
- ⏳ Prices shown are placeholders until the client sets them. The tax invoice document is not built: it needs the company's GST details.

### 1.6 Requests for quotation (M3)
- ✅ **Draft a request** from a listing or for the open market: product, grade, specification limits, quantity, packaging, certificates needed, incoterms, payment terms, delivery country, port and window, a target price and notes. A draft is free and can be written before verification.
- ✅ **Submit** once verified. It takes one of the ten free requests, or credits. The request shows what is still missing before it can be sent.
- ✅ **Preview** exactly what a seller will read. The target price and the buyer's name are never shown to a seller.
- ✅ **Matched requests** for sellers: the desk sends a request only to sellers whose listing meets it. Opening one costs credits once.
- ✅ A request the desk refuses, or that no seller fits, is **refunded** automatically.
- ✅ **Quote (sellers):** price, quantity, incoterm, port, lead time, payment terms, validity, and whether each required specification is met. One quote per request, changeable until Corridor One X starts pricing it.
- ✅ **Offers (buyers):** each offer shows the seller's code, lead time, incoterm and specifications met for free. Unlocking shows the price and terms and costs credits once. The buyer never sees what the seller quoted.

### 1.7 Negotiation (M4)
- ✅ **Choose an offer:** the buyer goes ahead with one unlocked offer. Negotiation opens with that seller; the other sellers are told their quote wasn't taken.
- ✅ **Chat through Corridor One X:** each side writes to Corridor One X in its own thread. A clean message reaches the other side under the sender's company code. One that may name a company waits for Corridor One X; one with a phone number, email or link is refused.
- ✅ **Three refused messages in 90 days suspend the company** from writing, quoting and requesting. Reading stays open. Only a desk manager can lift it.
- ✅ **Counter-offers:** either side proposes a new price in its own currency. Corridor One X checks it, then the other side sees what it means in their currency and accepts or declines. Neither side sees the other's price.
- ✅ **Samples:** the buyer asks for a sample (paid in credits). The seller sends it to Corridor One X's hub, which splits it, seals both halves, keeps one for disputes and sends the other to the buyer under its own name. The buyer records whether it passed. Each side sees only its own courier leg.
- ✅ **Term sheet:** Corridor One X drafts the terms (product, quality, quantity, price, payment, incoterm, ports, delivery window). Each side reads its own price and accepts the exact version it read, or says what needs to change. When both accept, the version is agreed and can never change; new terms mean a new version, which replaces it once both accept.
- ✅ **Letters of intent:** once the term sheet is agreed, each side receives its own letter of intent with Corridor One X, naming only itself, at its own price. It is read and signed in the app: the signer confirms they may sign for their company. Corridor One X countersigns. If both letters aren't signed within five business days, both lapse and new ones can be issued.
- ✅ **Contracts:** after both letters are signed, the buyer receives a sales contract and the seller a purchase contract, each with Corridor One X. They are signed the same way. Both take effect at the same moment, when Corridor One X signs the second; the deal is then contracted. Contracts not signed within five business days of the letters lapse with them.
- ✅ **Payment schedule:** when the contracts take effect, each side sees its own payments: the buyer what it pays Corridor One X and when, the seller what Corridor One X pays it, with a 10 % retention held until the buyer accepts the goods. Eight payment terms: advance, advance and balance against documents, cash against documents, letter of credit at sight, usance letter of credit, documents against acceptance, open account, escrow.
- ✅ **Bank accounts:** a verified company adds its account for each currency in Settings; the number is stored encrypted and shown masked. Corridor One X verifies it before any payment uses it; a new account replaces the old one and is verified again.
- ✅ **Payments received:** a buyer's payment is marked received when it reaches Corridor One X's bank from the buyer's verified account for the exact amount due.
- ⏳ The retention (10 %) and the four-month outlay cap are placeholders until the client and the bank confirm them.
- ⏳ The letter and contract texts are drafts until a trade lawyer approves them; nothing is sent for signature before then.
- ⏳ The sample fee is a placeholder (5 credits) until it is set from a courier quote.

---

## 2. Corridor operations (admin console — "Control Tower")

### 2.1 Admin accounts and roles
- ✅ **Named admin accounts** — no shared password.
- ✅ Roles: **Super admin** (everything) and **Reviewer** (reviews businesses and documents). New roles can be added later.
- ✅ Super admins create admins; a **temporary password** is shown once and must be changed (12+ characters) at first sign-in.
- ✅ Super admins can change roles, disable / enable, reset passwords, unlock and sign out other admins; at least one active super admin is always kept, and nobody can demote or disable themselves.
- ✅ Admin sessions: **one device**, end after **30 minutes idle** or **8 hours**; same lockout rules as traders.
- ✅ **Network restriction** setting (admin access only from listed IPs) — built, switched off during testing.
- 🔜 Two-factor authentication for admins (Phase B, before launch).

### 2.2 Reviews (KYB)
- ✅ **One combined review** of the business profile and its documents.
- ✅ Approve → business verified and its required documents approved.
- ✅ Reject → the reviewer must tick the failed items and give a reason; the trader is emailed.
- ✅ Revoke a verified badge; reopen a review.
- ✅ Full numbers and files open only on deliberate action, **rate-limited and logged** (who viewed what, when).
- 🔜 Ask for a reason before revealing a number or opening a file (Phase A remainder).

### 2.3 Directory and support
- ✅ Directory of all accounts with search and status filters; account detail with profile, documents, onboarding timeline.
- ✅ Edit business details (audited).
- ✅ **Sign-in & security** card per trader: lock state, signed-in device; super admins can **unlock** an account and **sign out** its device.
- ✅ **Identity access is logged (M2):** opening an account or a listing under review records who looked at which company. A super admin can turn a company code back into a name by giving a reason. Unusual volume is flagged in the audit trail.

### 2.3a Listing review (M1)
- ✅ Queue of new submissions and edits to published listings; the reviewer sees the listing, the seller behind it, and for an edit the published value next to the proposed one.
- ✅ Approve (publish, or apply the edit), reject with a reason, or take a published listing down. Every decision is in the audit trail.
- ✅ Mark each listing document internal or downloadable.
- ✅ Listing templates: specification rows and document types per category, required or optional, retired but never deleted.
- ✅ Opening a KYB file or revealing a full KYB number asks for a reason once per business; the reason is stored with the audit entry.

### 2.4 Countries and document types
- ✅ Super admins **open a country together with its required documents** (name, flag, dial code, currency, address labels, postcode format).
- ✅ Pause / reopen a country for new businesses; add, edit, hide documents; mark required or optional.
- ✅ Reviewers can view the lists but not change them.

### 2.5 Dashboard
- ✅ Live counts (sign-ups, businesses by status, products, pending reviews), sign-up timeline, businesses stuck in onboarding, India ⇄ UAE corridor view.

### 2.6 Audit trail
- ✅ Every admin decision and edit is recorded (admin, action, target, reason, time).
- ✅ Every sign-in, failure, lockout, logout and password event is recorded (network shortened, never the full IP).
- 🔜 Tamper-evident (hash-chained, insert-only) audit log (Phase B).

---

## 3. Data protection & security (summary for the customer)

| Area | What the platform does |
|---|---|
| Passwords | Stored only as slow salted hashes (bcrypt); never visible to anyone |
| KYB numbers | Encrypted (AES-256-GCM) with keys kept outside the database; masked by default |
| Access between businesses | A business can never see or change another business's documents (tested) |
| Sessions | Server-side, revocable instantly; traders on up to five devices (each can be signed out from Settings), admins on one; idle and absolute timeouts |
| Brute force | Lockout after repeated wrong passwords; rate limits on sign-in, sign-up and reset |
| Web protections | Cross-site request blocking, strict CORS, security headers, no caching of personal data, Secure cookies on HTTPS |
| Logs | No passwords, numbers or document contents in logs; who-did-what recorded |
| Privacy (DPDP / UAE PDPL) | Consent recorded; access, correction and erasure built in; Aadhaar never collected |
| Testing | 238 automated tests, including security and cross-business access tests |

Planned before launch (Phase B): two-factor authentication, private encrypted file storage with malware scanning, shared rate limiting, key management service, web application firewall, central log retention (180 days, CERT-In), database hardening and backups, dependency upgrades. Full detail: `docs/05_security_review.md`.

---

### 2.7 Trade desk (M3)
- ✅ **Request queue:** new requests with the sellers the rules propose and why. The desk adds or removes sellers, confirms, rejects with a reason, or closes a request as unmatched.
- ✅ **Hard rules:** same category, monthly capacity covers the quantity, required specifications within the buyer's limits, lead time inside the delivery window. The desk cannot add a seller who fails one.
- ✅ **Roles:** trade desk and desk manager. They see company codes, never names.
- ✅ **Ranked proposals:** among the sellers that pass every rule, the best ten are proposed, ranked out of 100 on optional specifications met, price against the buyer's target, and how often the seller quotes when sent a request. The desk sees the score and why.
- ✅ **Cost sheet:** the desk adds freight, insurance, inspection and other costs to a quote (each in rupees, dirhams or dollars, converted once at the stored rate), converts once at a stored rate with a buffer, and sets the margin. A freight figure older than seven days is refused. A margin under the floor needs a desk manager other than the author.
- ✅ **Publish the offer:** the buyer gets the selling price; the deal moves to Quoted. The offer ends at least two days before the quote behind it.
- ✅ **Held countries** and the desk's settings (how long a request stays open and others), set by a super admin.

### 2.8 Negotiation desk (M4)
- ✅ **Held messages:** release or reject, with a reason the sender reads. The desk reads both threads of a deal and can write into either.
- ✅ **Counter-offers:** each shows what it means for the other side and the margin left. Pass it on at the sheet's margin or another; outside the floor or ceiling only a desk manager may.
- ✅ **Samples in progress:** record arrival at the hub, the two seal numbers, the forward courier and delivery. A sample can't be forwarded before both halves are sealed.
- ✅ **Term sheet:** draft a version (the first starts from the chosen offer at the last accepted counter's prices), edit it, and issue it to both sides. Issuing fixes the text. A margin outside the limits needs a desk manager. A version can be withdrawn until it is agreed.

- ✅ **Contracts (desk):** set each contract's own terms (quantity tolerance, shipment window, inspection, penalties, claim window, law, seat, force majeure). The two contracts are refused, naming the term, unless every promise to the buyer is backed by the seller: penalties are compared as amounts of money, not percentages. Contracts above a set value need the lawyer who reviewed them recorded first.
- ✅ **Letters of intent (desk):** issue both letters from the agreed term sheet (refused if they would disagree, or would show the other side's identity), countersign as Corridor One X (desk manager), void with a reason. Templates are listed with their approval; a super admin records the lawyer's approval of each version.

### 2.9 Finance (M5)
- ✅ **Bank accounts:** verify or reject a company's account, saying how it was checked; see the full number only with a recorded reason.
- ✅ **Bank statements:** describe each bank's CSV export once, then import statements. Payments that name the deal and match a payment due from the buyer's verified account are matched automatically; the rest wait for finance to match by hand, under the same rules, or set aside with a reason.
- ✅ **The books:** each deal's buyer and seller sides in one view, balanced per currency.

## Change log

| Date | Added |
|---|---|
| Nov 2026 (M4, sprint S8) | Choosing an offer, chat through the desk with the leak filter and suspension, counter-offers, sample chain of custody, versioned term sheet |
| 31 Oct 2026 | Catalogue started. Phase A security: named admins and roles, one-device sessions, timeouts, lockout with support unlock, forgot password, sign-in activity, admin accounts page, security headers |
| Nov 2026 (M1) | Listing review, price range, specifications, listing documents, prices for verified businesses only, market shows state not city, reason required for admin views of KYB data, image metadata stripped on upload, security emails |
| Nov 2026 (M3, screens) | Requests page, request editor with checklist and seller preview, offers with unlock, seller's matched requests and quote form, "Request a quote" on a listing, trade desk page |
| Nov 2026 (M3, sprint S7, API) | Seller quotes, cost sheets with stored FX and margin approval, offers with paid unlock |
| Nov 2026 (M3, sprint S6, API) | Deals and their state machine, requests for quotation, matching by hard rules, trade desk queue and roles, held countries, automatic refund and expiry |
| Nov 2026 (M2, sprint S5) | Credit wallet and ledger, free RFQ quota, plans and top-ups with a payment webhook, listing text checked by the leak filter, notification template lint |
| Nov 2026 (M2, sprint S4) | Identity vault, company codes, market shows the code instead of an internal id, contact reveal retired, identity access by staff logged and limited |
| Earlier | Sign-up with email code, business profile and per-country KYB, combined review, countries, products and market, currency display, contact reveal, admin console |
