# Build log

One entry per Devin session. Failures stay in.

| Session | Start | End | Minutes | Consumption | Human corrections | Defects found in review | Guardrails green on first PR |
|---|---|---|---|---|---|---|---|
| 1 Core and KYC backend | 2026-11-16 00:37 EST | 2026-11-16 01:36 EST | ~59 | $0.16, size XS, 12 user messages | 9 (3 in round 1, 6 in round 2) | 1 (Devin Review) | n/a (G1 to G6 are session 3) |
| 2 Web shell and KYC pages | 2026-11-16 00:37 EST | 2026-11-16 00:50 EST (first PR); follow-up fixes and the post-merge check ran to about 01:54 EST | ~13 to the first PR | $1.35, size XS, 9 user messages | 1 | 3 (Devin Review) | n/a (G1-G6 not written yet; web typecheck, build and vitest green) |
| 3 Guardrail tests and CI | 2026-11-16 01:56 EST | 2026-11-16 02:09 EST | ~13 | $3.93, size XS, 2 user messages | 0 | | yes (G1 to G7 green against main on first run; no findings) |
| 4 Feature flags (playbook) | 2026-11-16 02:15 EST | 2026-11-16 02:20 EST | ~5 (timed build, to the stop); kit fix ~2 on its own line below | $4.30, size S, 3 user messages | 1 | 2 (Devin Review on #6: 1 fixed, 1 escalated as a kit finding) | yes for backend (G1 to G7 green on first run with the tool); web vitest red until kit PR #5 |

Consumption was added by hand after the sessions ended. It is the on-demand usage, session size
and user message count shown in each session's panel in the Devin app, read between 02:40 and
02:50 EST on 2026-11-16. The four sessions total $9.74. Devin's size guide puts XS at $4 or less
and S above $4.

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

**Second review round, corrected by the human** (questions 01:18, fixes 01:26 to 01:27 EST,
2026-11-16). The VM clock and GitHub's `Date` header agree, but the fix times look too short to be
real. Per fix, from commit timestamps: F1 under 1 min, F2 under 1 min, F3 under 1 min, F4a under
1 min, F4b under 1 min. What I got wrong in the first round of fixes:
- *F1, the owner check could be spoofed.* `register_permissions` trusted an `owner` string from
  the caller, so `("tools.kyc_review", "kyc", {"kyc.pii.read": {"engineer"}})` passed. My test only
  tried the wrong owner and the wrong namespace. Fix: each namespace's grants are registered once
  (identical repeats are a no-op, anything else fails), and `create_app` freezes policy.
- *F2, approval kinds were outside the namespace rule.* `approvals.register` checked neither
  `action` nor `propose_action`, and `ApprovalKind.tool` is self-reported: a kind with a foreign
  `propose_action` was accepted, and a spoofed `tool` silently replaced another tool's kind. Fix:
  both actions must be declared in one namespace owned by `tools.<kind.tool>`; one kind per action;
  none after freeze.
- *F3, approval payloads could store raw PII.* Masking runs on every serialization, so
  `case.model_dump()` in a payload stored raw PII when the proposer held the PII action (and `***`
  otherwise), and `GET /api/approvals` returns the payload unmasked. Audit detail had a PII key
  check; approval payloads did not. Fix: `approvals.create` refuses PII keys (shared
  `masking.pii_keys`).
- *F4a/F4b, masking could still be switched off.* A `PiiModel` subclass with its own
  `model_serializer` served raw PII, and so did a route returning a hand-built `dict`, `dict(model)`
  or a `Response`; `check_response_type` caught only `pii_field()` on a plain `BaseModel`, and it
  had no test. Fix: a `PiiModel` subclass may not define a `model_serializer`, and a route with an
  action must return a pydantic model (or list/optional of one). Still open: a handler annotated
  with a model that returns a `Response` object, PII inside free-form `dict`/`Any` model fields,
  `computed_field`, a forgotten `pii_field()`, or a wrong `pii_action`.
- *`auditor` in core was not put to the human as a trade.* Moving `audit.read` into core made core
  name a role, against SPEC section 5; I mentioned it but offered no alternatives. Kept, by the
  human's decision, and listed under Deviations.
- *Core tests were in the KYC tool's test folder.* Core-mechanism tests now live in
  `backend/core/tests/` and import no tool; the KYC folder keeps only KYC assertions.

### Session 2

- Asked: web shell (user picker login, nav from discovered tools, approvals inbox, audit view) and `tools/kyc_review` pages (case queue, case detail with propose form), coded against SPEC sections 5 and 6 with a switchable mock, touching only `web/`.
- Delivered: Vite + React + TS + Mantine app in `web/`. Tools are discovered with `import.meta.glob('../tools/*/index.tsx')`. Controls render only when `GET /api/me` lists the action. Mock layer (`npm run dev:mock`, `VITE_USE_MOCK=true`) patches `fetch` for `/api/*`, with per-tool handlers discovered by glob from `tools/<name>/mock.ts`; it is excluded from normal builds. Tests cover discovery, control gating, masking display and the mock KYC flow including `self_approval`. Also added `web/Dockerfile` for compose to use; compose wiring is session 1's.
- Assumptions the backend must match or the web must adjust (spec does not pin these): `/api/me` returns `actions` (`allowed_actions` also accepted); approval request `action` is the action the decider needs (`kyc.decision.approve`); approve/reject body is `{comment}`; list routes return an array or `{items}`; the action guarding `GET /api/approvals` is unspecified, so its nav entry is always shown and a 403 is displayed.
- Got wrong: first typecheck failed (`React.FormEvent` without import; `process` in `vite.config.ts` without node types). My first browser check failed because a stale tab from an earlier run rewrote the mock's `localStorage` state; the mock shares state across tabs through storage, which is a known limit of the mock, not the app.
- Defects found by Devin Review on the first PR revision, all fixed: (1) switching user kept the previous user's fetched data on screen, including unmasked PII, because pages were not remounted on identity change; (2) the nav covered the page on small screens with no way to close it; (3) KYC-specific mock tests sat in the shared `web/src/mock/` suite instead of `tools/kyc_review/`.
- Defect found by recorded browser testing (mock API, all six roles): at 500px width the fixed 56px header wrapped the Switch user control onto a second row, overlapping page content. Fixed by keeping the header on one row, hiding the roles text below the `sm` breakpoint and narrowing the switcher. Role matrix, approvals, rejections, masking and user-switch checks passed.
- Contract drift. These are the places where my assumptions differed from session 1's backend (PR #1). I found them all by reading PR #1's code, then confirmed them with curl as each seeded user against `docker compose up` + seed. The 15 mock-based tests and the recorded mock browser test missed every one of them. All are fixed except Decide gating; see the human correction below.
  - Audit timestamp: I assumed `created_at`, but the backend sends `at` (`core/audit.py` `AuditEvent`). The Time column was blank. Confirmed with `GET /api/audit`.
  - Approvals list guard: I assumed no action, but the backend requires a derived `approvals.read` (`core/api.py`, `core/approvals.py` `_derived_grants`), which `/me` lists. The Approvals link was shown to Audrey, Eli and Lee, who got a 403. Confirmed: `GET /api/approvals` returns 403 for those three.
  - Decide gating: I used only the request's `action` from `/me`. The backend also returns `can_decide` (`core/api.py` `ApprovalOut`), which is false on your own request, so Dana saw a Decide button the API then refused. Confirmed: curl shows `can_decide: false` for Dana's own request. I gated Decide on `can_decide`; that was reverted (see the human correction below).
  - Proxy target: Vite read `API_TARGET`, but compose passes `BACKEND_URL` (`docker-compose.yml`), so every API call from the compose `web` container would fail. Found by reading the compose file and confirmed by running the Vite proxy with only `BACKEND_URL` set. Session 1 fixed this on its side before PR #1 merged (compose now sets `API_TARGET`), so after rebasing I removed the `BACKEND_URL` fallback I had added.
  - Mock vs backend: I found these by comparing `web/src/mock` with `core/approvals.py`, `core/api.py` and `tools/kyc_review/service.py`.
    - audit action `approval.approve` vs the backend's `approvals.approve`
    - detail key `approval_id` vs `approval_request_id`
    - the mock didn't write the `kyc.decision.apply` and `kyc.decision.return` rows
    - propose returned the approval request instead of `{case, approval_request_id}`
    - login returned `{ok}` instead of the `/me` shape, and an unknown user got 422 instead of 401
    - the mock let anyone list approvals
  - Assumptions that matched: `/me` returns `actions`; an approval's `action` is the decider's action; approve/reject take `{comment}`; lists are bare arrays; errors use `{error: {code, message}}`.
- Human correction: I had hidden Decide when the backend's `can_decide` was false. That was wrong for this prototype. SPEC section 8 includes Dana to show a self-approval being refused, so the server's `self_approval` error has to be visible in the UI. Decide is again shown when the request is pending and `/api/me` lists its action. `can_decide` stays in the types but no longer gates Decide. The test now checks that Dana sees Decide on her own request and that the `self_approval` refusal is displayed.
- After both PRs merged: ran the SPEC section 2 flow in the browser on merged main against `docker compose up` + `make seed`. Dana proposes on flagged case 3; her self-approval shows the server's `self_approval` refusal; Ana sees no Decide; Sam approves; the case is cleared; Audrey sees masked PII and three audit rows (propose, approve, apply) with no raw PII. Noted, not changed: a refused self-approval writes no audit row, because only state changes are audited. The compose web container writes a root-owned `web/.vite/` cache that git did not ignore, so I added it to `web/.gitignore`.

### Session 3

Times are from the VM clock (`date -u`): start 06:56:14 UTC, end 07:09:51 UTC.

**Asked:** G1 to G7 from SPEC section 9 in `backend/tests/`, written from the spec and discovering
routes, roles, actions, tools and PII fields at runtime; a GitHub Actions workflow (Postgres
service, `make lint`, `make test`, web typecheck, build and tests); proof that each guardrail can
fail, with the failing output in the PR and the breakage not committed; findings fixed in
separate commits.

**Delivered:**
- `backend/tests/discover.py` reads everything from the running app: routes from `main.app`, the
  action from each route's `ActionCheck` dependency, tools from `tools/`, roles from the grant
  table, approval kinds from `core.approvals`, PII fields and their `pii_action` from the
  response models of mounted routes, and request bodies from each route's JSON schema. Nothing
  names KYC; a new tool is picked up without editing the tests.
- `backend/tests/conftest.py` adds a `policy_sandbox` (copy, unfreeze, restore, same pattern as
  `backend/core/tests/conftest.py`), a `throwaway_tool` that writes a real tool package into a temp
  dir on `tools.__path__`, and users with any role combination. Shared database fixtures stay in
  `backend/conftest.py`; nothing in `backend/core/tests/` was moved or duplicated.
- G1 to G7, 123 test cases. Readings stricter than the spec text, listed in the PR under
  Deviations: the G1 exemption covers only core routes at those paths (a tool route under
  `/api/auth/` is not exempt) and raw Starlette routes fail; G2 sends a malformed body so a route
  that validates before authorizing fails, and checks anonymous callers get 401; G4 also tries
  TRUNCATE.
- `.github/workflows/ci.yml`: backend job with `postgres:16-alpine`, `make install`, `make lint`,
  `make test`; web job with `npm ci`, typecheck, build, test.
- 17 temporary breakages (throwaway tools and temporary core/schema edits), at least two per
  guardrail. Each one fails its guardrail; output is in the PR. A script applied each one, ran the
  test file and reverted it, so none was committed.

**Findings against main:** none. All seven guardrails passed on main the first time they ran.

**Not covered (limits of runtime discovery):** G6 learns what counts as PII from `pii_field()`
markings. It catches a route that leaks a known PII value through an unmarked field, but not a
new tool that forgets to mark its own PII, or marks it with the wrong `pii_action`. Session 1's
open list still applies.

**Got wrong along the way:**
- First `make test PYTHON=.venv/bin/python` failed with `.venv/bin/python: not found`, because the
  Makefile `cd`s into `backend/`. The interpreter path has to be absolute.
- The G5 runtime probe imported `tools.kyc_review.routes` on its own, which skips
  `main.load_tool`'s order (permissions first). The KYC service then failed to register its
  approval kind. That was a false failure in my test, not a boundary violation. The probe now
  registers the tool's permissions first, the way `main` does.
- First `make lint` on the new files: 6 lines over 100 characters, 6 files not formatted, and 1
  mypy error (`str | None` passed as `str` in G7).
- My breakage script reverted with `git checkout -- backend db`. That wiped an uncommitted edit to
  the G3 test. I noticed because the G3 proof still showed the old behaviour. After that I
  committed before every proof run.
- The G3 API test opened requests with an empty payload. With the self-approval rule removed, the
  test still failed, but it failed with a 500 from the KYC handler (`KeyError: 'case_id'`), not
  because a self-approval went through. Fixed by swapping the kind's handlers for no-ops inside
  `policy_sandbox`. Now the proof shows the request `approved` with `decided_by` equal to
  `proposed_by`.

### Session 4

Times are from the VM clock (`date -u`).
- Timed build: start 07:15:13 UTC; end 07:20:17 UTC, when I stopped on the web test finding below
  (~5 min).
- Kit fix (PR #5, not part of the timed build): 07:24:00 UTC to about 07:25:30 UTC, when PR #5 was
  opened (~2 min).

**Asked:** follow `playbooks/new-tool.md` to build the feature flags tool from SPEC section 7. Roles
are `engineer`, `eng_lead` and `auditor`; seed users Eli and Lee already exist. The whole diff stays
inside `backend/tools/feature_flags`, `web/src/tools/feature_flags`, seed data and this entry. Stop
and report if the core, the guardrail tests or the shell would need to change. Run G1 to G7 before
opening the PR.

**Delivered:**
- `backend/tools/feature_flags/`, namespace `flags`:
  - `flags.flag.read` (engineer, eng_lead, auditor), `flags.flag.toggle` (engineer, eng_lead),
    `flags.prod.propose` (engineer, eng_lead), `flags.prod.approve` (eng_lead).
  - Dev and staging toggles are direct, audited as `flags.flag.toggle`.
  - A prod toggle always goes through `core.approvals`. Even Lee cannot toggle prod directly. The
    flag stays unchanged with a `pending_request_id` until another eng_lead approves
    (`flags.prod.apply`) or rejects (`flags.prod.return`).
  - Self-approval is refused by the core.
  - Seed data is six synthetic `demo_` flags per environment in the tool's own `seed.py` hook.
    `db/seed.py` is unchanged. No PII.
  - 11 tool tests.
- `web/src/tools/feature_flags/`:
  - List page with an environment filter; detail page with a direct toggle, or a prod proposal
    form gated by `Can`.
  - Mock handlers and 9 web tests.
- Checks: `make lint` green; `make test` 254 passed (main: 158). That includes G1 to G7: 208 cases,
  unmodified, which picked up the new routes and roles at runtime. Web typecheck, build and vitest
  (26 tests) green on top of PR #5.

**Finding against the kit (PR #5, separate from this tool):** adding the tool broke two web tests
outside its folders. Both hardcoded which tools and grants existed when they were written:
- `web/src/mock/mock.test.ts` expected Eli to get 403 on `/api/approvals`. Proposing a prod toggle
  now gives him the derived `approvals.read`.
- `web/src/tools/kyc_review/mock.test.ts` asserted Audrey's full action list. She now also holds
  `flags.flag.read`.

I stopped and reported instead of working around it. The only in-folder workarounds would have
broken the request: dropping auditor read access, or not letting engineers propose prod toggles.
PR #5 makes both tests independent of which tools are installed:
- Test 1 picks, at runtime, a user who holds no propose or approve action of any installed tool's
  approval kinds.
- Test 2 asserts only on `kyc.*` actions.

A throwaway third tool mock (not committed) breaks the old tests and passes the new ones. This PR
is stacked on PR #5.

**Got wrong along the way:**
- First `make lint` on the tool: 2 lines over 100 characters (`service.py`, `test_flag_flow.py`).
  Fixed with `ruff format`.
- First web vitest run with the tool: 2 failures in the existing tests above. That was the finding,
  not a tool bug.
- My first suggested fix was to swap in another user ("Ana" for test 1). That was wrong twice:
  - Ana proposes KYC decisions, so she holds `approvals.read` too.
  - Swapping users only moves the hardcoding.

  Corrected by the user: make both tests independent of the installed tools.
- My first kit commit made test 1 check every user's 403 or 200 against their own `approvals.read`.
  That is tool-independent but not what was asked. The second commit picks the user with no
  propose or approve action at runtime, as asked.

**Found in review (Devin Review on #6, after the timed build):**
- The web mock accepted a prod request reason longer than 500 characters, which the backend
  rejects with a 422. Fixed: the mock now rejects it too, counting code points as Pydantic does (a second review
  caught my first fix counting UTF-16 units, so 500 emoji were refused; the form's `maxLength`
  had the same problem and was removed).
- Escalated as a kit finding, not patched: if a browser saved the mock's state before a tool was
  added, that tool has no state and its requests get a 500 until the storage is cleared. The
  cause is `load()` in `web/src/mock/index.ts`: it merges the saved state over a fresh one at the
  top level only, so the saved `tools` object replaces the fresh one entirely. That code is
  outside this tool's folders. It only affects `npm run dev:mock`.

**Did the diff stay inside the tool's folders?** This PR: yes. Every changed path is under
`backend/tools/feature_flags/` or `web/src/tools/feature_flags/`, plus this entry. Seed data is in
the tool's own `seed.py`. Adding the tool did need a change outside them, though: the two web tests
in PR #5, which went in as a separate kit fix.

**Did the core need to change?** No. `backend/core/`, `backend/tests/` (G1 to G7), `db/`,
`web/src/shell/` and `SPEC.md` are untouched. Policy, audit, approvals, self-approval and runtime
discovery covered the tool as they were. The only kit change was in the two web tests (PR #5).
