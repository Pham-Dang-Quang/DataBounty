# Minimal API

Status: Outline

Most pages are server-rendered. JSON endpoints exist only where JavaScript needs them.

## Authentication

- `POST /api/auth/challenge` — return one-time message for a wallet.
- `POST /api/auth/verify` — verify signature and create session.
- `POST /api/auth/logout` — end session.

## Calls

- `GET /` — list open calls.
- `GET /calls/new` — call form.
- `POST /calls` — create draft call.
- `GET /calls/{id}` — call detail and contribution form.
- `GET /calls/{id}/edit` — caller-only edit form for an unfunded draft.
- `POST /calls/{id}/edit` — update an unfunded draft.
- `POST /calls/{id}/delete` — remove an unfunded draft.
- `POST /calls/{id}/funding-tx` — record a submitted funding transaction hash; its sender must match the signed-in caller.
- `GET /calls/{id}/review` — caller review queue.

## Contributions

- `POST /calls/{id}/contributions` — upload and submit one file.
- `GET /contributions/{id}` — show status and result.
- `POST /contributions/{id}/decision` — caller accepts or rejects and selects tier.
- `POST /contributions/{id}/payout-tx` — record a submitted payout transaction hash.

## Rules

- Require authentication for mutations.
- Verify caller ownership for funding, review, and payout actions.
- Reject edits and removal after funding is submitted.
- Verify contributor ownership for private contribution views.
- Accept an idempotency key for decision and transaction-recording requests.
- Return simple errors with `code`, `message`, and optional field errors.
- Treat transaction hashes as pending until confirmed by Fuji.
