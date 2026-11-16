# Internal Tools Kit: Prototype Spec

Source of truth for the prototype. If code and this file disagree, this file wins until a human changes it. Not production. Synthetic data only.

## 1. What this is

A small kit for building governed internal tools, plus two tools built on it. The claim under test: with shared controls in a core, an agent can add the next internal tool quickly, and CI proves the controls still hold.

- **Tool 1, KYC review:** built alongside the core. Exercises every primitive.
- **Tool 2, feature flags:** built later from `playbooks/new-tool.md` in one timed session, without changing the core.

## 2. Outcome

A new governed internal tool goes from a one-paragraph request to a merged pull request, and it inherits access control, approvals and audit without re-implementing them. Concretely: an analyst proposes a decision on a flagged KYC case, a different senior reviewer approves it, and an auditor sees the trail.

## 3. Not in scope

No drag-and-drop editor, no real SSO, no regions, no hosting, no connectors, no notifications. `core/auth` is a stub login behind an interface where OIDC would go.

## 4. Stack and layout

FastAPI, SQLAlchemy 2, Postgres, pytest. Vite, React, TypeScript, one component library. `docker compose up` runs everything. Schema is plain SQL applied by the seed script (no migration tool).

```
backend/
  main.py          composition root: discovers tools, mounts routers
  core/            auth, policy, approvals, audit, masking, db
  core/tests/      unit tests of core (import no tool)
  tools/<name>/    routes, service, permissions, schemas, schema.sql, tests/
  tests/           generic guardrail tests
web/src/
  shell/           nav, user switcher, approvals inbox, audit view
  tools/<name>/    pages for one tool
db/                core schema.sql, seed.py
playbooks/new-tool.md
```

Boundary rules: tools import core. Core never imports tools. Tools never import each other. Tools are discovered (backend by package scan, web by glob), so adding one changes no file outside its own folders.

## 5. Core primitives

| Primitive | Behavior |
|---|---|
| **auth** | `POST /api/auth/login {user_id}` sets a signed HttpOnly cookie. `GET /api/me` returns id, name, roles and allowed actions. `GET /api/users` lists seeded users for the login picker. |
| **policy** | Every route declares one action, for example `kyc.case.read`. Each tool declares which roles hold which actions in its `permissions.py`. Each tool declares one namespace and grants only actions under it, once; approval kinds follow the same rule. Core owns `audit` and `approvals`. Policy is frozen after startup. Deny by default. Authorization runs before validation. |
| **approvals** | One table, `approval_requests`, for all tools: tool, action, entity, payload, proposed_by, status, decided_by, comment. A tool registers a handler that applies the change when a request is approved, in the same transaction. The decider must hold the request's approve action and must not be the proposer. The table has `CHECK (decided_by <> proposed_by)`. The payload never contains PII. |
| **audit** | `audit.record(...)` writes to `audit_events` (actor, role, tool, action, entity, detail) inside the caller's transaction. A trigger rejects UPDATE and DELETE. Detail never contains PII. |
| **masking** | PII is marked on a `PiiModel` and masked on every serialization unless the caller holds its PII action. A route with an action returns a model. |

Generic routes owned by core: `GET /api/approvals`, `POST /api/approvals/{id}/approve`, `POST /api/approvals/{id}/reject`, `GET /api/audit`.

Errors: JSON body `{"error": {"code", "message"}}`. 401 unauthenticated, 403 `forbidden` or `self_approval`, 404, 409 `invalid_state`, 422.

## 6. Tool 1: KYC review

Table `kyc_cases`: id, subject_name, national_id (PII), date_of_birth (PII), risk_flag, status (`open`, `pending_approval`, `cleared`, `rejected`).

| Route | Action |
|---|---|
| `GET /api/kyc/cases` and `/{id}` | `kyc.case.read` |
| `POST /api/kyc/cases/{id}/propose` with `{decision: clear or reject, rationale}` | `kyc.decision.propose` |

Proposing moves the case to `pending_approval` and creates an approval request. Approval applies the decision. Rejection returns the case to `open`. Every step is audited.

| Action | analyst | senior_reviewer | auditor |
|---|---|---|---|
| `kyc.case.read` | yes | yes | yes |
| `kyc.pii.read` | yes | yes | no (masked) |
| `kyc.decision.propose` | yes | no | no |
| `kyc.decision.approve` | no | yes | no |

`audit.read` is a core action held by `auditor`.

## 7. Tool 2: feature flags (the request given to the playbook session)

"Engineers need an admin panel for feature flags across dev, staging and prod. Anyone on the engineering team can see flags and toggle them in dev and staging. A toggle in prod needs approval from an engineering lead who is not the person asking. Every toggle is audited. Auditors can view flags."

Roles: `engineer`, `eng_lead`, `auditor`.

## 8. Seed data

Users: Ana (analyst), Sam (senior_reviewer), Dana (analyst and senior_reviewer, used to show self-approval being refused), Audrey (auditor), Eli (engineer), Lee (engineer and eng_lead). About 20 KYC cases and 6 flags per environment. Obviously fake values, fixed random seed.

## 9. Guardrail tests (the definition of done)

These live in `backend/tests/` and are generic, so every tool inherits them.

| ID | Test |
|---|---|
| G1 | Every route except health, `/api/auth/*`, `/api/me` and `/api/users` declares a policy action. |
| G2 | For every route and every role, the response is 403 exactly when the role lacks the declared action. |
| G3 | A proposer cannot decide their own request, through the API or by direct insert into the table. |
| G4 | UPDATE and DELETE on `audit_events` fail. A change that fails midway leaves no state change and no audit row. |
| G5 | Core imports no tool. No tool imports another tool. |
| G6 | A caller without the PII action never receives raw PII values. |
| G7 | No tool grants or registers an action outside its own namespace. A foreign action, a duplicate namespace or a core namespace fails. |

Done means: G1 to G7 pass in CI, `docker compose up` plus the seed script gives a working app from a clean clone, and the README explains how to run it.
