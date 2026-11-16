# Minimal Implementation Plan

Status: MVP and requested scope extension implemented; final two-account payout demo remains

## Suggested repository layout

```text
app/
  main.py
  auth.py
  models.py
  schemas.py
  services/
    evaluation.py
    blockchain.py
  templates/
  static/css/
  static/js/
contracts/
tests/
data/uploads/        # ignored by Git
docs/
```

Create more modules only when a file becomes difficult to understand.

## Phase 1: local web flow

- Set up FastAPI, Jinja2, SQLite, SQLAlchemy, and tests.
- Implement email/password accounts, profiles, and one signature-linked transaction wallet.
- Implement call creation and listing.
- Implement one-file contribution upload and validation.
- Implement manual accept/reject without blockchain.

Exit: two wallets can complete the off-chain flow locally.

## Phase 2: AI assistance

- Configure one hosted open-source vision-language evaluator.
- Define and validate its three-field structured output.
- Run deterministic checks before inference.
- Show the recommendation beside manual review controls.
- Record model name and result.

Exit: example image-text/CSV contributions produce understandable recommendations, and failures fall
back to manual review.

## Phase 3: Avalanche Fuji

- Implement and test the minimal escrow contract and mock ERC-20.
- Deploy to Fuji and record addresses in configuration.
- Let callers fund calls and approve payouts through their wallet.
- Read confirmed contract events and show transaction links/status.

Exit: the complete demo flow transfers a test reward exactly once.

## Phase 4: demo polish

- Add responsive styling and clear error/loading/empty states.
- Add sample calls and a short demo script.
- Run focused backend, contract, and end-to-end tests.
- Remove unused dependencies and incomplete features.
- Add browser-local light/dark and English/Vietnamese controls.
- Add minimal call author links and one-level discussions.

Exit: a fresh setup can reproduce the hackathon demo.

## Implementation rules

- Finish one phase before starting the next.
- Update `docs/progress.md` continuously.
- Use fake/synthetic demo data only.
- Do not optimize for scale.
- Do not add a production feature to solve a demo-only problem.
