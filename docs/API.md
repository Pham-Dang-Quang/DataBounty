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
- `GET /calls/{id}/review?tab=undecided|accepted|rejected` — caller/moderator review queue. An
  approved contribution stays undecided until payout confirmation; accepted means confirmed paid.
- `POST /calls/{id}/moderators` — caller adds an existing account by email.
- `POST /calls/{id}/moderators/{user_id}/delete` — caller removes a moderator.
- `POST /calls/{id}/review/apply-ai` — caller applies every decisive AI recommendation that fits
  the acceptance limit.
- `GET /calls/{id}/accepted.zip` — caller downloads confirmed-paid files and `manifest.csv` only.
- `POST /calls/{id}/comments` — add a top-level comment or one-level reply.

## Contributions

- `POST /calls/{id}/contributions` — submit the call's image-text, CSV, or segmentation package;
  segmentation uses `contribution_file` for the mask and optional `source_image_file` for the source.
  CSV schema/type/row failures and segmentation palette, complexity, or aspect-ratio failures return
  `422` before files are stored or AI evaluation is queued.
- `GET /contributions/{id}` — show status and result.
- `GET /contributions/{id}/file` — give contributors their original; for undecided/rejected images,
  give reviewers the stored protected derivative. Pre-payment CSV is denied to reviewers.
- `GET /contributions/{id}/protected-image-v4` — versioned stored watermarked image derivative for
  authorized reviewers before confirmed payout.
- `GET /contributions/{id}/source-file` and `/source-protected-image-v1` — original or protected
  segmentation source image according to contributor/reviewer/payment state.
- `GET /api/contributions/{id}/evaluation` — return authenticated evaluation progress for polling.
- `POST /contributions/{id}/decision` — caller/moderator accepts or rejects, or re-accepts rejected
  data, and selects a tier.
- `POST /contributions/{id}/payout-tx` — record a submitted payout transaction hash.

## Rules

- Require authentication for mutations.
- Allow one Fuji wallet per account and one account per wallet.
- Verify caller ownership for call management, moderator management, bulk decisions, export,
  funding, and payout actions.
- Permit assigned moderators only to view review data and submit individual decisions.
- Reject edits and removal after funding is submitted.
- Permit private contribution files only to their contributor and assigned reviewers. Browser
  display is not DRM: a reviewer can save or screenshot a protected preview, but the original bytes
  are not sent before confirmed payout.
- Accept an idempotency key for decision and transaction-recording requests.
- Return simple errors with `code`, `message`, and optional field errors.
- Treat transaction hashes as pending until confirmed by Fuji.
- Reject exact repeats of rejected file content before scheduling AI evaluation.
