# Cor1x data model — target schema (v1)

Status: **approved design, not yet implemented.** This replaces the current
schema (migrations up to `0018_hardening`). Implementation = one migration
(`0019_business_entity`) that moves existing data into this shape.

## Principles

1. **The business is the main entity.** Verification, documents, listings and
   contact reveals belong to the business, not to a person.
2. **Users are people who log in and belong to one business.** Today every
   user is the business `owner`; more users per business (RBAC) later means
   adding `users` rows — no data reshaping.
3. **Signup proves inbox ownership in place** (6-digit email code on the same
   screen). No admin approval and no documents at signup.
4. **Verification is enforced at the moment of action:** a listing is visible
   in the market, and a seller's contact can be revealed, only when the
   business(es) involved are `verified`. Admin reviews a business only after it
   presses "Send for verification".
5. Countries use ISO 3166-1 alpha-2 (`IN`, `AE`); currencies ISO 4217 (`INR`).
   All timestamps are UTC `timestamptz`. All primary keys are UUIDs.

## Overview

```
                        ┌───────────────────┐
                        │    businesses     │  the company — verified, trades
                        └───────────────────┘
                          ▲        ▲       ▲
              business_id │        │       │ business_id
        ┌─────────────────┘        │       └──────────────────┐
   ┌─────────┐          ┌──────────────────┐        ┌────────────────────┐
   │  users  │          │     products     │        │ business_documents │
   │ (people)│          │    (listings)    │        │    (KYB files)     │
   └─────────┘          └──────────────────┘        └────────────────────┘
                                 ▲
                      product_id │
                        ┌──────────────────┐
                        │ contact_reveals  │  buyer_business_id → businesses
                        └──────────────────┘  seller_business_id → businesses

   email_codes    — signup / password-reset codes, keyed by email (no FK)
   admin_actions  — append-only audit log (no FK)
```

## Enums

| Enum | Values |
|---|---|
| `business_status` | `draft` · `pending_verification` · `verified` · `rejected` |
| `user_role` | `owner` · `admin` · `member` (only `owner` used now) |
| `account_status` | `active` · `disabled` |
| `doc_status` | `pending` · `approved` · `rejected` |
| `email_code_purpose` | `signup` · `reset_password` · `invite` (only `signup` used now) |

## 1. `businesses`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | uuid | no | PK |
| legal_name | varchar(200) | yes | filled on the Passport |
| legal_name_normalized | varchar(200) | yes | **unique**; lowercased/trimmed, synced automatically |
| entity_type | varchar(30) | yes | `proprietorship` · `partnership` · `llp` · `private_ltd` · `public_ltd` |
| industry | varchar(120) | yes | |
| operating_countries | char(2)[] | yes | ISO alpha-2 (JSON list on SQLite) |
| website_url | varchar(300) | yes | |
| website_normalized | varchar(300) | yes | **unique**; synced automatically |
| address_line | varchar(200) | yes | company address |
| city | varchar(100) | yes | shown in the market as "city, state" |
| state | varchar(100) | yes | |
| pincode | varchar(10) | yes | |
| country | char(2) | no | default `IN` |
| google_business_url | varchar(300) | yes | |
| facebook_url | varchar(300) | yes | |
| trade_position | varchar(10) | yes | `seller` · `buyer` · `both` |
| seller_type | varchar(60) | yes | miller/producer, exporter, trader, aggregator… |
| export_status | varchar(40) | yes | exporting · first-time · domestic only |
| target_markets | char(2)[] | yes | ISO alpha-2 |
| target_buyer_types | varchar(40)[] | yes | importer, wholesaler, retail chain, food processor, HoReCa… |
| company_introduction | text | yes | public "About us" |
| verification_status | business_status | no | default `draft` |
| verification_submitted_at | timestamptz | yes | set on "Send for verification" |
| verified_at | timestamptz | yes | set when admin approves |
| verification_rejected_reason | varchar(500) | yes | admin's note when rejected |
| created_at | timestamptz | no | default now() |
| updated_at | timestamptz | no | default now(), on update |
| deleted_at | timestamptz | yes | soft delete |

Indexes: `uq_businesses_legal_name_normalized`, `uq_businesses_website_normalized`
(unique, NULLs allowed), `ix_businesses_verification_status`.

**7 mandatory fields for "Send for verification"**: owner's full name,
position, phone (on `users`); legal_name, industry, operating_countries,
trade_position (on `businesses`).

## 2. `users`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | uuid | no | PK |
| business_id | uuid | no | FK → businesses.id, ON DELETE RESTRICT; indexed, **not unique** |
| role | user_role | no | default `owner` — what the person may do in the app (permissions), unlike `position` |
| email | varchar(200) | no | **unique**, lowercased; the login handle (a verified work email) |
| password_hash | varchar(255) | no | bcrypt; set at signup |
| account_status | account_status | no | default `active` |
| email_verified_at | timestamptz | no | set at signup when the email code is confirmed |
| full_name | varchar(100) | no | one field — names don't always split into first/last |
| position | varchar(120) | yes | job title, free text (CEO, Director, Export Manager) — display only |
| phone | varchar(20) | yes | |
| phone_normalized | varchar(20) | yes | **unique**; digits and `+` only, synced automatically |
| session_version | integer | no | default 0; also stamped in the session cookie. Bumping it rejects every older cookie → logs out all devices (password change, "log out everywhere", account deletion) |
| consent_at | timestamptz | yes | terms/privacy acceptance (DPDP / PDPL) |
| consent_version | varchar(30) | yes | |
| last_login_at | timestamptz | yes | |
| created_at | timestamptz | no | default now() |
| updated_at | timestamptz | no | default now(), on update |
| deleted_at | timestamptz | yes | soft delete (DPDP erasure; email anonymised) |

Indexes: `uq_users_email`, `uq_users_phone_normalized`, `ix_users_business_id`.

## 3. `email_codes`

One-time 6-digit codes sent to an inbox. Keyed by email because the user does
not exist yet at signup.

| Column | Type | Null | Notes |
|---|---|---|---|
| id | uuid | no | PK |
| email | varchar(200) | no | lowercased; indexed |
| purpose | email_code_purpose | no | `signup` now |
| code_hash | char(64) | no | SHA-256 of the code (+ server secret); never stored plain |
| attempts | integer | no | default 0; code is dead after 5 wrong tries |
| expires_at | timestamptz | no | 10 minutes after issue |
| verified_at | timestamptz | yes | set when the correct code is entered |
| consumed_at | timestamptz | yes | set when the account is created with it (single use) |
| created_at | timestamptz | no | default now() |

Index: `ix_email_codes_email_purpose` (email, purpose). Issuing a new code for
the same email + purpose invalidates older ones. Sending is rate-limited per
email and per IP.

## 4. `business_documents`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | uuid | no | PK |
| business_id | uuid | no | FK → businesses.id, ON DELETE CASCADE; indexed |
| uploaded_by_user_id | uuid | yes | FK → users.id, ON DELETE SET NULL |
| doc_type | varchar(150) | no | e.g. "GST Certificate", "FSSAI License", "IEC" |
| original_filename | varchar(300) | no | |
| storage_key | varchar(400) | no | key in storage (local disk / S3) |
| mime_type | varchar(120) | no | detected from file bytes (PDF/JPEG/PNG/WEBP) |
| size_bytes | integer | no | max 10 MB |
| status | doc_status | no | default `pending` |
| rejection_reason | varchar(500) | yes | |
| reviewed_at | timestamptz | yes | |
| reviewed_by | varchar(200) | yes | admin email |
| uploaded_at | timestamptz | no | default now() |

Files are served only to users of the owning business and to admins.

## 5. `products` (listings)

| Column | Type | Null | Notes |
|---|---|---|---|
| id | uuid | no | PK |
| business_id | uuid | no | FK → businesses.id, ON DELETE CASCADE — the owner |
| created_by_user_id | uuid | yes | FK → users.id, ON DELETE SET NULL |
| name | varchar(200) | no | 2–200 chars |
| category | varchar(50) | no | Rice · Sugar · Wheat · Pulses · Spices · Oilseeds · Cotton · Millets · Tea · Coffee · Other |
| variety | varchar(100) | yes | |
| origin_state | varchar(100) | yes | |
| packaging | varchar(50) | yes | Jute · PP woven · HDPE · Bulk · Other |
| quantity | numeric(12,2) | yes | ≥ 0 |
| unit | varchar(10) | no | `MT` · `kg` · `quintal`; default `MT` |
| moq | numeric(12,2) | yes | ≥ 0, ≤ quantity |
| price_per_unit | numeric(12,2) | yes | ≥ 0 |
| currency | char(3) | no | ISO 4217; default `INR` |
| description | text | yes | ≤ 5000 chars |
| photos | json | no | list of 1–5 URLs produced by our upload route |
| created_at | timestamptz | no | default now() |
| updated_at | timestamptz | no | default now(), on update |
| deleted_at | timestamptz | yes | soft delete (seller removes a listing) |

Indexes: `ix_products_business_id`, `ix_products_category_created_at`.

**Visible in the market** when: product not deleted AND owning business
`verified` AND not deleted.

## 6. `contact_reveals`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | uuid | no | PK |
| buyer_business_id | uuid | no | FK → businesses.id, ON DELETE CASCADE |
| revealed_by_user_id | uuid | yes | FK → users.id, ON DELETE SET NULL |
| seller_business_id | uuid | no | FK → businesses.id, ON DELETE CASCADE |
| product_id | uuid | no | FK → products.id, ON DELETE CASCADE |
| revealed_at | timestamptz | no | default now() |

Constraints: **unique (buyer_business_id, product_id)**; index
(buyer_business_id, revealed_at) for the 20-per-hour limit per buyer business.
Rule: buyer and seller businesses must both be `verified`; a business cannot
reveal its own listing.

## 7. `admin_actions`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | uuid | no | PK |
| admin_email | varchar(200) | no | |
| action | varchar(50) | no | `business.verify` · `business.reject` · `business.update` · `doc.approve` · `doc.reject` |
| target_type | varchar(30) | no | `business` · `user` · `document` |
| target_id | varchar(64) | no | target UUID as text |
| reason | varchar(500) | yes | |
| details | json | yes | e.g. edited field names |
| created_at | timestamptz | no | default now() |

Indexes: (target_type, target_id), (created_at). Admin login stays
environment-configured (single operator); an `admin_users` table comes when
there is more than one operator.

## Flows on this schema

**Signup (one screen)**
1. User enters work email → domain check (no free-mail / disposable) →
   `email_codes` row (`signup`, 10 min) → code emailed.
2. User enters the code → `verified_at` set.
3. Full name, position, password, terms consent appear → submit →
   in one transaction: `businesses` (`draft`), `users` (`owner`, `active`,
   `email_verified_at`), code `consumed_at` → logged in.

**Browse** — any logged-in user can explore the market.

**Verify the business** — fill the Passport (7 mandatory fields, optional
documents) → "Send for verification" → `pending_verification` → admin approves
(`verified`) or rejects (`rejected` + reason) → `admin_actions` row + email.

**Sell** — listings can be created any time; visible only once `verified`.

**Buy** — revealing a seller's contact requires both businesses `verified`.

**Future** — password reset reuses `email_codes` (`reset_password`); team
members are invited with `email_codes` (`invite`) and get `users` rows with the
same `business_id` and `admin`/`member` roles.

## Migration from the current schema (`0019_business_entity`)

| Current | Target |
|---|---|
| `business_profiles` | renamed `businesses`; per-user 1:1 link dropped |
| `users.status` (verification part) + `verification_submitted_at`, `verified_at`, `verification_rejected_reason` | moved to `businesses` (`verified`→`verified`, `rejected`→`rejected`, `pending_verification`→`pending_verification`, else `draft`) |
| `users` | gains `business_id`, `role` (`owner`), `account_status` (`active`), person fields from `profiles` |
| `profiles.full_name`, `phone`, `position`, `consent_*` | → `users` |
| `profiles.department` | dropped |
| `profiles.address_line`, `city`, `state`, `pincode`, `country`, `google_business_url`, `facebook_url` | → `businesses` (country converted to ISO alpha-2) |
| `profiles.website_url` | → `businesses.website_url` if the business has none |
| `profiles` | dropped |
| `verification_docs` | renamed `business_documents`; `cert_type`→`doc_type`, `filename`→`original_filename`, `stored_path`→`storage_key`; `user_id` → `business_id` + `uploaded_by_user_id` |
| `products.user_id` | → `business_id` + `created_by_user_id`; new `currency` (`INR`), `deleted_at` |
| `contact_reveals.buyer_id` / `seller_id` | → `buyer_business_id` + `revealed_by_user_id` / `seller_business_id` |
| `temp_credentials` | dropped; replaced by `email_codes` |
| `users.must_change_password`, `UserStatus.active` | dropped |
| business columns `main_objective`, `business_role`, `nature_of_business`, `business_type`, `udyam`, `bank_*`, `ifsc_verified_at`, `onboarded_at` | dropped |
| 3-letter country codes in arrays | converted to alpha-2 |

Every existing user gets exactly one business (their current business profile,
or a new `draft` one) and becomes its `owner`. **Accounts that never set a real
password (only ever had a temporary password) are deleted** by the migration,
together with their business data — there is no production data yet.

## Why each users / email_codes / contact_reveals column exists

- `role` vs `position`: role = permissions (system-set), position = job title
  (display). They can differ (an Export Manager may own the account).
- `consent_at` / `consent_version`: proof of Terms/Privacy acceptance and which
  version, required by DPDP (India) / PDPL (UAE).
- `email_codes.created_at`: resend cooldown, per-email/IP send limits, cleanup;
  `verified_at`: gates the account-creation step and bounds it to 30 minutes;
  `consumed_at`: single use, funnel metrics.
- `contact_reveals`: the ledger of introductions — idempotent re-display,
  anti-scraping limit, proof of introduction (circumvention), seller interest
  insight, buyer "my contacts", ops visibility and analytics.

## Indexes and table-level constraints

Rule: every index below exists because a real query needs it (or it backs a
uniqueness/integrity rule). No speculative indexes — each one costs write speed.
Integrity rules live in the database (UNIQUE / CHECK / FK), so a bug or a race in
application code can never store bad data. Partial indexes (`WHERE …`) work on
both Postgres and SQLite.

### businesses
| Name | Definition | Why |
|---|---|---|
| `uq_businesses_legal_name_normalized` | UNIQUE (legal_name_normalized) WHERE deleted_at IS NULL | one live company per legal name (deleted ones don't block re-registration) |
| `uq_businesses_website_normalized` | UNIQUE (website_normalized) WHERE deleted_at IS NULL | one live company per website |
| `ix_businesses_verification_queue` | (verification_status, verification_submitted_at) | admin KYB queue (pending, oldest first); market join on `verified` |
| `ck_businesses_trade_position` | CHECK trade_position IN ('seller','buyer','both') OR NULL | |
| `ck_businesses_entity_type` | CHECK entity_type IN (…5 values…) OR NULL | |
| `ck_businesses_country` | CHECK length(country) = 2 | ISO alpha-2 |
| `ck_businesses_verified_has_date` | CHECK verification_status <> 'verified' OR verified_at IS NOT NULL | state consistency |
| `ck_businesses_rejected_has_reason` | CHECK verification_status <> 'rejected' OR verification_rejected_reason IS NOT NULL | the user always sees why |
| `ck_businesses_submitted_has_date` | CHECK verification_status = 'draft' OR verification_submitted_at IS NOT NULL | |

### users
| Name | Definition | Why |
|---|---|---|
| `uq_users_email` | UNIQUE (email) | login lookup + one account per email |
| `ck_users_email_lowercase` | CHECK email = lower(email) | stops `A@x.com` / `a@x.com` duplicates |
| `uq_users_phone_normalized` | UNIQUE (phone_normalized) WHERE deleted_at IS NULL | one live account per phone |
| `uq_users_one_owner_per_business` | UNIQUE (business_id) WHERE role = 'owner' AND deleted_at IS NULL | exactly-one-owner rule, ready for teams |
| `ix_users_business_id` | (business_id) | users of a business; FK lookups |
| `ck_users_session_version` | CHECK session_version >= 0 | |

### email_codes
| Name | Definition | Why |
|---|---|---|
| `ix_email_codes_lookup` | (email, purpose, created_at DESC) | latest code for an email; cooldown + "5 per hour" counts |
| `ix_email_codes_expires_at` | (expires_at) | cleanup job |
| `ck_email_codes_attempts` | CHECK attempts BETWEEN 0 AND 5 | |
| `ck_email_codes_order` | CHECK consumed_at IS NULL OR verified_at IS NOT NULL | can't consume an unverified code |

### business_documents
| Name | Definition | Why |
|---|---|---|
| `ix_business_documents_business` | (business_id, uploaded_at DESC) | a business's documents, newest first |
| `ix_business_documents_pending` | (uploaded_at) WHERE status = 'pending' | admin document queue |
| `ix_business_documents_uploaded_by` | (uploaded_by_user_id) | FK (SET NULL on user delete) |
| `ck_business_documents_size` | CHECK size_bytes > 0 AND size_bytes <= 10485760 | 10 MB cap |
| `ck_business_documents_rejected_reason` | CHECK status <> 'rejected' OR rejection_reason IS NOT NULL | |

### products
| Name | Definition | Why |
|---|---|---|
| `ix_products_market` | (category, created_at DESC) WHERE deleted_at IS NULL | public market: category filter, newest first |
| `ix_products_market_all` | (created_at DESC) WHERE deleted_at IS NULL | market "All" view |
| `ix_products_business` | (business_id, created_at DESC) WHERE deleted_at IS NULL | seller's listings page; visibility join |
| `ix_products_created_by` | (created_by_user_id) | FK (SET NULL) |
| `ck_products_category` | CHECK category IN (11 values) | |
| `ck_products_unit` | CHECK unit IN ('MT','kg','quintal') | |
| `ck_products_currency` | CHECK length(currency) = 3 | ISO 4217 |
| `ck_products_amounts` | CHECK quantity >= 0 AND moq >= 0 AND price_per_unit >= 0 (each when not NULL) | |
| `ck_products_moq_le_quantity` | CHECK moq IS NULL OR quantity IS NULL OR moq <= quantity | |
| `ck_products_name_length` | CHECK length(trim(name)) >= 2 | |

### contact_reveals
| Name | Definition | Why |
|---|---|---|
| `uq_contact_reveals_buyer_product` | UNIQUE (buyer_business_id, product_id) | reveal once; idempotent re-display |
| `ix_contact_reveals_buyer_time` | (buyer_business_id, revealed_at DESC) | 20-per-hour limit; buyer's "my contacts" |
| `ix_contact_reveals_seller_time` | (seller_business_id, revealed_at DESC) | seller insight ("8 buyers viewed you") |
| `ix_contact_reveals_product` | (product_id) | per-listing interest; FK cascade |
| `ix_contact_reveals_revealed_by` | (revealed_by_user_id) | FK (SET NULL) |
| `ck_contact_reveals_not_self` | CHECK buyer_business_id <> seller_business_id | no self-reveal |

### admin_actions
| Name | Definition | Why |
|---|---|---|
| `ix_admin_actions_target` | (target_type, target_id, created_at DESC) | history of one business/user/document |
| `ix_admin_actions_created_at` | (created_at DESC) | recent activity feed |
| `ix_admin_actions_admin` | (admin_email, created_at DESC) | per-operator audit |

### Later, when the catalog grows (not now)
Market text search uses `ILIKE '%term%'`, which no normal index can speed up.
Past ~10k listings, add Postgres `pg_trgm` GIN indexes on `products.name` and
`products.description` (or full-text search). Not needed at current scale.

## Exchange rates (multi-currency prices)

Principle: **a listing's price is never changed** — it is stored exactly as the
seller entered it (`price_per_unit` + `currency`). Conversion is only for
display and for comparing/filtering across currencies. The common unit is
**USD** (international commodity trade is quoted in USD/MT).

### 8. `exchange_rates`

| Column | Type | Null | Notes |
|---|---|---|---|
| id | uuid | no | PK |
| base | char(3) | no | always `USD` |
| quote | char(3) | no | ISO 4217, e.g. `INR`, `AED` |
| rate | numeric(18,8) | no | 1 USD = `rate` × quote; > 0 |
| as_of | date | no | the day the rate applies to |
| source | varchar(50) | no | `frankfurter` · `fawazahmed0` · `pegged` · `manual` |
| fetched_at | timestamptz | no | default now() |

Constraints / indexes:
| Name | Definition | Why |
|---|---|---|
| `uq_exchange_rates_quote_day` | UNIQUE (base, quote, as_of) | one rate per currency per day |
| `ix_exchange_rates_latest` | (quote, as_of DESC) | "latest rate for X" |
| `ck_exchange_rates_rate_positive` | CHECK rate > 0 | |
| `ck_exchange_rates_codes` | CHECK length(base) = 3 AND length(quote) = 3 | |

### Changes to `products`

| Column | Type | Null | Notes |
|---|---|---|---|
| price_usd | numeric(14,2) | yes | `price_per_unit ÷ rate(currency)`; NULL when there is no price |
| price_usd_as_of | date | yes | which day's rate produced `price_usd` |

| Name | Definition | Why |
|---|---|---|
| `ix_products_market_price` | (category, price_usd) WHERE deleted_at IS NULL | market price-range filter |
| `ck_products_price_usd` | CHECK price_usd IS NULL OR price_usd >= 0 | |

`price_usd` is set when a listing is created/edited (latest rate) and refreshed
for all listings after each daily rate fetch.

### Change to `users`

| Column | Type | Null | Notes |
|---|---|---|---|
| display_currency | char(3) | no | currency the user sees converted prices and types filter amounts in; default from the business country (IN → INR, AE → AED, else USD); user-changeable |

`ck_users_display_currency`: CHECK display_currency IN the supported list.

### Supported currencies
`INR`, `AED`, `USD` now (one config list; adding a currency = adding its code).
`USD`→`USD` = 1. `AED` is pegged (3.6725) and used as a fallback if no provider
returns it.

### Rate fetching
- A daily job (and on backend start if today's rates are missing) fetches
  USD-based rates for the supported currencies.
- Provider order: **Frankfurter v2** (`api.frankfurter.dev/v2/rates`, free, no
  key, open source, self-hostable) → **fawazahmed0 currency-api** (jsDelivr
  CDN, free, no key) → keep the last stored rates.
- Implemented as a swappable integration (`app/integrations/fx`), like email
  and SMS; a `console`/static provider serves fixed rates in tests and offline
  development.
- The app never calls the external API while a user waits — requests read the
  `exchange_rates` table only.

### Display & filtering rules
- Cards show the seller's real price first, conversion second:
  `AED 520 / MT · ≈ ₹11,800` (the "≈" part only when the viewer's display
  currency differs; labelled indicative, with the rate date on hover).
- The market price filter takes min/max in the viewer's display currency,
  converts them to USD and filters on `price_usd`.
- Deals are always in the seller's currency.

---

## KYB profile (`0021_kyb_profile`)

Approved 2026-10-24. Sign-up collects **full name, country, company name and
work email**; the 6-digit code proves the email; then the user sets a
password. The business profile (logo, banner, KYB entries) can be skipped and
completed later; a quick tour is offered on first sign-in.

### 9. `kyb_document_types` (new) — admin-managed list per country

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | uuid | PK | |
| `country` | char(2) | no | `IN`, `AE`… |
| `code` | varchar(40) | no | slug: `gstin`, `pan`, `udyam`, `iec`, `fssai`, `trade_licence`, `trn` |
| `name` | varchar(150) | no | dropdown label |
| `input_kind` | enum `kyb_input_kind` | no | `value` · `file` · `value_or_file` · `value_and_file` |
| `value_pattern` | varchar(200) | yes | format check (full match) |
| `value_placeholder` | varchar(60) | yes | |
| `help_text` | varchar(300) | yes | |
| `is_mandatory` | bool | no | required before KYB submission (default false) |
| `is_unique` | bool | no | one value per business across the platform (default true) |
| `sort_order` | smallint | no | default 0 |
| `active` | bool | no | hidden instead of deleted (default true) |
| `created_at` / `updated_at` | timestamptz | no | |

Constraints: `uq_kyb_document_types_country_code (country, code)`,
`ck_kyb_document_types_country`, `ck_kyb_document_types_code`,
`ck_kyb_document_types_no_aadhaar` (codes `aadhaar` / `aadhar` refused —
Aadhaar Act). Index `ix_kyb_document_types_dropdown (country, active, sort_order)`.

Seed: **IN** — GSTIN (value, mandatory), PAN (value, mandatory), Udyam (value),
IEC (value, "needed to export"), FSSAI (value + file). **AE** — Trade licence
(file, mandatory), TRN (value).

### Changes to `business_documents` — one row = one KYB entry

| Column | Change |
|---|---|
| `document_type_id` | **new** uuid → `kyb_document_types` (`ON DELETE RESTRICT`); null = "Other" |
| `doc_type` | kept — the type's name, or the custom name typed for "Other" |
| `value_encrypted` | **new** text — AES-256-GCM ciphertext; plain values are never stored |
| `value_key_version` | **new** smallint — key that encrypted it (rotation) |
| `value_hash` | **new** char(64) — HMAC-SHA256 of the normalised value (duplicate checks) |
| `value_last4` | **new** varchar(4) — masked display hint |
| `value_unique` | **new** bool — copied from the type's `is_unique` when saved |
| `original_filename`, `storage_key`, `mime_type`, `size_bytes` | now **nullable** — a file is optional |
| `updated_at` | **new** — entries can be corrected |

Constraints: `ck_business_documents_has_content` (value or file),
`ck_business_documents_file_complete` / `ck_business_documents_value_complete`
(all-or-none), `ck_business_documents_size` (null or 1 B–10 MB),
`ck_business_documents_doc_type`, existing `ck_business_documents_rejected_reason`.
Partial unique indexes: `uq_business_documents_business_type
(business_id, document_type_id) WHERE document_type_id IS NOT NULL` and
`uq_business_documents_unique_value (document_type_id, value_hash) WHERE
value_unique AND value_hash IS NOT NULL AND status <> 'rejected'`.

Existing rows keep their file and name and appear as "Other".

### Other column changes

* `businesses.logo_key`, `businesses.banner_key` — varchar(400), public images (dashboard hero).
* `users.tour_completed_at` — timestamptz; null → show the quick tour.

### Encryption keys (configuration, never in the database or git)

* `KYB_ENC_KEYS` — `version:base64key` list; newest encrypts, all decrypt.
* `KYB_HASH_KEY` — separate key for `value_hash`.
* Production refuses to start without them; development uses a marked local key.

### Access

| Data | Owner | Other businesses / public | Admin |
|---|---|---|---|
| Logo, banner, company name, verified badge | ✓ | ✓ | ✓ |
| KYB value, masked | ✓ | ✗ | ✓ |
| KYB value, full (dedicated reveal call) | ✓ own | ✗ | ✓ — logged `kyb.value_viewed` |
| KYB file | ✓ own | ✗ | ✓ — logged `kyb.file_viewed` |

### KYB submission rule

Company name + registered address with country + every **mandatory** document
type for that country. Logo, banner and other profile fields are optional.

---

## Combined KYB review (`0022_reject_items`)

Approved 2026-10-31.

* `businesses.verification_rejected_items` — JSON list, nullable. Keys the
  admin ticked when rejecting: profile fields (`legalName`, `addressLine`,
  `city`, `country`) and KYB entries (`kyb:<code>` for listed documents,
  `doc:<entry id>` for "Other"). Flagged entries are rejected with the same
  reason. Cleared on resubmit and on approval.

Rules (API, not schema):

* **Countries** — a country exists only once an admin adds it *together
  with* its documents (`POST /admin/kyb/countries`, ≥ 1 required). The last
  active required document of a country can't be hidden or made optional.
  Businesses may only pick set-up countries (`GET /kyb/countries`).
* **One review** — `/admin/verify` reviews profile and documents together.
  Approving a business approves its pending documents. The queue also lists
  verified businesses with new pending documents (reviewed per document; the
  business stays verified).
* **Re-review** — a verified business that changes its company name,
  address, city or country, or adds / changes / removes a *required*
  document, goes back to `pending_verification` (its listings leave the
  market until re-approved). The UI asks for confirmation first.

---

## Countries (`0023_countries`)

Approved 2026-10-31.

### 10. `countries`

| Column | Type | Null | Notes |
|---|---|---|---|
| `code` | char(2) | PK | ISO 3166-1 alpha-2; `ck_countries_code` (2 upper-case letters) |
| `name` | varchar(100) | no | unique (`uq_countries_name`) |
| `flag` | varchar(8) | yes | emoji |
| `dial_code` | varchar(6) | yes | `+91`; `ck_countries_dial_code` |
| `default_currency` | char(3) | no | INR / AED / USD (`ck_countries_default_currency`) — a new user's display currency |
| `region_label` | varchar(30) | no | "State", "Emirate"… (address form) |
| `postal_label` | varchar(30) | no | "PIN code", "PO Box"… |
| `postal_pattern` | varchar(100) | yes | postcode format check |
| `active` | bool | no | open for onboarding; false = paused (existing businesses unaffected) |
| `created_by` / `updated_by` | varchar(200) | no | admin email or `system` |
| `created_at` / `updated_at` | timestamptz | no | |

Index `ix_countries_active`. Never deleted.

Foreign keys (ON DELETE RESTRICT): `businesses.country` → `countries.code`
(`fk_businesses_country`), `kyb_document_types.country` → `countries.code`
(`fk_kyb_document_types_country`). `operating_countries` / `target_markets`
stay free lists (informational).

Seed: India and the UAE, plus every code already used by businesses or
document types (known codes from a 20-country reference; unknown codes as a
paused placeholder named by its code).

Rules: a country is offered to businesses when `active` **and** it has an
active required document. `POST /admin/kyb/countries` creates (or completes a
seeded) country together with its documents; `PATCH /admin/kyb/countries/{code}`
edits details or pauses / resumes. Postcodes are checked against
`postal_pattern`. Changes are audited (`kyb_country.create` / `kyb_country.update`).

## Identity & access (`0024_identity_access`)

Phase A of the security plan (`docs/05_security_review.md`). Signed cookies
are replaced by server-side sessions; every cookie issued before 0024 stops
working (users sign in again).

### 11. `admin_users` — named admin accounts

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | uuid | PK | |
| `email` | varchar(200) | no | unique (`uq_admin_users_email`), lower-case (`ck_admin_users_email_lowercase`) |
| `full_name` | varchar(100) | no | |
| `role` | enum `admin_role` | no | `super_admin` \| `reviewer` (permissions in `app/modules/admin/permissions.py`) |
| `status` | enum `admin_status` | no | `active` \| `disabled` (disabling ends the session) |
| `password_hash` | varchar(255) | no | bcrypt |
| `must_change_password` | bool | no | temporary password — only `/admin/me` + `/admin/change-password` until changed |
| `password_changed_at` | timestamptz | yes | |
| `failed_login_count` / `lockout_count` / `locked_until` | int / int / timestamptz | no / no / yes | lockout (below) |
| `last_login_at` | timestamptz | yes | |
| `created_by` | varchar(200) | no | creator's email or `bootstrap` |
| `created_at` / `updated_at` | timestamptz | no | |

Empty after the migration: signing in with `ADMIN_EMAIL` / `ADMIN_PASSWORD_HASH`
while it is empty creates the first super admin.

| Permission | super_admin | reviewer |
|---|---|---|
| `dashboard.view`, `users.view`, `users.edit` | ✓ | ✓ |
| `kyb.review` (verify / reject businesses and documents) | ✓ | ✓ |
| `kyb.sensitive_view` (reveal numbers, open files — audited) | ✓ | ✓ |
| `catalog.view` (countries, document types) | ✓ | ✓ |
| `catalog.manage` (create / edit countries, document types) | ✓ | |
| `accounts.security` (unlock traders, sign them out) | ✓ | |
| `admins.manage` (create / edit / reset / unlock / sign out admins) | ✓ | |

### 12. `user_sessions` / `admin_sessions` — server-side sessions

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | uuid | PK | |
| `user_id` / `admin_user_id` | uuid | no | FK → `users` / `admin_users`, ON DELETE CASCADE |
| `token_hash` | char(64) | no | SHA-256 of the cookie token; unique |
| `created_at` | timestamptz | no | |
| `last_seen_at` | timestamptz | no | refreshed ≤ once a minute; idle expiry = this + idle TTL |
| `expires_at` | timestamptz | no | absolute cap |
| `revoked_at` / `revoked_reason` | timestamptz / varchar(30) | yes | `logout`, `replaced`, `logout_all`, `password_changed`, `password_reset`, `account_deleted`, `account_disabled`, `admin_revoked` |
| `ip_prefix` | varchar(64) | yes | truncated IP — IPv4 /24, IPv6 /48 (never the full address) |
| `user_agent` | varchar(200) | yes | |

Partial unique index `uq_*_one_active` on the owner where `revoked_at IS NULL`
→ **one active session per account**; a new sign-in revokes the old one
(`replaced`). Timeouts: traders 12 h idle / 7 days absolute; admins 30 min /
8 h (`USER_SESSION_*`, `ADMIN_SESSION_*`).

### 13. `auth_events` — security log

`subject_type` (`user` | `admin`), `subject_id` (null for an unknown email —
the email isn't stored), `event` (`login_succeeded`, `login_failed`,
`locked`, `locked_support`, `unlocked`, `logout`, `session_replaced`,
`sessions_revoked`, `password_changed`, `password_reset_requested`,
`password_reset`), `ip_prefix`, `user_agent`, `details` (JSON), `created_at`.
Indexes `ix_auth_events_subject`, `ix_auth_events_created_at`.

### Changes to `users` and `admin_actions`

* `users.failed_login_count`, `users.lockout_count` (≥ 0 checks), `users.locked_until`.
  Lockout: 5 wrong passwords → 15 min; the next → 30 min; the 3rd lockout →
  locked until support unlocks (`lockout_count ≥ 3`, `locked_until` null).
  A successful sign-in resets both counters; a password reset clears a
  temporary lock but not a support lock.
* `admin_actions.admin_user_id` → `admin_users.id` (ON DELETE SET NULL; null
  for rows before 0024). `admin_email` is kept for readability.
* `users.session_version` is no longer read (kept for history; still bumped).
