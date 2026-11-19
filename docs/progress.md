# Implementation Progress

Last updated: 2026-11-19

## Current status

- Phase: Application source refactor
- State: Split the oversized FastAPI entry point and evaluation module into focused route and
  business-rule modules. Every Python file under `app/` is now 277 lines or fewer, with no database,
  schema, template, static-asset, or user-data changes.
- Next milestone: review the module boundaries, then continue the existing Fuji deployment/demo
  milestone without changing the active database.

### Latest source refactor

- Reduced `app/main.py` from 1,928 lines to application assembly only.
- Grouped routes by accounts, call creation/management, community, funding, submissions, review,
  and contribution files/actions.
- Extracted call rules, review decisions, preview generation, chain/evaluation lifecycle work,
  shared web dependencies, request schemas, constants, and deterministic upload validation.
- Kept the existing endpoints, templates, database models, and AI API contract unchanged.
- Verification: all app files are at most 275 lines; Ruff, mypy, and `git diff --check` pass. The
  full suite ran outside the restricted Windows sandbox and all 57 tests passed. The discussion
  test now opens its call before exercising visitor comments, matching the documented restriction
  that draft discussions are caller/moderator-only.

### Latest demo seed work

- Added `demo/seed_demo_content.py`, an idempotent SQLite/file seeder using the existing models.
- Added `demo_account/accounts.csv` and `demo_account/README.md` with 10 local-only accounts.
- Added `demo_data/` with five call-specific subdirectories and `SOURCES.md`; each call has 3 invalid,
  3 valid-but-low-quality, and 3 valid-good fixtures. Segmentation fixtures include paired masks.
- Seeded three comments/replies per call and persisted AI recommendations/validation summaries so the
  review UI can demonstrate reject, unsure, and accept paths.
- Verification: seeder completed; Ruff passed for the seeder; SQLite inspection confirmed 10 demo users,
  5 named calls, 9 contributions per call, and discussion rows. The generated files are artificial and
  do not redistribute third-party source data.
- Follow-up verification: `demo_data/` contains only `info_call_1.md` through `info_call_5.md`; the
  named calls have zero seeded contributions; the account CSV and database contain the natural demo
  identities; Ruff still passes for the seeder.
- Added `demo/seed_discussions.py` with call-specific debate prompts and one-level replies. Every call,
  including Phạm Đăng Quang's existing chest X-ray call, now has 24-26 comments/replies. Ruff passed
  for both demo seed scripts.
- Per owner instruction, changed the five newly added calls to `draft` and cleared their fabricated
  funding transaction hashes. Their escrow IDs and budgets remain intact for the owner's real Fuji
  funding transactions; no contributions can be submitted while they are drafts.
- Draft discussion policy is now enforced in `app/main.py`: only the caller or an assigned moderator
  may post comments on a draft call. Removed all prior draft-call comments, assigned two moderators to
  each of the five draft calls, and seeded 16 caller/moderator-only debate comments per call.
- Verification: all five draft calls have two moderators, 16 comments each, and every comment author is
  either the caller or an assigned moderator; Ruff passes for the changed application and seed script.
- Replaced the earlier robotic discussion copy with natural, call-specific back-and-forth: concrete
  examples, disagreements, follow-up questions, and concessions across all six calls. Each call now
  has 16 comments/replies; draft-call authorship remains caller/moderator-only. Ruff passes for the
  refresh script and database verification completed successfully.
- Rotated draft-call ownership and moderation across the demo accounts: each of the five draft calls
  now has a different caller and a distinct two-person moderator pair. Rebuilt their discussions with
  matching authors and staggered UTC timestamps over roughly six days; verification confirms no future
  timestamps and 16 comments per draft call. Added `demo/rebalance_draft_discussions.py`.
- Kept the reproducible scripts under `demo/` as source while ignoring generated `demo_account/` and
  `demo_data/` outputs so demo credentials and disposable fixtures are not committed.

## Completed

- Added owner-only `addFunds` escrow funding with exact-transfer checks and a funding-added event.
  The caller UI prices each additional acceptance slot at the maximum reward tier, approves DBT,
  submits the Fuji top-up, and expands `max_acceptances` only after the backend verifies confirmation,
  exact escrow/caller/call/amount calldata, transaction reuse, and sufficient remaining liability.
  No schema change was needed.
- Confirmed that submissions were already independent of the acceptance limit and made that behavior
  explicit: contributors may submit until the deadline, while manual and bulk acceptance stop at the
  funded limit. Callers can still inspect the queued data before funding more slots.
- Confirmed the hosted evaluator already parses explicit `accept`, `reject`, and `unsure` outputs;
  added direct `unsure` coverage plus combined accept/reject/unsure filters across all review tabs.
- This funding/filter implementation made no active-database or schema changes; the separate demo
  seeding work is recorded in the current-status section above.
- Decoded payout revert `0xf8166afa` as `ContributionAlreadyPaid()` and verified recorded Fuji
  transaction `0x9f2b…e96` succeeded at block 61268671, transferring 2,000,000 DBT units to the
  intended contributor. Reconciled the active resubmitted contribution 2 to `paid`/Accepted; no
  second payment is required. Submitted payouts now hide the Pay action and refresh until confirmed.
- Replaced reusable SQLite-ID payout hashes with stored random `bytes32` payout keys for new
  contributions. The additive migration preserves legacy hashes for existing rows so confirmed
  transactions remain discoverable after upgrading.
- Revised active call 1 so standalone red/blue bilateral lung masks on plain backgrounds are valid,
  and explicitly high quality when contrast, boundaries, fills, bilateral separation, and cleanliness
  are strong. Removed the latest resubmitted `good_segmentation.png` (contribution 2), its 2 events,
  and both mask/source files at the owner's request; contribution 1 remains.
- Permanently removed every database backup under `data/backups/` at the owner's request. No local
  recovery copy was retained. Added local caches, presentation output, backups, and manual sample
  data to `.gitignore` while keeping application assets, templates, and tests visible to Git.
- Fixed two-image segmentation framing after Qwen conflated a separate X-ray source with its mask.
  The evaluator now sends the mask first as the primary artifact, labels the source as context only,
  and instructs both system and user prompts never to composite the files or infer an overlay from
  the source's presence.
- Cleared the active demo database again at the owner's request: removed the current call, 3
  contributions, 14 events, all other call-dependent rows, and 10 non-profile uploads while
  preserving 2 user accounts.
- Switched `.env` to token `0x1f8e…C4AB` and escrow `0xDC43…d7F0`. On-chain verification confirms the
  escrow's immutable reward token is the configured token.
- Replaced local CLIP/Transformers inference with one OpenAI-compatible hosted evaluator.
- Selected `Qwen/Qwen3-VL-8B-Instruct` as the shared criteria-aware evaluator for image-text, CSV,
  and image-segmentation-text.
- Added validated `accept`/`reject`/`unsure`, tier, and explanation parsing plus an explicit `unsure`
  fallback for disabled, missing, failed, or invalid API responses.
- Removed local PyTorch/Transformers/CUDA dependencies and model-cache configuration.
- Added email/password signup and signin using scrypt password hashes and session cookies.
- Added editable email, display name, bio, profile picture, and password settings.
- Replaced Quang Pham's placeholder bio with concise professional project-focused copy. Every
  visible account name now includes its uploaded picture or a bundled neutral default avatar through
  one shared template component.
- Fixed the default avatar to use its static asset URL directly in rendered templates, avoiding a
  broken image when templates reload before the Python profile route; missing uploaded files also
  fall back safely after restart.
- Added one signature-verified Fuji wallet per account; one wallet cannot belong to two accounts.
- Preserved a wallet-signature recovery path for existing wallet-only users so funded calls remain
  accessible during migration.
- Added persistent browser-local light/dark and English/Vietnamese switches across core pages.
- Added up to five validated HTTP(S) author/project links per call.
- Added authenticated call comments and one-level replies.
- Applied additive SQLite migration for account fields, links, and comments to the existing database.
- Added a shared error popup for wallet/evaluation errors.
- Added a top-right × dismiss button and an independently scrollable area for long error messages;
  versioned the UI and CSS assets to prevent stale browser caching.
- Removed the standalone error page. Browser HTTP/unexpected errors now return to the originating
  same-site page with a one-use session message and open the existing dismissible, scrollable popup;
  API and wallet errors continue through JSON/JavaScript into the same popup.
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
- Kept exactly three user-facing review tabs: undecided, accepted, and rejected. Approved items stay
  undecided until payout confirmation; accepted means confirmed paid. The call-page review
  counter now includes only undecided contributions.
- Standardized new calls on image-text pairs. Image uploads require a 1–2000 character text
  label/description, and the hosted evaluator receives both parts of the pair.
- Exact file content matching a rejected contribution now receives an immediate 409 rejection and
  never enters background AI evaluation.
- Replaced hard-coded light UI colors with theme variables for forms, notices, badges, code blocks, and modal content.
- Removed visible hackathon wording from the application UI and translations.
- Updated `AGENTS.md`, `README.md`, and all specifications for the implemented design.
- Added caller-managed, per-call moderators by registered email. Moderators can inspect review data
  and make individual decisions but cannot edit/remove/fund/pay calls, manage moderators, apply AI
  recommendations in bulk, or export accepted data.
- Stored and displayed the account that last accepted or rejected each contribution; callers can
  reconsider and accept previously rejected data.
- Added a caller-only action that applies all decisive AI recommendations while respecting the
  call acceptance limit. `unsure` recommendations remain undecided.
- Added caller-only accepted-data ZIP export with source files and `manifest.csv`; only confirmed-
  paid contributions are included. Rejected and undecided contributions, including approved items
  without confirmed payment, are excluded.
- Documented the unavoidable browser boundary: authorized reviewers can save content they are able
  to inspect, so the MVP enforces authorization and accepted-only export rather than DRM.
- Replaced raw undecided/rejected image responses with a stored, versioned derivative capped at
  480×480, recompressed as JPEG, and covered by translucent repeated ASCII contribution-ID
  watermark bands and diagonal marks. Version 4 uses fewer, lighter marks and quality 40 so manual
  evaluation remains practical. A distinct preview URL prevents an older raw browser response from
  being reused; only confirmed-paid pages switch back to the original image URL.
- Restored readable, unwatermarked companion text. Added `no-store` headers, image
  copy/drag/context-menu deterrence, and one audit event per reviewer/contribution.
- Collapsed each call's activity timeline into a native dropdown with an event count; transaction
  links and the complete audit history remain available when expanded.
- Added a localized live deadline countdown on call details with days, hours, minutes, seconds, and
  an expired state.
- Added typed CSV calls with deterministic schema, datatype, delimiter, row-range, missing/extra,
  and uniqueness validation. Invalid CSV is rejected before storage/AI; reviewers see validation and
  detailed AI assessment but cannot fetch CSV bytes before confirmed payment.
- Made the CSV maximum record count optional; blank stores no upper limit while the minimum remains
  enforced.
- Added Image-Segmentation-Text calls with Image+Segmentation, Segmentation+Text, or all-three modes.
  Source images and masks use separate protected derivatives, and the existing hosted Qwen adapter
  evaluates the requested components using the caller's detailed prompt.
- Replaced exact-color segmentation validation with adaptive 16-color palette grouping. Mild
  shading and anti-aliasing now pass when average reconstruction error is at most 18, while the
  pre-check still requires meaningful color groups and strong region boundaries and rejects grouped
  boundary complexity above 45%. The supplied example with 44,547 exact colors passes at 7.5 error
  and 18.1% complexity. Source images must still match mask aspect ratio. Failed mask or CSV checks
  create no contribution or AI evaluation. Submission remains irreversible.
- Explicitly allowed source images and segmentation masks to use different pixel resolutions. Their
  aspect ratios may differ by at most 0.5% to tolerate integer resize rounding; end-to-end coverage
  now submits a 120×80 mask with a 300×200 source image.
- Raised the caller-controlled maximum accepted contributions limit from 100 to 100,000 in both the
  HTML form and backend validation; coverage confirms a call with 1,000 acceptances is stored.
- Added `pitch.md` with a concise, bullet- and number-based problem-to-solution slide outline;
  each slide stays within the requested 40-word limit.
- Reworked `pitch.md` for a smoother narrative and added `presentation.md` with transitions,
  talking points, and suggested timing; both presentation-only files are ignored by Git.
- Condensed the first three problem slides in `pitch.md` to one sentence each, keeping detail in
  the speaker flow.
- Reworked all `pitch.md` slide copy into short, glanceable phrases and incomplete talking-point
  fragments for distracted viewers.
- Added a final closing slide to `pitch.md`; judge-question slides are intentionally pending the
  owner's answers and preferred positioning.

## Main files changed

- Configuration and dependencies: `.env.example`, `pyproject.toml`, `uv.lock`
- Backend: `app/auth.py`, `app/config.py`, `app/db.py`, `app/evaluation.py`, `app/main.py`,
  `app/models.py`
- Interface: `app/templates/`, `app/static/css/app.css`, `app/static/js/ui.js`,
  `app/static/js/wallet.js`
- Verification: `tests/`
- Documentation: `AGENTS.md`, `README.md`, `docs/`

## Verification

- Expansion/filter verification: Ruff and mypy passed; `wallet.js` and `ui.js` passed `node --check`;
  all 6 Foundry tests passed, including owner-only added funding and updated remaining balance. The
  13 frontend tests, explicit AI-unsure test, and pure remaining-liability test passed (15 focused
  tests total). Authenticated temporary-database runs, including the pre-existing health test,
  stalled in the existing test harness and were stopped without touching active data.
- Fuji verification: transaction `0x9f2b…e96` has status 1, emits the expected DBT transfer and
  `ContributionPaid` event for call `6373351965198043963` and legacy key `keccak256("2")`; the
  escrow's `paid` lookup returns true. Local contribution 2 is now `paid`, has exactly one payout
  confirmation event, and SQLite integrity is `ok`.
- Payout-key verification: the focused persistence test and all 12 frontend-asset tests passed;
  Ruff, mypy, `node --check` for `wallet.js`/`ui.js`, and `git diff --check` passed.
- `uv run ruff check app tests`: passed.
- `uv run mypy app`: passed with no issues in 8 source files.
- `uv run pytest`: 50 passed, including duplicate-list prevention, undecided-only
  counters, three payment-aware review tabs, rejected-repeat short-circuiting, image-text requirements,
  moderator permissions, reviewer attribution, rejected-data reconsideration, bulk AI
  decisions, accepted-only ZIP contents, persisted protected-image transformation, original image
  isolation, readable companion text, no-store headers, and access auditing.
- Profile verification covers the default-avatar response and shared avatar/name rendering across
  navigation, caller cards, call details, discussions, moderators, contributors, and reviewers.
- Typed CSV tests cover schema syntax, five datatypes, delimiters, row limits, extra/missing fields,
  uniqueness, direct rejection, confidential pre-payment review, detailed hosted-model prompts, and
  a blank maximum-record field persisting as no upper limit.
- Segmentation tests cover required components, multi-color flat masks, gradient/noise rejection,
  aspect-ratio enforcement, separate protected mask/source previews, and reuse of the hosted vision
  request with both images.
- Provider-default verification: Ruff and mypy passed; all 8 evaluation tests passed.
- Final focused funding/UI verification: 10 passed; wallet JavaScript syntax passed; draft 1 remains
  unfunded and points to escrow ID `6926560940804481703`.
- Read-only Fuji query confirmed escrow call 1 already exists with 45,000,000 minor units and is
  owned by `0x8D6B…Fc24`; the replacement ID was confirmed unused before updating SQLite.
- Fuji event recovery confirmed repaired escrow ID `6926560940804481703` in block 61180660 with
  9,999,995 units; the local call is now `open`.
- `node --check` passed for `ui.js`, `wallet.js`, and `evaluation.js`.
- `git diff --check`: passed; only expected Windows LF-to-CRLF notices were printed.
- Protected-preview tests require measurable watermark-colored pixel coverage while keeping the
  underlying image visible for manual review.
- Purge verification recorded 2 preserved users and zero call-related rows; a new open call has since
  been created for the continuing demo.
- Existing SQLite database additive migration: completed successfully.
- Active SQLite migration created `call_moderators` and added `contributions.reviewer_id` without
  changing existing calls or contributions.
- Active SQLite migration added call-level CSV/segmentation/AI-prompt fields and optional
  contribution source-image/validation fields without changing existing rows.
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

- The currently configured Fuji escrow predates `addFunds` and cannot be upgraded. Top-ups require a
  new deployment and address configuration; existing calls bound to the old escrow cannot use this
  feature in place.
- The resumed Fuji deployment succeeded from `0xbe51…7698b`; its nonce advanced from 1 to 4. Token
  `0x1f8e…C4AB` and escrow `0xDC43…d7F0` contain verified on-chain bytecode (3,778 and 5,330 hex
  characters respectively), and the application now uses this fresh deployment.
- One wallet per account is intentional for the minimal hackathon build; multiple-wallet management
  is deferred.
- Discussions have one reply level and no moderation, voting, deletion, or notifications.
- Translation covers application-owned core UI text. User content, stored event messages, model
  explanations, and server validation messages are not machine-translated.
- An authorized caller/moderator can still screenshot a protected preview in a normal browser or
  photograph the display. The preview is deliberately low-quality and heavily watermarked; original
  undecided/rejected bytes are never sent, unrelated accounts are denied, and only accepted data
  appears in the caller-only bulk export.
- Hidden CSV contents are disclosed to the configured hosted AI provider for assessment. The prompt
  instructs the model to summarize quality without quoting raw records, but provider privacy terms
  still apply.

## Exact next step

Deploy the updated contracts to Fuji, update `TOKEN_CONTRACT_ADDRESS` and
`ESCROW_CONTRACT_ADDRESS`, restart the app, then create and initially fund a fresh call before testing
the additional-slot top-up. Do not modify the active demo database until the owner's separate data
enrichment agent has finished.
