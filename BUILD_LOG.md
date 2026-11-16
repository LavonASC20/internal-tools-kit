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
context manager. No human corrections.

### Session 2

### Session 3

### Session 4

Did the diff stay inside the tool's folders? Did the core need to change?
