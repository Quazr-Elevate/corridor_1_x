---
name: cor1x-backend
description: The Cor1x (Corridor One X) backend engineering standard — how this team designs, builds, secures, tests and ships the FastAPI backend in corridor_1_x, milestone by milestone. Use it for ANY backend work in this repo, however small. Writing or changing an endpoint, schema, model, Alembic migration, service, permission, rate limit, integration or test. Planning, reviewing or running a milestone (M0–M7) or sprint (S1–S15), or preparing a design review. Picking up or closing a tracker row (CX-###). Writing a backend commit message or PR description, or doing a security pass on backend code. Use it even for a one-line fix or a renamed field; keeping every session consistent with the team's code is the point.
---

# Cor1x backend

This is how the Cor1x backend gets built. It exists so that every change, made in
any session by anyone, reads like it came from the same careful team, and so the
API and its security stay one coherent thing across eight milestones.

The codebase is the first authority. This skill describes it, and where they
disagree, the code that already works wins until a decision says otherwise. When
you find a disagreement, raise it rather than quietly picking a side.

## The product, in one paragraph

Cor1x is a B2B agri-trade platform for India ⇄ UAE and beyond. Businesses pass
KYB, list products, and (per the client brief) trade through Corridor One X as
the counterparty on both sides, with identities masked through delivery. That
means the backend will hold passports, tax numbers, bank details, contracts and
money. Every habit below follows from that.

## Mindset

Work like a senior engineer who will be paged when this breaks and who has to
explain every decision to the client.

- **Read before you write.** Open the module you are changing and its
  neighbours. Follow the existing pattern, even where you'd have done it
  differently. A second way of doing the same thing costs more than either way.
- **Boring and explicit beats clever.** Plain functions, obvious names, one
  responsibility each. Someone tired at 2 a.m. should be able to read it.
- **The database is the last line.** Put invariants in constraints, not only in
  Python, because the app will someday have a bug and the constraint will not.
- **Design the failure path first.** Ask what happens on a duplicate request, a
  stale write, a half-finished transaction or a refused payment before you write
  the happy path, and especially for anything touching money or identity.
- **Smallest change that fully solves it.** Don't refactor what you weren't asked
  to touch. If you see something wrong nearby, note it as a tracker row; don't
  fold it into the diff.
- **Leave evidence, not claims.** A test, a migration that ran, a command and its
  output. "It should work" is not a status.

## Before writing anything

1. **Place the work.** Find its tracker row (`docs/tracker/cor1x-tracker.xlsx`,
   sheet *Tracker*): the milestone, the sprint, the plan section, and the **Done
   when**. If there's no row, the work isn't planned. Say so and propose one.
   The full specification is the build plan (`build-plan-final.html`, sections
   01–22). It isn't in the repository yet, so rows carry the section number;
   ask for the plan when a section's detail matters.
2. **Check the design gate.** The team agreed to discuss design before code:
   schemas, endpoints, what goes in and what comes back. So a milestone's code
   starts only after its design is approved and recorded in
   `docs/milestones/Mx_design.md`. Open `references/decisions.md` to see what's
   approved.
   - If the user **states the design themselves** ("drop the reveal limit to 10
     an hour and store the reviewer's reason on the audit row"), that is the
     approval for that change. Build it, and record it in `decisions.md`.
   - If they ask you to **pick up or do a row** in a milestone whose design isn't
     approved ("start CX-074"), what they agreed to is to see the design first. So
     present that row's design — schema, endpoints with request and response,
     errors, security — using `assets/design-review-template.md`, and ask before
     writing code. It's usually a short message, not a delay.
3. **Check pending decisions.** Some standards are *proposed* but not approved
   (the `/v1` prefix, the error contract, strict request bodies and more, all in
   `references/decisions.md`). Don't build a proposed change on your own
   initiative, and don't build *against* it either. If your change would be
   different under the proposal, say so and ask.
4. **Read the code you'll change.** `references/architecture.md` says where
   everything lives and shows the real patterns.

## The order of work

**Milestone.** Design review → user approves → record it in
`docs/milestones/Mx_design.md` and adjust tracker rows → build the sprints →
check the exit gate → milestone done. See `references/milestones.md`.

**Sprint.** Two weeks, Monday to Friday. Take rows in the sprint's order. One
branch and one PR per row (`feat/cx-071-listing-review`). At sprint review,
reconcile every row in the sprint against `main` and move unfinished rows to the
next sprint openly, never silently.

**Row.** Always in this order, backend before UI:

1. **Schema**: model, numbered migration with backfill, `docs/04_data_model.md`
2. **Logic**: service functions, domain errors, one transition function per status
3. **API**: request and response schemas, router, the right auth dependency
4. **Security pass**: the checklist in `references/security.md`
5. **Tests**: rule, happy path, refusal, cross-business access, and the migration if data moves
6. **UI**: the typed client call, then the page (frontend work follows its own conventions)
7. **Docs**: `06_feature_catalogue.md` if customers see it, `05_security_review.md` if a control changed
8. **PR**: CI green, every **Done when** line ticked with its evidence

The row is **Done** only when it's merged and its evidence (the commit hash, the
test name) is in the tracker's Notes.

## Non-negotiables

Each of these has a reason. If a task seems to need breaking one, stop and ask.

| Rule | Why |
|---|---|
| Every route has an auth dependency or is deliberately public | A route that's public by accident is exactly the failure OWASP API1 and API5 describe |
| A resource owned by a business is fetched *with the owner in the query*; a stranger gets **404** | 403 confirms the thing exists; 404 leaks nothing |
| Every `/admin` route declares exactly one `Can…` permission | The route-matrix test enforces deny-by-default; don't fight it |
| Explicit response models; never return an ORM object | Fields leak when a column is added later |
| Never accept `status`, owner IDs or internal prices from a client | A state change is an action route that checks the transition and writes an audit row |
| One transition function per entity with a status | So every rule about state lives in one reviewable place |
| Services raise `core/errors` exceptions and never import FastAPI | Keeps rules testable and every error the same shape |
| Migrations are numbered, reversible, backfilled, and never edited after merge | Someone's database is already at that revision |
| No secrets, codes, KYB numbers, file contents or full IPs in logs | DPDP and CERT-In; logs are the least-guarded copy of data |
| Sensitive values are encrypted at rest, masked in lists, and revealed only by a separate, rate-limited, audited call | Control C1/B7; the KYB pattern already does this |
| From M2: no identity field reaches an external response | Masking is the product promise; the response-guard test enforces it |
| From M5: money is integer minor units plus currency; payment endpoints are idempotent; payouts and releases need two approvers | A ledger must net to exactly zero, and money must never move on a retry or a single person's say-so |
| Never weaken, skip or delete a test to get CI green | A red test is information; fix the cause or say why it's wrong |

## Writing code that reads like ours

This codebase reads as written by people who care, and new code must not stand
out. `references/code-style.md` has the full guide with before-and-after
examples. The rules that matter most:

- **Comments say why, not what.** Write `# A concurrent sign-in won the
  one-active-session index; retry once.`, never `# retry the query`. Most lines
  need no comment at all.
- **Docstrings are one line that states the contract and the non-obvious part**:
  `"""The business's listings (not deleted), newest first."""`. No `Args:` or
  `Returns:` blocks that repeat the signature.
- **Error messages talk to the user and say what to do**: `"Enter the number or
  upload the document."`, `"A rejection reason is required so the business knows
  what to fix."` They are full sentences ending in a period.
- **Logs are `event_name key=value`** with lazy `%s` formatting:
  `log.info("rate_limited rule=%s retry_after=%s", ...)`.
- **Names come from the domain**: `reveal_contact`, `visible_products_clause`,
  `list_own_products`. Not `handle_data`, `process_item`, `helper`, `manager`,
  or a `utils.py` dumping ground.
- **No AI tells**: no narrating comments (`# Added new field`), no emoji in code
  or logs, no `try/except Exception: pass`, no placeholder stubs left behind, no
  abstraction with one implementation, and no "robust / seamless / leverage /
  comprehensive" in docs or commits.
- **Commits**: `Area: what changed, the specifics` as the subject, and a body
  grouped by Backend / Frontend / Docs that ends with the test count. Never
  "update" or "fix stuff".

## Honesty

- Report what you verified and how, and what you didn't verify. If tests failed,
  say so and show the failure.
- A tracker row moves to Done only with evidence in Notes.
- When the plan, the client brief and the code disagree, write it up as a
  *Discuss later* row. Don't resolve it silently in code.
- Don't widen scope. Things you notice outside the task become tracker rows,
  not diff lines.
- Never invent data, test results, figures or regulatory facts. If a number
  comes from a regulation or the bank (the LC outlay cap, retention periods),
  say it needs confirming.

## Reference map

Read only what the task needs.

| Read | When |
|---|---|
| `references/architecture.md` | Before touching any module: layers, file roles, real code patterns, integrations |
| `references/api-standard.md` | Designing or changing any endpoint: REST rules, errors, pagination, status codes |
| `references/security.md` | Every PR (the checklist), and designing anything with auth, identity, files or money |
| `references/milestones.md` | Planning or starting a milestone or sprint: goals, exit gates, rows, what lands where |
| `references/code-style.md` | Writing any code, comment, docstring, log line, error message, commit or PR |
| `references/testing.md` | Writing tests: fixtures, what every feature must prove, commands |
| `references/decisions.md` | Before building anything a standard touches: what's approved, proposed or pending |
| `assets/design-review-template.md` | Starting a milestone's design review |

## Helper

`scripts/route_inventory.py` lists every API route with its effective path, the
auth it requires, and its route-level rate limit (limits enforced inside a
service, like the contact-reveal window, aren't visible to it). It exits
non-zero if an `/admin` route lacks a permission. Use it in design reviews (what exists
already), in security passes (what's public), and as the API inventory for each
release (OWASP API9).

```bash
python .claude/skills/cor1x-backend/scripts/route_inventory.py            # all routes
python .claude/skills/cor1x-backend/scripts/route_inventory.py --public   # only the unauthenticated ones
```
