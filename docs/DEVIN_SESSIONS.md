# Devin sessions

The prompts used to build this repo, in order. Sessions 1 and 2 run in parallel. Session 3 starts when session 1 has merged. Session 4 starts after a human has reviewed the core.

Before session 1: confirm in a throwaway session that `docker compose up` with Postgres runs in Devin's environment.

## Session 1: core and KYC backend

```
Read SPEC.md and AGENTS.md first.

Outcome: a running backend where the KYC flow in SPEC section 2 works through the API.

Build:
- docker-compose.yml (Postgres, backend, web placeholder), Makefile targets from AGENTS.md
- db/schema.sql and db/seed.py per SPEC sections 5 and 8
- backend/core: auth, policy, approvals, audit, masking, db (SPEC section 5)
- backend/tools/kyc_review (SPEC section 6)
- backend/main.py that discovers tools by scanning backend/tools, so adding a tool
  needs no edit outside its folder
- README.md: what this is, how to run it, how to log in as each seeded user

Constraints:
- Follow the layout and boundary rules in SPEC section 4 exactly.
- The self-approval rule must hold at the database, not only in Python.
- Do not write the generic guardrail tests (G1 to G6). Another session writes them
  from the spec. Write only tests for KYC-specific behavior.
- No dependencies beyond the stack in SPEC section 4 without a justification.

Deliverable: one PR, CI-ready, with the PR description AGENTS.md asks for.
Append your session to BUILD_LOG.md.
```

## Session 2: web shell and KYC pages (parallel with session 1)

```
Read SPEC.md and AGENTS.md first.

Outcome: a web app where a user can pick a seeded user, work the KYC flow, decide
approvals, and view the audit trail.

Build in web/:
- shell: user picker login, nav built from discovered tools, approvals inbox,
  audit view. These are generic and work for any tool.
- tools/kyc_review: case queue and case detail with the propose form.
- Tool pages are discovered with a glob import, so adding a tool needs no edit
  to the shell.

Constraints:
- The backend is being built in parallel. Code against the routes and shapes in
  SPEC sections 5 and 6, with a small mock layer you can switch off.
- Show a control only when GET /api/me lists the action. Never decide permissions
  in the frontend.
- Plain and clean. Use the component library defaults. No custom design work.

Deliverable: one PR. Append your session to BUILD_LOG.md.
```

## Session 3: guardrail tests and CI (after session 1 merges)

```
Read SPEC.md and AGENTS.md first.

Outcome: the six guardrail tests in SPEC section 9 exist, are generic, and run in CI.

Build:
- backend/tests/ with G1 to G6. Write them from SPEC.md, not from the
  implementation. They must discover routes, roles, actions and tools at runtime
  so a tool added later is covered without editing these tests.
- GitHub Actions workflow: Postgres service, make lint, make test, web type check
  and build.

Constraints:
- If a guardrail fails against the current code, do not weaken the test. Report
  the failure in the PR, then fix the code in a separate commit and say what was
  wrong. These failures are findings and go in BUILD_LOG.md.
- Do not change SPEC.md.

Deliverable: one PR. Append your session to BUILD_LOG.md.
```

## Session 4: feature flags from the playbook (timed)

```
Follow playbooks/new-tool.md exactly. Note your start time before you begin.

The request:
"Engineers need an admin panel for feature flags across dev, staging and prod.
Anyone on the engineering team can see flags and toggle them in dev and staging.
A toggle in prod needs approval from an engineering lead who is not the person
asking. Every toggle is audited. Auditors can view flags."

Roles: engineer, eng_lead, auditor. Seed users Eli and Lee already exist.

If you think the core, the guardrail tests or the shell must change, stop and
report it instead. That is a finding about the kit, not a problem to work around.

Deliverable: one PR whose diff is inside backend/tools/feature_flags,
web/src/tools/feature_flags and seed data. Record start time, end time and every
correction in BUILD_LOG.md.
```
