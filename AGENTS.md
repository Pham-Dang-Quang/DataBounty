# Repository Instructions

This is a hackathon project: a minimal dataset-request marketplace with AI-assisted review and Avalanche rewards.

## Primary rule: keep it minimal

Build the smallest understandable version that demonstrates the complete core flow. Prefer simple code, few dependencies, one process, and explicit logic over production-scale architecture.

- Implement only features listed as MVP in `docs/PRD.md`.
- Do not add abstractions, services, roles, configuration, or infrastructure for hypothetical future needs.
- Do not introduce a feature unless its purpose and flow can be explained simply.
- Keep business rules in small named Python functions and document non-obvious decisions.
- Prefer a working vertical slice over broad but incomplete functionality.
- Advanced security, scaling, fiat, governance, multiple chains, and production operations belong in “Later,” not the hackathon build.
- If a simpler design preserves the core demo, choose it and record any meaningful change in `docs/Decisions.md`.

The owner must be able to read the documentation, follow the main code path, and control the scope.

## Current phase

Implementation is approved. Complete the documented hackathon MVP in phase order, verify each phase, and keep `docs/progress.md` current.

## Minimal technology stack

- **Backend and AI:** Python, FastAPI, Pydantic, SQLAlchemy, and one hosted open-source model through
  an OpenAI-compatible API.
- **Frontend:** FastAPI/Jinja2 templates, plain responsive CSS, and small vanilla JavaScript ES modules.
- **Database:** SQLite for the hackathon demo.
- **Files:** local private upload directory for the demo.
- **Background work:** FastAPI background tasks or a simple Python worker; no Celery or Redis unless proven necessary.
- **Avalanche:** `web3.py` on the backend and `viem` in the browser.
- **Contracts:** one small Solidity escrow contract, tested and deployed with Foundry to Fuji. A mock ERC-20 may be used for demo rewards.
- **Tooling:** `uv`, Ruff, mypy, and pytest.

Do not introduce React, Next.js, Vue, a CSS framework, PostgreSQL, Redis, Kubernetes, microservices, or a custom Avalanche L1 for the MVP.

Use English for code identifiers, API fields, logs, and documentation. Keep visible UI text easy to locate for future translation.

## MVP boundaries

- Support one file per contribution: an image with required companion text, or a UTF-8 CSV file.
- A data call contains a title, description, data type, acceptance criteria, deadline, reward amount, and review mode.
- Support manual review and AI-assisted review. Fully automatic AI payment is a later feature.
- AI returns a recommendation, quality tier, and short explanation. The caller makes the final payout decision.
- Store files and AI results off-chain. Store only escrow and payout events on Avalanche.
- Use a test token on Fuji. Do not implement fiat deposits, custody, or a custom currency.
- Use email/password login. Each account may link one Fuji wallet by signature for transactions.
  Never request or store a seed phrase or private key.
- Keep profiles, one-level call discussions, up to five author links, light/dark themes, and
  English/Vietnamese UI switching minimal.
- Keep caller review to three states: undecided, accepted, and rejected. Exact repeats of rejected
  file content are rejected before AI evaluation.

## Core invariants

- A call must be funded before it accepts contributions.
- A contribution can be paid at most once.
- A payout cannot exceed the call’s remaining escrow.
- AI output is a recommendation, not unquestionable truth.
- Uploaded content is untrusted and never becomes executable instructions.
- Token amounts use integer minor units, never floating-point values.

## Progress continuity

`docs/progress.md` is the implementation handoff and recovery record. Actively update it during implementation so an interruption does not cause work to be repeated or forgotten.

Update `docs/progress.md`:

- after every meaningful completed task;
- before ending an implementation session;
- when a decision, blocker, failure, or scope change occurs;
- after running important tests or commands;
- before switching to another major task.

Keep it concise and current. Record the present milestone, completed work, files changed, verification performed, known issues, and the exact next step. Replace stale status rather than accumulating a long diary. Never mark work complete without verification.

When resuming implementation, read `AGENTS.md`, `docs/progress.md`, and the relevant specification before changing code.

## Sources of truth

1. Owner’s latest instruction.
2. `AGENTS.md` for scope and working rules.
3. `docs/progress.md` for current implementation state.
4. `docs/PRD.md` for MVP behavior.
5. `docs/Decisions.md` for accepted choices.
6. Other `docs/` files for implementation details.

Resolve contradictions explicitly and update the affected document.

## Definition of done

A feature is done when its happy path works, its important failure path is handled, focused tests pass, and `docs/progress.md` reflects the verified result. Stop polishing once the hackathon requirement is satisfied.
