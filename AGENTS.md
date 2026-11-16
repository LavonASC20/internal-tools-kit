# AGENTS.md

Rules for any AI agent (including Devin) working in this repo. Read `SPEC.md` first.

## Commands

- Run everything: `docker compose up`
- Seed: `make seed`
- Backend tests: `make test`
- Lint and type checks: `make lint`

CI must be green before you ask for review.

## Hard rules

1. **Policy.** Every route declares its action through the core policy dependency. Never check a role inside a handler or a service.
2. **Audit.** Every state change calls `core.audit.record` in the same transaction. Never update or delete audit rows, and never weaken the trigger.
3. **Approvals.** Changes that need a second person go through `core.approvals`. Never build a tool-specific approval table.
4. **Boundaries.** Tools import core. Core never imports tools. Tools never import each other. A tool's code, schema and tests live in its own folders.
5. **PII.** Mark PII fields and let `core.masking` handle them. Never log PII or put it in audit detail or error messages.
6. **Spec.** Do not change `SPEC.md` or a guardrail test to make code pass. If the spec is wrong or the core is missing something, stop and say so in the PR under "Deviations".
7. **Dependencies.** Add none without a one-line justification in the PR.
8. **Data and secrets.** Synthetic data only. No secrets in the repo.

## Pull requests

- One concern per PR, with tests.
- The description lists what changed, which guardrails it touches, deviations, and new dependencies.
- Changes under `backend/core/` or `backend/tests/` need a "Core changes" section explaining why. A human reviews these.
- Do not merge your own PR.

## Build log

After each session, append to `BUILD_LOG.md`: start and end time, what was asked, what was delivered, and what you got wrong or were corrected on. Do not tidy failures away.

## Adding a tool

Follow `playbooks/new-tool.md`.
