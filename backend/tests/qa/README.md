# QA flow suite

Ported from Pegan's `backend/tests/qa` (branch `work/pegan-2026-10-21`,
commit `02c19c8`) and adapted to main's API. Test IDs (`QA-NNN.x`) follow
his `flows.md`.

| Flow | File | On main |
|---|---|---|
| FLOW-100 country | `test_qa_country.py` | Country is chosen on the business profile (not at sign-up), from countries Corridor ops has set up; ISO validation + lower-case / alpha-3 normalisation kept |
| FLOW-200 admin document list | `test_qa_doc_types.py` | `/admin/kyb/document-types` (country, code, name, input kind, pattern, help text). No `help_url`; Aadhaar and invalid patterns refused instead. Capitals in codes are lower-cased |
| FLOW-300/400/500 trader documents + submit gate | `test_qa_trader_docs.py` | `GET /kyb/document-types`; one entry per type — a second add is 409, the file is replaced via PATCH. `mandatoryTotal` = 4 profile fields + required documents |
| FLOW-600/700 single review + trader rejection view | `test_qa_single_review.py` | Keys `kyb:<code>` / `doc:<entry id>`; `rejectedItemLabels` is a list aligned with `rejectedItems`. Unknown keys → 400 (not silently dropped) |
| FLOW-800 auto re-review | `test_qa_auto_unverify.py` | Triggered by company name, address, city, country, required documents — not contact person or trade position |
| FLOW-900 per-document review | existing `tests/test_docs.py`, `tests/test_review.py` | — |

Run: `python -m pytest tests/qa -q`
