# Internal Tools Kit

A prototype kit for building governed internal tools. Access control, approvals, audit and PII
masking live once in `backend/core/`; each tool under `backend/tools/<name>/` inherits them.
The first tool is **KYC review**: an analyst proposes a decision on a flagged case, a different
senior reviewer approves it, and an auditor sees the trail. See [SPEC.md](SPEC.md) for the full
spec and [AGENTS.md](AGENTS.md) for contributor rules.

Not production. Synthetic data only. Login is a stub (pick a user, no password).

## Run it

Requires Docker with Compose.

```sh
docker compose up -d     # postgres :5432, backend :8000, web placeholder :5173
make seed                # drop + recreate the schema, load synthetic users and cases
```

- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/health
- The `web` service is a placeholder until `web/package.json` exists, then it runs the Vite dev
  server on http://localhost:5173.

`make seed` is safe to rerun; it resets the database to the same fixed data every time.

## Log in as a seeded user

Login sets a signed HttpOnly cookie. `GET /api/users` lists who you can be.

| User id | Name | Roles | Can |
|---|---|---|---|
| `ana` | Ana | analyst | read cases with PII, propose decisions |
| `sam` | Sam | senior_reviewer | read cases with PII, approve or reject proposals |
| `dana` | Dana | analyst, senior_reviewer | propose and approve, but never her own proposal |
| `audrey` | Audrey | auditor | read cases with PII masked, read the audit trail |
| `eli` | Eli | engineer | nothing yet (feature flags tool comes later) |
| `lee` | Lee | engineer, eng_lead | nothing yet (feature flags tool comes later) |

The KYC flow from SPEC section 2 with curl:

```sh
API=http://localhost:8000/api
login() { curl -s -c "/tmp/$1.jar" -X POST $API/auth/login -H 'content-type: application/json' -d "{\"user_id\":\"$1\"}"; }
login dana; login sam; login audrey

# Dana proposes clearing case 2
curl -s -b /tmp/dana.jar -X POST $API/kyc/cases/2/propose \
  -H 'content-type: application/json' -d '{"decision":"clear","rationale":"Documents verified"}'

# Dana cannot approve her own proposal: 403 self_approval
curl -s -b /tmp/dana.jar -X POST $API/approvals/1/approve

# Sam can
curl -s -b /tmp/sam.jar -X POST $API/approvals/1/approve

# Audrey sees the trail
curl -s -b /tmp/audrey.jar "$API/audit?entity=kyc_case:2"
```

## API

| Route | Action |
|---|---|
| `POST /api/auth/login {user_id}`, `POST /api/auth/logout`, `GET /api/me`, `GET /api/users` | auth (no action) |
| `GET /api/approvals?status=` | `approvals.read` |
| `POST /api/approvals/{id}/approve`, `.../reject` with optional `{comment}` | `approvals.decide`, plus the request's own approve action |
| `GET /api/audit?tool=&entity=&actor=&limit=` | `audit.read` |
| `GET /api/kyc/cases?status=`, `GET /api/kyc/cases/{id}` | `kyc.case.read` |
| `POST /api/kyc/cases/{id}/propose {decision: clear or reject, rationale}` | `kyc.decision.propose` |

`approvals.read` and `approvals.decide` are derived: a role holds them if it holds the propose or
approve action of any registered approval kind. `GET /api/me` returns the caller's actions.

Errors are `{"error": {"code", "message"}}`: 401 `unauthenticated`, 403 `forbidden` or
`self_approval`, 404 `not_found`, 409 `invalid_state`, 422 `validation_error`.

## Develop

```sh
python3 -m venv .venv && . .venv/bin/activate
make install             # backend runtime + dev dependencies
docker compose up -d postgres
make test                # pytest against a separate itk_test database (TEST_DATABASE_URL)
make lint                # ruff check, ruff format --check, mypy
```

Layout (SPEC section 4):

```
backend/main.py          discovers backend/tools/* and mounts each tool's router under /api
backend/core/            auth, policy, approvals, audit, masking, db (+ errors, api routes)
backend/tools/<name>/    permissions.py, routes.py, service.py, schemas.py, schema.sql, seed.py, tests/
backend/tests/           generic guardrail tests (G1 to G6)
db/schema.sql            core tables: users, approval_requests, audit_events
db/seed.py               applies core + tool schema.sql, seeds users, calls each tool's seed.py
```

To add a tool, follow [playbooks/new-tool.md](playbooks/new-tool.md). No file outside the tool's
folder needs to change: `main.py` and `db/seed.py` find it by scanning `backend/tools/`.
