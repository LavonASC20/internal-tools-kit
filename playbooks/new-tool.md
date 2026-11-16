# Playbook: add a new internal tool

Input: a one-paragraph request describing who uses the tool, what they can do, and which changes need a second person.

Rule for the whole procedure: you may only add files under `backend/tools/<name>/` and `web/src/tools/<name>/`, plus seed rows. If you believe a change to `backend/core/`, `backend/tests/` or `web/src/shell/` is needed, stop and report it. Do not make it.

## Steps

1. **Restate the request** as a table of roles and actions, and a list of entities with their fields. Mark PII fields. Mark which actions need approval. Put this at the top of the PR description.
2. **Schema.** Write `schema.sql` for the tool's tables only.
3. **Permissions.** Declare the tool's actions and which roles hold them in `permissions.py`. Name actions `<tool>.<entity>.<verb>`.
4. **Service.** One function per use case. Each state change runs in one transaction and calls `core.audit.record`. For changes that need approval, create a request through `core.approvals` and register a handler that applies the change when it is approved.
5. **Routes.** Thin handlers. Each declares exactly one action and calls one service function.
6. **Schemas.** Response models with PII fields marked for `core.masking`.
7. **Pages.** A list page and whatever detail or form the request needs, using the shell's components. Show only the actions `GET /api/me` says the user holds. Approvals and audit already have pages in the shell, so do not rebuild them.
8. **Seed.** A handful of obviously fake rows.
9. **Tests.** Tool-specific behavior only, in the tool's `tests/` folder. The generic guardrail tests already cover policy, approvals, audit and boundaries. Do not copy them.
10. **Verify.** `make lint` and `make test` pass. Run `git diff --name-only main` and confirm every path is inside the allowed folders.
11. **PR and build log.** Open the PR. Append your session to `BUILD_LOG.md` with start and end times.

## Done when

- All guardrail tests pass without modification.
- The diff touches only the tool's own folders and seed data.
- A user with each role can do what the request says and nothing else.
