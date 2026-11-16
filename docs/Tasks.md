# Hackathon Tasks

Status: Core MVP implemented; final two-wallet contribution and payout demo remains

## 0. Confirm scope

- [x] Use `DataBounty` as the hackathon project name.
- [x] Choose the hosted Qwen evaluator and document its API/privacy boundary.
- [x] Set the upload limit to 5 MB; reward amounts remain caller-selected per call.

## 1. Local application

- [x] Create the minimal Python project and dependency lock.
- [x] Add FastAPI, Jinja2, CSS, SQLite, and SQLAlchemy.
- [x] Implement email/password accounts, basic profiles, and one linked transaction wallet.
- [x] Implement create/list/view data calls.
- [x] Implement caller-only edit/remove controls for unfunded drafts.
- [x] Implement validated image-plus-text and UTF-8 CSV contributions.
- [x] Implement caller review and manual decision.
- [x] Add focused tests for ownership, validation, and duplicate submissions.

## 2. AI assistance

- [x] Add deterministic file checks.
- [x] Add one OpenAI-compatible hosted-model adapter with structured output.
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
- [x] Add light/dark and English/Vietnamese browser preferences.
- [x] Add up to five call-author links and one-level comments/replies.
- [x] Remove duplicate owner call cards; add undecided/accepted/rejected review tabs and counts.
- [x] Reject exact repeats of rejected data before AI evaluation.
- [ ] Complete the full demo with two wallets.

Update `progress.md` after every meaningful item.
