# Minimal Product Requirements

Status: Hackathon MVP

## Product

The platform lets a caller request image-text pairs or CSV data, fund a reward on Avalanche Fuji,
receive contributions, use AI to review them, and pay accepted contributors from escrow.

## Users

- **Caller:** creates and funds a data call, reviews contributions, and approves payouts.
- **Contributor:** finds a call, uploads one file, and receives a reward if accepted.

The same wallet may act as both.

## Core flow

1. User creates an account with email/password and optionally links a Fuji wallet by signature.
2. Caller creates a data call.
3. Caller may edit or remove the unfunded draft.
4. Caller funds the call’s escrow with the demo ERC-20 token.
5. The call becomes open after funding is confirmed.
6. Contributor uploads one image plus required companion text, or one UTF-8 CSV file.
7. The platform performs basic validation and, if enabled, asks the AI model to evaluate the file against the caller’s criteria.
8. Caller sees the file, validation result, AI recommendation, quality tier, and explanation.
9. Caller accepts or rejects the contribution.
10. For acceptance, the caller sends the payout transaction through their wallet.
11. The UI shows the confirmed transaction and updated escrow balance.

## Data call fields

- Title and short description
- Data type: image-text pair or CSV
- Plain-language acceptance criteria
- Review mode: manual or AI-assisted
- Reward amount per accepted contribution
- Optional quality tiers: standard and high
- Maximum accepted contributions
- Deadline

The caller may edit or remove only an unfunded draft. Terms freeze as soon as funding is submitted. Funded calls cannot be removed because their escrow and activity must remain traceable.

## AI behavior

AI-assisted review returns structured output:

- recommendation: accept, reject, or unsure;
- quality tier: standard or high;
- short explanation.

Basic deterministic checks run first: allowed type, non-empty file, size limit, readable content,
required image text, valid CSV structure, and exact duplicate content within the call. An exact repeat
of previously rejected file content is rejected immediately without AI reevaluation. “Unsure”
requires caller judgment. The caller always makes the final decision and can disagree with AI.

Use hosted `Qwen/Qwen3-VL-8B-Instruct` through a configurable OpenAI-compatible API for image-text
and CSV review. If the API is disabled, missing, or fails, return `unsure` and require manual review.
Do not download or run CLIP or Qwen locally.

## MVP requirements

- Responsive pages for calls, call creation, contribution upload, and caller review.
- Caller controls to edit or remove an unfunded draft.
- Email/password signup and signin, a basic profile (name, picture, bio), and one signature-linked
  Fuji wallet per account.
- Light/dark themes and an English/Vietnamese interface switch stored in the browser.
- One-level comments/replies on calls and up to five validated author/project links per call.
- Open-call cards identify the caller by profile name/avatar; call details may also show their bio.
- Fuji testnet and a demo ERC-20 token.
- Escrow funding and one-time payouts.
- Image plus required text, or UTF-8 CSV, with one uploaded file per contribution.
- Manual and AI-assisted review.
- Three caller-review tabs: undecided, accepted, and rejected. Only undecided items appear in the
  review counter.
- Clear pending, confirmed, failed, empty, and validation-error states.
- A simple audit timeline for call funding, submission, review, and payout.

## Not in the MVP

- Fiat deposits or withdrawals
- A custom platform currency
- Mainnet deployment
- Fully automatic AI payouts
- Disputes or arbitration
- Multiple uploaded files, ZIP datasets, audio, video, or spreadsheet formats other than CSV
- Data resale, reputation, messaging, notifications, teams, or administration dashboards
- Production KYC, moderation, scaling, high availability, or complex retention tooling
- Custom Avalanche L1 or cross-chain transfers

## Demo success

The MVP is successful when a reviewer can demonstrate one complete flow on Fuji: create and fund a call, upload data from another wallet, receive an AI recommendation, approve it, and show the contributor’s confirmed token payout.
