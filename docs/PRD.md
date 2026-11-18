# Minimal Product Requirements

Status: Hackathon MVP

## Product

The platform lets a caller request image-text pairs, typed CSV files, or image-segmentation-text
packages, fund a reward on Avalanche Fuji,
receive contributions, use AI to review them, and pay accepted contributors from escrow.

## Users

- **Caller:** creates and funds a data call, reviews contributions, and approves payouts.
- **Moderator:** is assigned by a caller using an existing account email and may only inspect,
  accept, reject, or reconsider contributions for that call.
- **Contributor:** finds a call, uploads one file, and receives a reward if accepted.

The same wallet may act as both.

## Core flow

1. User creates an account with email/password and optionally links a Fuji wallet by signature.
2. Caller creates a data call.
3. Caller may edit or remove the unfunded draft.
4. Caller funds the call’s escrow with the demo ERC-20 token.
5. The call becomes open after funding is confirmed.
6. Contributor uploads the required image/text, CSV, or segmentation package.
7. The platform performs basic validation and, if enabled, asks the AI model to evaluate the file against the caller’s criteria.
8. Caller or assigned moderator sees the file, validation result, AI recommendation, quality tier,
   and explanation. The interface records who made the decision.
9. A reviewer approves for payout or rejects the contribution. Rejected data may later be approved.
10. Approved data remains undecided and continues using its protected image preview until payment.
11. The caller sends the payout transaction through their wallet. Only confirmed-paid data becomes
    accepted and downloadable in the ZIP.
12. The UI shows the confirmed transaction and updated escrow balance.
13. Contributors may continue submitting after the acceptance limit is full. The caller may review
    them, but must add enough DBT to escrow and expand the limit before approving another payout.

## Data call fields

- Title and short description
- Data type: image-text pair, CSV, or image-segmentation-text package
- CSV schema: required `name:type` fields, delimiter, minimum rows, optional maximum rows,
  extra/missing-value rules, and an
  optional uniqueness field
- Segmentation components: image+segmentation, segmentation+text, or all three. Masks must contain
  clearly separated semantic color regions; mild shading and anti-aliasing are allowed, while
  photographic detail, heavy gradients, and visually complex noise are rejected. A supplied source
  image and mask may have different resolutions but must have the same aspect ratio, allowing up to
  0.5% relative difference for integer resizing/rounding.
- Detailed AI evaluation prompt
- Plain-language acceptance criteria
- Review mode: manual or AI-assisted
- Reward amount per accepted contribution
- Optional quality tiers: standard and high
- Maximum accepted contributions (1–100,000)
- Deadline

The caller may edit or remove only an unfunded draft. Terms freeze as soon as funding is submitted. Funded calls cannot be removed because their escrow and activity must remain traceable.

## AI behavior

AI-assisted review returns structured output:

- recommendation: accept, reject, or unsure;
- quality tier: standard or high;
- short explanation.

Basic deterministic checks run first: allowed type, non-empty file, size limit, readable content,
required components, typed CSV schema/row constraints, segmentation palette/complexity/aspect ratio,
and exact duplicate content within the call. Failed CSV or segmentation pre-checks are rejected
without storage or AI evaluation. An exact repeat
of previously rejected file content is rejected immediately without AI reevaluation. “Unsure”
requires human judgment. The caller or an assigned moderator makes the review decision and can
disagree with AI; only the caller controls payout.

Use hosted `Qwen/Qwen3-VL-8B-Instruct` through a configurable OpenAI-compatible API for all three
types. CSV and segmentation calls require AI-assisted review and a detailed assessment prompt. If
the API is disabled, missing, or fails, return `unsure` and require human review.
Do not download or run CLIP or Qwen locally.

## MVP requirements

- Responsive pages for calls, call creation, contribution upload, and caller review.
- Caller controls to edit or remove an unfunded draft.
- Email/password signup and signin, a basic profile (name, picture, bio), and one signature-linked
  Fuji wallet per account.
- Light/dark themes and an English/Vietnamese interface switch stored in the browser.
- One-level comments/replies on calls and up to five validated author/project links per call.
- Every visible account attribution pairs its name with its uploaded profile picture or a neutral
  default avatar; call details may also show the caller bio.
- Fuji testnet and a demo ERC-20 token.
- Escrow funding and one-time payouts.
- Image-text, typed CSV, and the three minimal segmentation component combinations.
- Contribution forms warn that submission is irreversible and contributions cannot be withdrawn.
- Invalid CSV is rejected before storage or AI evaluation. Reviewers cannot access CSV contents
  before confirmed payment; they receive deterministic validation and detailed AI assessment.
- Manual and AI-assisted review.
- Three caller-review tabs: undecided, accepted, and rejected. Approved data remains undecided until
  payout confirmation; accepted means confirmed paid.
- Caller-managed moderators identified by registered email; moderators have review access only.
- Caller-only bulk application of `accept`/`reject` AI recommendations and a confirmed-paid-only ZIP
  export containing files plus a CSV manifest.
- Undecided and rejected images use a stored, versioned, low-resolution derivative with repeated
  baked-in watermarks. Original image bytes are not sent to reviewers until payout confirmation. Companion
  text remains readable and unwatermarked for manual evaluation.
- Clear pending, confirmed, failed, empty, and validation-error states.
- Browser-facing errors return the user to the current page and appear in one dismissible, scrollable
  popup instead of a separate error page. API errors remain structured for the same popup in JavaScript.
- A live days/hours/minutes/seconds countdown beside each call's deadline.
- A simple audit timeline for call funding, submission, review, and payout.
- Owner-only additional funding that expands the acceptance limit after Fuji confirmation.
- Combined review filters for AI accept, reject, and unsure recommendations.

## Not in the MVP

- Fiat deposits or withdrawals
- A custom platform currency
- Mainnet deployment
- Fully automatic AI payouts
- Disputes or arbitration
- Arbitrary multi-file datasets, ZIP submissions, audio, video, or spreadsheet formats other than CSV
- Data resale, reputation, messaging, notifications, general teams, or administration dashboards
- Production KYC, moderation, scaling, high availability, or complex retention tooling
- Custom Avalanche L1 or cross-chain transfers

## Demo success

The MVP is successful when a reviewer can demonstrate one complete flow on Fuji: create and fund a call, upload data from another wallet, receive an AI recommendation, approve it, and show the contributor’s confirmed token payout.
