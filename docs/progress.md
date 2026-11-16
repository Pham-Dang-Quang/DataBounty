# Implementation Progress

Last updated: 2026-11-16

## Current status

- Phase: Review workflow and data-type revision
- State: Implemented and verified
- Next demo milestone: configure hosted AI and test a new image-text pair or CSV contribution

## Completed

- Replaced local CLIP/Transformers inference with one OpenAI-compatible hosted evaluator.
- Selected `Qwen/Qwen3-VL-8B-Instruct` as the default criteria-aware image-text/CSV model.
- Added validated `accept`/`reject`/`unsure`, tier, and explanation parsing plus an explicit `unsure`
  fallback for disabled, missing, failed, or invalid API responses.
- Removed local PyTorch/Transformers/CUDA dependencies and model-cache configuration.
- Added email/password signup and signin using scrypt password hashes and session cookies.
- Added editable email, display name, bio, profile picture, and password settings.
- Added one signature-verified Fuji wallet per account; one wallet cannot belong to two accounts.
- Preserved a wallet-signature recovery path for existing wallet-only users so funded calls remain
  accessible during migration.
- Added persistent browser-local light/dark and English/Vietnamese switches across core pages.
- Added up to five validated HTTP(S) author/project links per call.
- Added authenticated call comments and one-level replies.
- Applied additive SQLite migration for account fields, links, and comments to the existing database.
- Cleared all rows from the active SQLite database; the recovery backup and upload directory were preserved.
- Added a shared error popup for wallet/evaluation errors.
- Added a top-right × dismiss button and an independently scrollable area for long error messages;
  versioned the UI and CSS assets to prevent stale browser caching.
- Diagnosed Fuji revert selector `0x15d64c28` as `CallAlreadyExists()`: clearing SQLite had reused
  local ID 1 while escrow call 1 remained funded on the persistent contract.
- New calls now receive independent random positive 63-bit escrow IDs, and the browser ABI includes
  the contract custom errors for readable reverts.
- Reassigned current unfunded draft 1 to Fuji-verified-unused escrow ID `6926560940804481703`.
- Recovered confirmed funding transaction `0x2742…c16ef` after the backend RPC initially could not
  retrieve it; verified sender, owner, escrow ID, and 9,999,995-unit budget, then opened call 1.
- Funding and payout JavaScript now waits for a successful Fuji receipt before submitting the hash
  to FastAPI, preventing RPC propagation races; wallet asset version advanced to v6.
- Purged all local calls and related contributions, comments, links, and events at the owner's
  request. Removed all contribution/orphan data uploads and the old database recovery copy while
  preserving two user accounts and the profile-prefixed image.
- Added caller identity to open-call cards for every account: profile avatar/name appear in the
  marketplace, and the call page also shows the caller bio and links without exposing email.
- Removed duplicate owner call cards by excluding the signed-in caller's calls from the separate
  open-call section.
- Added undecided, accepted, and rejected review tabs with per-tab counts; the call-page review
  counter now includes only undecided contributions.
- Replaced new-call image/text choices with image-text pairs and UTF-8 CSV. Image uploads require a
  1–2000 character text label/description; CSV validation requires a header, data row, and consistent
  columns. The hosted evaluator receives both parts of an image-text pair.
- Exact file content matching a rejected contribution now receives an immediate 409 rejection and
  never enters background AI evaluation.
- Replaced hard-coded light UI colors with theme variables for forms, notices, badges, code blocks, and modal content.
- Removed visible hackathon wording from the application UI and translations.
- Updated `AGENTS.md`, `README.md`, and all specifications for the implemented design.

## Main files changed

- Configuration and dependencies: `.env.example`, `pyproject.toml`, `uv.lock`
- Backend: `app/auth.py`, `app/config.py`, `app/db.py`, `app/evaluation.py`, `app/main.py`,
  `app/models.py`
- Interface: `app/templates/`, `app/static/css/app.css`, `app/static/js/ui.js`,
  `app/static/js/wallet.js`
- Verification: `tests/`
- Documentation: `AGENTS.md`, `README.md`, `docs/`

## Verification

- `uv run ruff check app tests`: passed.
- `uv run mypy app`: passed with no issues in 8 source files.
- `uv run pytest`: 31 passed in 7.00 seconds, including duplicate-list prevention, undecided-only
  counters, three review tabs, rejected-repeat short-circuiting, image-text requirements, and CSV
  validation.
- Provider-default verification: Ruff and mypy passed; all 8 evaluation tests passed.
- Final focused funding/UI verification: 10 passed; wallet JavaScript syntax passed; draft 1 remains
  unfunded and points to escrow ID `6926560940804481703`.
- Read-only Fuji query confirmed escrow call 1 already exists with 45,000,000 minor units and is
  owned by `0x8D6B…Fc24`; the replacement ID was confirmed unused before updating SQLite.
- Fuji event recovery confirmed repaired escrow ID `6926560940804481703` in block 61180660 with
  9,999,995 units; the local call is now `open`.
- `node --check` passed for `ui.js`, `wallet.js`, and `evaluation.js`.
- `git diff --check`: passed; only expected Windows LF-to-CRLF notices were printed.
- Purge verification recorded 2 preserved users and zero call-related rows; a new open call has since
  been created for the continuing demo.
- Existing SQLite database additive migration: completed successfully.
- Active database migration added `contributions.companion_text` and converted call data type
  `image` to `image_text`; the existing paid legacy contribution remains unchanged with no invented
  companion text.
- Hosted API success, structured parsing, image data-URL request, API failure fallback, account/profile,
  legacy recovery, links, comments, replies, themes, and language controls have focused tests.

## Configuration required

- OpenRouter's base URL and exact `qwen/qwen3-vl-8b-instruct` model slug are now preconfigured.
  No live provider credential is stored, so runtime evaluation correctly returned the explicit
  `deterministic-fallback` result. Add `AI_API_KEY` and set `ENABLE_AI_API=true` in `.env`.
- Enabling hosted evaluation sends contribution content and caller criteria to that provider.

## Known constraints

- One wallet per account is intentional for the minimal hackathon build; multiple-wallet management
  is deferred.
- Discussions have one reply level and no moderation, voting, deletion, or notifications.
- Translation covers application-owned core UI text. User content, stored event messages, model
  explanations, and server validation messages are not machine-translated.

## Exact next step

Add an OpenRouter API key to `.env`, set `ENABLE_AI_API=true`, restart the app, then submit one new
image-text pair or valid CSV contribution from the second account and verify its review tab flow.
