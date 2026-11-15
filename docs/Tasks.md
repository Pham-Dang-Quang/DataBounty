# Hackathon Tasks

Status: Core MVP implemented; final two-wallet contribution and payout demo remains

## 0. Confirm scope

- [x] Use `DataBounty` as the hackathon project name.
- [x] Choose the first demo models and document their license/hardware limits.
- [x] Set the upload limit to 5 MB; reward amounts remain caller-selected per call.

## 1. Local application

- [x] Create the minimal Python project and dependency lock.
- [x] Add FastAPI, Jinja2, CSS, SQLite, and SQLAlchemy.
- [x] Implement wallet challenge/signature login.
- [x] Implement create/list/view data calls.
- [x] Implement caller-only edit/remove controls for unfunded drafts.
- [x] Implement validated one-file image/text contribution.
- [x] Implement caller review and manual decision.
- [x] Add focused tests for ownership, validation, and duplicate submissions.

## 2. AI assistance

- [x] Add deterministic file checks.
- [x] Add model adapters with structured output.
- [x] Store and display recommendation, tier, explanation, and model name.
- [x] Handle disabled/model errors by returning an `unsure` manual-review result.
- [x] Test with a small synthetic example set.

## 3. Avalanche Fuji

- [x] Write the minimal escrow contract and mock ERC-20.
- [x] Test funding, payout, duplicate rejection, insufficient balance, and refund.
- [x] Deploy contracts to Fuji and record addresses.
- [x] Add browser funding and payout transactions with `viem`.
- [x] Confirm transactions with `web3.py` and update application status.

## 4. Demo readiness

- [x] Add responsive styling and clear states.
- [x] Add sample data and demo setup instructions.
- [x] Run Python integration and contract happy-path tests.
- [x] Remove unused code and deferred UI.
- [ ] Complete the full demo with two wallets.

Update `progress.md` after every meaningful item.
