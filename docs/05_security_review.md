# Security & data-protection review — Corridor One X

**Date:** 31 October 2026 · **Code:** `main` @ `6a50644` + ported QA suite · **Scope:** backend API, web app, data at rest, dependencies
**Policy checked against:** the security plan agreed in this project (authentication, authorization, data storage — 36 items, tracker CX-031…CX-060) and the data-handling commitments in the Platform Overview (DPDP Act 2023, UAE PDPL, CERT-In).

## How this was checked

Evidence, not code reading alone:

| Method | What it covered |
|---|---|
| Route inventory (programmatic, all 64 API routes) | Which authentication each endpoint requires |
| Live probes against the running API | Cookie flags, CSRF, CORS, enumeration, cross-business access, admin access, tampered cookies, path traversal, response headers, data in responses |
| Database scan (every text column of every table) | Plaintext GSTIN / PAN / FSSAI / Aadhaar-like values, password and code hashing, encryption coverage |
| File scan (email outbox, uploads) and live server logs | Secrets or personal data written to disk / logs |
| Git scan | Committed secrets, keys, databases |
| Dependency audit (`pip-audit`, `npm audit --omit=dev`) | Known vulnerabilities (CVE / GHSA) |
| Automated tests — **191 passing** | Business rules, ownership checks, encryption, audit, migrations (incl. 44 QA flow tests) |

Status: ✅ meets policy · ⚠️ partial · ❌ gap · ⏳ planned (agreed phase) · 🔧 deploy-time (can't be verified locally).

---

## 1. Executive summary

**Strong today:** access control between businesses, encryption and masking of KYB numbers, no secrets or personal data in logs or git, cross-site request protection, audited admin views, KYB data removed on account deletion, Aadhaar blocked.

**Must fix before real data** (in priority order):

1. **Admin access is one shared password with no 2FA** — no individual accountability. *(Phase A: named admins + roles; 2FA before launch.)*
2. **Known vulnerabilities in dependencies** — 1 critical (Next.js) and several high (Starlette, python-multipart, cryptography, Jinja2). *(Upgrade — new item.)*
3. **Insecure defaults** — `DEBUG` defaults to true and session secrets default to dev strings; production only refuses to start for missing KYB keys. *(CX-001.)*
4. **Session cookie `Secure` flag depends on `CROSS_SITE_COOKIES`** — a same-domain HTTPS deployment would send the session cookie without `Secure`. *(New finding.)*
5. **No security headers / no `Cache-Control: no-store`** on personal responses. *(Phase A.)*
6. **Files on local disk, unencrypted at rest; no malware scan.** *(Phase B.)*

**Scorecard** (64 controls): ✅ 30 · ⚠️ 5 · ❌ 11 · ⏳ 14 · 🔧 4

---

## 2. Authentication

| ID | Control | Policy | Status | Evidence |
|---|---|---|---|---|
| A1 | Password storage | Slow salted hash | ✅ | All `users.password_hash` are bcrypt (`$2b$`); >72-byte passwords refused |
| A2 | Equal timing for unknown emails | No account enumeration | ✅ | Dummy hash verified for unknown emails (`auth/service.py`) |
| A3 | Generic login error | No account enumeration | ✅ | Wrong password and unknown email both return "Invalid email or password." |
| A4 | Signup email proof | Work email, one-time code | ✅ | Personal/disposable domains refused; codes HMAC-hashed (64-char), 10-min TTL, 5 attempts, single use |
| A5 | Session cookie | HttpOnly, signed, revocable | ✅ | `HttpOnly; SameSite=lax`; tampered cookie → 401; "log out everywhere" revoked a second device (401) |
| A6 | Session cookie `Secure` in production | Always over HTTPS | ❌ | `Secure` only when `CROSS_SITE_COOKIES=true` (`core/security.py`) — **new finding** |
| A7 | One active device per user | Agreed rule (new login replaces old) | ⏳ A | Today two devices were signed in at once (both 200) |
| A8 | Session lifetime / idle timeout | 12h idle · 7d max (users); 30m / 8h (admins) | ⏳ A | Today fixed 24h (users), 12h (admins) |
| A9 | Account lockout | 5 fails → 15 min, doubling | ⏳ A | Not present; only rate limits |
| A10 | Password reset | Email code; revoke all sessions | ⏳ A | Not present (CX-005) |
| A11 | Rate limits on auth | Per IP + per email | ⚠️ | Present on signup/login/admin login; **in-memory** — reset on deploy, not shared across instances (CX-009) |
| A12 | Admin authentication | Named accounts, roles | ❌ → A | **Single shared password** (`ADMIN_PASSWORD_HASH`); admin cookie can't be revoked (CX-029) |
| A13 | Two-factor (admins + users) | Mandatory | ⏳ B (before launch) | Not present — moved to pre-launch by decision |
| A14 | New-device / password-change alerts | Email the user | ⏳ A/B | Not present |

## 3. Authorization & access to data

| ID | Control | Policy | Status | Evidence |
|---|---|---|---|---|
| B1 | Every non-public route authenticated | Deny by default | ✅ | Inventory: 26 user, 21 admin, 17 public-by-design routes; no `/me` or `/admin` route without auth (only `/admin/logout`, harmless) |
| B2 | Cross-business access (BOLA) | Owner only; no existence leak | ✅ | Live: another business's file → 404; tests: stranger can't list/reveal/edit/delete/download entries |
| B3 | User session on admin routes | Refused | ✅ | `/admin/verify/queue`, `/admin/docs/{id}/reveal` with user cookie → 401 |
| B4 | KYB file access | Owner or admin only | ✅ | No session → 401; legacy public path → 404 |
| B5 | Public market masking | No seller name / contact | ✅ | `/public/products` seller keys = `city, sellerId, state, verified`; no emails in response |
| B6 | Contact reveal | Verified buyer ↔ verified seller; limited | ✅ | Tests: gates + 20 new reveals / business / hour |
| B7 | Full KYB numbers only on deliberate action | Masked in lists | ✅ | Live: no full GSTIN/PAN in `/me` or the entry list; reveal rate-limited (30/h user, 200/h admin) |
| B8 | Admin roles (super admin / reviewer) | Least privilege | ❌ → A | All admins can do everything |
| B9 | Route-permission matrix test | Every admin route declares a permission | ⏳ A | Not present |
| B10 | Reason required for admin reveal/download | Purpose-bound access | ⏳ A | Views are audited, no reason captured |
| B11 | Tenant isolation at database level | Row-level security | ⏳ C | App-level checks only |
| B12 | Super admin only: countries & admin users | Agreed | ⏳ A | Today any admin can manage countries/doc types |

## 4. Data protection

| ID | Control | Policy | Status | Evidence |
|---|---|---|---|---|
| C1 | KYB numbers encrypted at rest | AES-256-GCM, app-level | ✅ | DB scan: **no plaintext GSTIN/PAN/FSSAI anywhere**; all value entries have ciphertext + key version (matches were example placeholders and phone numbers only) |
| C2 | Duplicate numbers without decrypting | Keyed hash | ✅ | `value_hash` (HMAC-SHA256) + partial unique index; tests |
| C3 | Masked display | Last 4 only | ✅ | `valueMasked` e.g. `••••K1Z9` |
| C4 | Keys outside DB/git; rotatable; refuse to start without them | — | ✅ | `KYB_ENC_KEYS` / `KYB_HASH_KEY` env, versioned; production refusal tested |
| C5 | Keys in a key-management service | Vault / KMS | ⏳ B | Env keys today |
| C6 | Aadhaar never collected | Aadhaar Act | ✅ | DB check constraint + API refuse Aadhaar types / "Other" names |
| C7 | No secrets / personal data in logs | — | ✅ | Access log = method, path, status, duration, request ID; **no IPs, bodies or PII**; scan of outbox/uploads: no KYB numbers |
| C8 | Actor in access logs (who did it) | Investigations / CERT-In | ⚠️ | Request log has no user/admin ID (admin actions *are* attributed in `admin_actions`) — **new finding** |
| C9 | Admin views audited | Every number reveal / file view | ✅ | `kyb.value_viewed`, `kyb.file_viewed` rows confirmed; no values in details |
| C10 | Audit log tamper-evident / append-only | Hash chain; insert-only role | ⏳ A/B | Ordinary table today |
| C11 | Files encrypted at rest, private bucket | S3/MinIO + KMS | ❌ → B | Server disk (`uploads/`), not encrypted; not durable on Railway restarts (CX-004/CX-010) |
| C12 | Upload safety | Type from content, size limits | ✅ | Magic-byte sniffing (PDF/JPEG/PNG/WEBP), 10 MB / 5 MB limits, sanitised names, `nosniff`; disguised HTML refused (test) |
| C13 | Malware scan of uploads | ClamAV | ❌ → B | Not present |
| C14 | Path traversal | Blocked | ✅ | `/uploads/products/..%2F..%2F.env`, `/uploads/branding/..%2F..%2Fcor1x.db` → 404 |
| C15 | Erasure on account deletion | Anonymise + remove KYB | ✅ | Personal fields anonymised, sessions revoked, KYB entries + files deleted (tests) |
| C16 | Replaced files removed | No orphaned KYB copies | ✅ | Old file deleted when an entry or logo/banner is replaced; ⚠️ orphaned product photos remain (CX-015) |
| C17 | No secrets in git | — | ✅ | No `.env`, keys or databases tracked; no key-like strings in code |
| C18 | Database private network, TLS, least-privilege roles | — | 🔧 B | Railway configuration — not verifiable locally (CX-013) |
| C19 | Encrypted backups + tested restore | — | 🔧 B | Not verified |

## 5. Platform & application security

| ID | Control | Policy | Status | Evidence |
|---|---|---|---|---|
| D1 | Cross-site request forgery | Origin check | ✅ | `POST` from `https://evil.example` → 403 |
| D2 | CORS | Allow-list | ✅ / ⚠️ | Foreign origin gets no CORS header; ⚠️ any `localhost` port is always allowed, also in production (CX-012) |
| D3 | Input validation | Strict schemas | ✅ | Pydantic models with lengths/patterns; DB constraints |
| D4 | Security headers (HSTS, CSP, X-Frame-Options, Referrer-Policy, Permissions-Policy) | Required | ❌ → A | None sent (checked on `/me`) |
| D5 | `Cache-Control: no-store` on personal responses | Required | ❌ → A | Not sent on `/me` (KYB files do send `private, no-store`) |
| D6 | Insecure defaults | Refuse to start | ❌ | `DEBUG=true` and dev session secrets by default (CX-001) |
| D7 | Dependencies free of known vulnerabilities | — | ❌ | See §7 — **new item** |
| D8 | WAF / bot protection / DDoS | Cloudflare | ⏳ B | Not present |
| D9 | Security scanning in CI | Dependabot, CodeQL, pip-audit | ⏳ B | Not present (this review ran it manually) |
| D10 | Central logging + alerts, 180-day retention | CERT-In | 🔧 B | Not present |

## 6. Privacy & compliance (DPDP / PDPL / CERT-In)

| ID | Control | Status | Evidence |
|---|---|---|---|
| E1 | Consent recorded (date + policy version) | ✅ | `users.consent_at`, `consent_version` |
| E2 | Purpose limitation / minimisation | ✅ | No card, bank or Aadhaar data; public views minimal |
| E3 | Right to access & correct | ✅ | `/me`, business profile, entry list; documents downloadable by owner |
| E4 | Right to erasure | ✅ | Self-service deletion (C15) |
| E5 | Data export (machine-readable copy) | ⚠️ | No one-click export yet |
| E6 | Retention periods defined + enforced | ❌ | Not defined (CX-054) |
| E7 | Breach runbook (6-hour CERT-In) | ❌ | Not written (CX-055) |
| E8 | Privacy Policy matches reality | ⚠️ | Text outdated (CX-006) |
| E9 | Hosting location / cross-border (UAE) | 🔧 | Railway (Singapore) for testing; client's own server later — counsel to confirm |

## 7. Dependency vulnerabilities (31 Oct 2026)

| Package | Version | Advisories | Upgrade to | Severity / note |
|---|---|---|---|---|
| **next** (frontend) | 14.2.x | critical | next 16.x (breaking) or latest patched 14.x/15.x line | **Critical** — plan an upgrade |
| postcss (via next) | — | 1 | with next | High |
| zod | <4.6.6 | 1 | 4.6.7 (breaking) | High |
| source-map-js | 1.2.1 | 1 | `npm audit fix` | High (build-time) |
| **starlette** (FastAPI) | 0.40.0 | 7 | ≥ 1.3.1 (with a FastAPI upgrade) | High — request handling / DoS |
| **python-multipart** | 0.0.12 | 7 | ≥ 0.0.31 | High — upload parsing DoS |
| **cryptography** | 46.0.3 | 7 | ≥ 50.0.0 | High |
| jinja2 | 3.1.4 | 3 | ≥ 3.1.6 | Medium (templates are ours) |
| python-dotenv | 1.0.1 | 1 | ≥ 1.2.2 | Low |

---

## 8. Findings & actions (prioritised)

| # | Severity | Finding | Action | When |
|---|---|---|---|---|
| F1 | Critical | Shared admin password, no roles, non-revocable admin cookie | Named admins (super admin / reviewer), permissions, server-side admin sessions | Phase A |
| F2 | Critical | Next.js critical advisory | Upgrade Next.js (test the app after) | Now |
| F3 | High | Backend dependency advisories (Starlette, python-multipart, cryptography, Jinja2) | Upgrade FastAPI/Starlette, python-multipart, cryptography, Jinja2; run full tests | Now |
| F4 | High | Insecure defaults (DEBUG, session secrets) | Refuse to start in production with defaults (CX-001) | Phase A |
| F5 | High | `Secure` cookie flag tied to `CROSS_SITE_COOKIES` | Always `Secure` when not in debug / on HTTPS | Phase A (small) |
| F6 | High | No security headers; no `no-store` on personal data | Add headers middleware (X-Frame-Options `SAMEORIGIN` to keep PDF previews) | Phase A |
| F7 | High | No lockout, no password reset, concurrent sessions | Server-side sessions (one device), lockout, reset | Phase A |
| F8 | High | Files on disk, unencrypted, no malware scan | Private S3-compatible storage (MinIO on own server), ClamAV | Phase B |
| F9 | High | No 2FA | Mandatory 2FA, admins + users | Phase B (before launch) |
| F10 | Medium | In-memory rate limits | Redis-backed limiter | Phase B |
| F11 | Medium | Access logs lack actor ID | Add user/admin ID (not IP) to the request log | Phase A (small) |
| F12 | Medium | Audit log not tamper-evident | Hash chain + insert-only DB role | Phase A/B |
| F13 | Medium | CORS allows any localhost in production | Only in debug (CX-012) | Phase A (small) |
| F14 | Medium | Retention, breach runbook, privacy text | Agree with counsel; write runbook; update policy | Before launch |
| F15 | Low | DB network / roles / backups unverified | Verify on Railway; plan for own server | Phase B |
| F16 | Low | Old migration 0010 can't build a fresh SQLite DB | Fix or squash old migrations | Later |

## 9. Revised roadmap

| Phase | Scope |
|---|---|
| **Now** | F2, F3 dependency upgrades |
| **A — identity & access core** | F1 admins + roles (super admin, reviewer) + permission matrix test; F7 server-side sessions (one device, new login replaces old), device list, remote logout, lockout, password reset; F4 insecure defaults; F5 Secure cookie; F6 security headers + no-store; F11 actor in logs; F13 CORS; reveal reasons; IP-allowlist setting (off); super-admin-only countries/admins |
| **B — before launch** | F9 **mandatory 2FA (admins + users)**; F8 private encrypted file storage + malware scan; F10 Redis limits; F12 append-only audit; Vault/KMS keys; Cloudflare; central logs (180 days); DB network/roles/backups; IP allowlist on; F14 legal items; penetration test decision |
| **C — after launch** | Passkeys, admin SSO, row-level security, crypto-shredding, ISO 27001 / SOC 2 readiness |
