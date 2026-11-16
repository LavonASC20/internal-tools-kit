# Playbook: add a new internal tool

Input: a one-paragraph request describing who uses the tool, what they can do, and which changes need a second person.

Rule for the whole procedure: you may only add files under `backend/tools/<name>/` and `web/src/tools/<name>/`, plus seed rows. If you believe a change to `backend/core/`, `backend/tests/` or `web/src/shell/` is needed, stop and report it. Do not make it.

## Steps

1. **Restate the request** as a table of roles and actions, and a list of entities with their fields. Mark PII fields. Mark which actions need approval. Put this at the top of the PR description.
2. **Schema.** Write `schema.sql` for the tool's tables only.
3. **Permissions.** In `permissions.py`, set `NAMESPACE` and declare in `PERMISSIONS` which roles hold each action. Name actions `<namespace>.<entity>.<verb>`. Grant only actions in your own namespace; `audit` and `approvals` belong to core. Grants are registered once at startup and policy is frozen after.
4. **Service.** One function per use case. Each state change runs in one transaction and calls `core.audit.record`. For changes that need approval, register an `ApprovalKind` whose `action` and `propose_action` are declared in your namespace, with a handler that applies the change when it is approved, and create requests through `core.approvals`. The approval payload must not contain PII fields. Do not call masking.
5. **Routes.** Thin handlers. Each declares exactly one action and calls one service function.
6. **Schemas.** Response models. A model with PII subclasses `core.masking.PiiModel`, sets `pii_action`, and marks each PII field with `pii_field()`; core masks it on serialization. Do not define a `model_serializer` on it. Every route that declares an action returns a model (or a list of models).
7. **Pages.** A list page and whatever detail or form the request needs, using the shell's components. Show only the actions `GET /api/me` says the user holds. Approvals and audit already have pages in the shell, so do not rebuild them.
8. **Seed.** A handful of obviously fake rows.
9. **Tests.** Tool-specific behavior only, in the tool's `tests/` folder. The generic guardrail tests already cover policy, approvals, audit and boundaries. Do not copy them.
10. **Verify.** `make lint` and `make test` pass. Run `git diff --name-only main` and confirm every path is inside the allowed folders.
11. **PR and build log.** Open the PR. Append your session to `BUILD_LOG.md` with start and end times.

## Done when

- All guardrail tests pass without modification.
- The diff touches only the tool's own folders and seed data.
- A user with each role can do what the request says and nothing else.
