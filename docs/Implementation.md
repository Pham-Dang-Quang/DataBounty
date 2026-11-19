# Minimal Implementation Plan

Status: MVP and requested scope extension implemented; final two-account payout demo remains

## Suggested repository layout

```text
app/
  main.py
  auth.py
  call_rules.py
  lifecycle.py
  models.py
  previews.py
  review_service.py
  schemas.py
  upload_validation.py
  evaluation.py
  blockchain.py
  routes_*.py
  templates/
  static/css/
  static/js/
contracts/
tests/
data/uploads/        # ignored by Git
docs/
```

Keep each Python source file at or below roughly 300 lines. Split by an existing user flow or
business responsibility; do not add framework layers or speculative abstractions.

## Phase 1: local web flow

- Set up FastAPI, Jinja2, SQLite, SQLAlchemy, and tests.
- Implement email/password accounts, profiles, and one signature-linked transaction wallet.
- Implement call creation and listing.
- Implement image-text, typed CSV, and minimal image-segmentation-text upload validation. Gate CSV
  AI evaluation behind schema/type/row validation. Gate segmentation AI evaluation behind adaptive
  palette grouping, bounded reconstruction error and boundary complexity, distinct region edges,
  and source/mask aspect ratios within 0.5%; do not require matching pixel dimensions.
- Implement manual accept/reject without blockchain.
- Implement per-call moderators, reviewer attribution, rejected-data reconsideration, bulk AI
  decisions, and accepted-only ZIP export.

Exit: two wallets can complete the off-chain flow locally.

## Phase 2: AI assistance

- Configure one hosted open-source vision-language evaluator.
- Define and validate its three-field structured output.
- Run deterministic checks before inference.
- Show the recommendation beside manual review controls.
- Record model name and result.

Exit: example image-text, CSV, and segmentation contributions produce understandable recommendations, and failures fall
back to manual review.

## Phase 3: Avalanche Fuji

- Implement and test the minimal escrow contract and mock ERC-20.
- Deploy to Fuji and record addresses in configuration.
- Let callers fund calls and approve payouts through their wallet.
- Let callers approve ERC-20 allowance and call `addFunds` to buy additional acceptance slots. The
  backend changes the existing `max_acceptances` field only after Fuji confirms enough remaining
  escrow for every unpaid slot at the maximum reward tier.
- Keep submissions open until the deadline regardless of whether all currently funded slots are
  committed; block only further acceptance until the limit is expanded.
- Preserve all three hosted-model outcomes and allow combined AI recommendation filters in review.
- Read confirmed contract events and show transaction links/status.

Exit: the complete demo flow transfers a test reward exactly once.

## Phase 4: demo polish

- Add responsive styling and clear error/loading/empty states. Route browser errors back to the
  originating local page through a one-use session message and show them in the shared dismissible
  popup; never render a standalone error page.
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
