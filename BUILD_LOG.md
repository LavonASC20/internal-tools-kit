# Build log

One entry per Devin session. Failures stay in.

| Session | Start | End | Minutes | Consumption | Human corrections | Defects found in review | Guardrails green on first PR |
|---|---|---|---|---|---|---|---|
| 1 Core and KYC backend | 2026-11-16 05:37 UTC | 2026-11-16 05:41 UTC | ~4 | not measured in-session | 0 | pending review | n/a (G1 to G6 are session 3) |
| 2 Web shell and KYC pages | | | | | | | |
| 3 Guardrail tests and CI | | | | | | | |
| 4 Feature flags (playbook) | | | | | | | |

## Notes per session

### Session 1

Times are from the VM clock (`date -u`) at session start and at commit.

**Asked:** core (auth, policy, approvals, audit, masking, db), the KYC review tool, a `main.py`
that discovers tools, `db/schema.sql` + `db/seed.py`, docker compose with a web placeholder,
Makefile targets, README. No guardrail tests; no files under `web/src`.

**Delivered:** all of the above, with 12 KYC-specific tests in
`backend/tools/kyc_review/tests/`. `make lint` and `make test` green locally. Verified the SPEC
section 2 flow end to end with curl against `docker compose up` + `make seed` (Dana refused with
`self_approval`, Sam approves, Audrey sees propose, approve and apply in the audit trail with PII
masked on the case). Also spot-checked, without committing tests: every non-auth route declares
an action; authorization runs before body parsing (403 even on malformed JSON); a direct insert
with `decided_by = proposed_by` fails on the CHECK; UPDATE, DELETE and TRUNCATE on
`audit_events` fail; a failing approval handler leaves the request pending with no audit rows.

**Choices a reviewer should check:**
- `approvals.read` / `approvals.decide` are derived from registered approval kinds, so core
  never names a role. `audit.read` is granted to `auditor` in the KYC tool's `permissions.py`
  (the spec puts it in the KYC table); the feature flags tool will need to grant it too.
- Added `core/errors.py` and `core/api.py` (core HTTP routes) beyond the six modules SPEC lists.
- Tools may ship an optional `seed.py` hook so seed data also stays inside the tool's folder.
- Shared fixtures are in `backend/conftest.py` (outside `backend/tests/`) so tool tests and
  guardrail tests share one test database setup.

**Got wrong along the way:** first test run hit infinite recursion: the derived approval grants
read `policy.roles_for`, which itself evaluates derived grants. Fixed by having derived providers
read only declared grants (`policy.declared_roles_for`). One mypy error on the DBAPI cursor
context manager.

**Corrected by the human after the PR was opened** (01:07 to 01:10 EST, 2026-11-16, VM clock).
Three questions, three misses:
- *Any tool could grant any action.* `policy.register_permissions` merged every tool's grants into
  one table with no ownership check, so a new tool's `permissions.py` could give `engineer`
  `kyc.pii.read` and unmask KYC PII. I had shown it working in-process. Nothing (G2, G5, my tests)
  would have caught it. Fix: each tool declares a `NAMESPACE` and may only grant actions under
  it; `audit` and `approvals` are core-owned; `audit.read` → `auditor` moved from the KYC tool into
  `core/audit.py`.
- *Masking depended on the tool remembering to call it.* The KYC service called `masking.mask` by
  hand; a tool that forgot would leak PII and nothing before merge would notice. Worse, a
  `pii_field()` on a plain `BaseModel` was silently ignored, which also blinded the audit PII
  check. Fix: `PiiModel` masks itself on serialization unless `core.policy` has revealed the
  caller's PII action for the request (fail closed); routes whose response model marks PII outside
  a `PiiModel` are refused at startup. The KYC service no longer calls masking.
- *I wired the web container without reading the web PR.* Compose set `BACKEND_URL`, which
  nothing reads; the web PR's Vite proxy reads `API_TARGET`, so under compose every `/api` call
  would have gone to the web container's own localhost. Fix: compose sets `API_TARGET`. Verified by
  running compose with the web PR's `web/` and calling `/api` through `:5173`.

Also during review, Devin Review found that a session cookie with a non-ASCII signature made
`hmac.compare_digest` raise (500 instead of 401). Fixed by comparing bytes.

### Session 2

### Session 3

### Session 4

Did the diff stay inside the tool's folders? Did the core need to change?
