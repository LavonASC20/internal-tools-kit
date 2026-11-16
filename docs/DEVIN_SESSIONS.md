# Devin sessions

The opening prompt of each session, as sent, in order. Sessions 1 and 2 ran in parallel. Session 3 started after sessions 1 and 2 had merged. Session 4 started after the core had been reviewed. The follow-up questions and corrections in each session are recorded in [BUILD_LOG.md](../BUILD_LOG.md).

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

## Session 3: guardrail tests and CI (after sessions 1 and 2 merged)

```
read SPEC.md and AGENTS.md first, and note your start time before you do anything.

this session is the guardrail tests + CI. main now has the core, the kyc tool and the web app merged.

what i want:
- backend/tests/ with G1 to G7 from SPEC section 9. write them from the spec, not from the implementation. they need to discover routes, roles, actions, tools and pii fields at runtime so a tool added later is covered without anyone editing these tests
- a github actions workflow: postgres service, make lint, make test, and the web typecheck, build and tests

some context so you dont waste time:
- shared fixtures are already in backend/conftest.py. core has its own unit tests in backend/core/tests/, dont move or duplicate those
- policy is frozen after startup, so if a test needs a throwaway tool or namespace you have to deal with that. look at how backend/core/tests/conftest.py does it

rules:
- i want proof each guardrail can actually fail. for each of G1 to G7, break the rule with a throwaway tool or a temporary change and paste the failing output in the PR. dont commit the breakage
- if a guardrail fails against the current code do not weaken the test. report it in the PR, then fix the code in a seperate commit and say what was wrong. those are findings and they go in BUILD_LOG.md
- dont change SPEC.md

one PR. append your session to BUILD_LOG.md with start and end times and anyhting you got wrong
```

## Session 4: feature flags from the playbook (timed)

```
follow playbooks/new-tool.md exactly. note your start time before you begin, this one is timed.

the request:
"Engineers need an admin panel for feature flags across dev, staging and prod. Anyone on the engineering team can see flags and toggle them in dev and staging. A toggle in prod needs approval from an engineering lead who is not the person asking. Every toggle is audited. Auditors can view flags."

roles: engineer, eng_lead, auditor. seed users eli and lee already exist.

if you think the core, the guardrail tests or the shell has to change, stop and tell me instead of working around it. thats a finding about the kit, not something to patch.

the guardrail tests (G1 to G7) and CI are on main. run them before you open your PR.

deliverable: one PR where the whole diff is inside backend/tools/feature_flags, web/src/tools/feature_flags and seed data (plus the BUILD_LOG.md entry). record start time, end time and every correction in BUILD_LOG.md, and answer the two questions at the bottom of the build log: did the diff stay inside the tool's folders, and did the core need to change
```
