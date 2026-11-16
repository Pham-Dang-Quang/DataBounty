# Minimal API

Status: Outline

Most pages are server-rendered. JSON endpoints exist only where JavaScript needs them.

## Authentication

- `GET/POST /signup` — create an email/password account and session.
- `GET/POST /signin` — authenticate an email/password account.
- `GET/POST /settings` — view/update email, name, bio, picture, password, and linked wallet.
- `GET /profiles/{id}/picture` — serve a stored profile picture.
- `POST /api/auth/challenge` — return a one-time message for linking a wallet.
- `POST /api/auth/verify` — verify the signature and link/replace the account wallet.
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
- `GET /calls/{id}/review?tab=undecided|accepted|rejected` — filtered caller review queue.
- `POST /calls/{id}/comments` — add a top-level comment or one-level reply.

## Contributions

- `POST /calls/{id}/contributions` — submit one image plus `companion_text`, or one UTF-8 CSV file.
- `GET /contributions/{id}` — show status and result.
- `GET /api/contributions/{id}/evaluation` — return authenticated evaluation progress for polling.
- `POST /contributions/{id}/decision` — caller accepts or rejects and selects tier.
- `POST /contributions/{id}/payout-tx` — record a submitted payout transaction hash.

## Rules

- Require authentication for mutations.
- Allow one Fuji wallet per account and one account per wallet.
- Verify caller ownership for funding, review, and payout actions.
- Reject edits and removal after funding is submitted.
- Verify contributor ownership for private contribution views.
- Accept an idempotency key for decision and transaction-recording requests.
- Return simple errors with `code`, `message`, and optional field errors.
- Treat transaction hashes as pending until confirmed by Fuji.
- Reject exact repeats of rejected file content before scheduling AI evaluation.
