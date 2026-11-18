# Decisions

Only current scope-shaping decisions are listed.

## Accepted

### Minimal hackathon scope

Build one understandable vertical slice. Defer production scale and optional marketplace features.

### Python-first application

Use FastAPI, Jinja2, SQLAlchemy, SQLite, and Python AI libraries. Use plain CSS and limited vanilla JavaScript. Do not use an SPA framework.

### Simple local infrastructure

Use SQLite, local private uploads, and simple background execution. PostgreSQL, S3, Celery, and Redis are deferred.

### Fuji test rewards

Use a mock ERC-20 on Avalanche Fuji. Do not implement fiat, custody, a custom currency, mainnet, a custom L1, or cross-chain transfers.

### Minimal Solidity

Use one small escrow contract for funding, one-time payout, balance limits, deadline refund, and events. All application and AI logic stays in Python.

### Caller-controlled final decisions

Support manual and AI-assisted review. AI returns a recommendation; the caller or an assigned
moderator decides, while only the caller submits payout. Fully automatic AI payout is deferred.

### Hosted criteria-aware evaluator

Use `Qwen/Qwen3-VL-8B-Instruct` through a configurable OpenAI-compatible chat-completions API for
image-text, CSV, and image-segmentation-text contributions. This replaces CLIP because a
vision-language model can reason
about caller-specific criteria. No checkpoint, CUDA runtime, or local model cache is required.
Uploaded contribution content is sent to the configured provider when API evaluation is enabled.
API failure always becomes an explicit `unsure` result; AI never controls payouts.

### Minimal accounts and community fields

Use email/password sessions and scrypt password hashes. Allow a name, bio, profile image, and one
signature-verified Fuji wallet per account. Multiple-wallet management is deferred because one
transaction wallet completes the hackathon flow with less identity and payout ambiguity.

All visible account names use one shared avatar/name component. Accounts without an uploaded image
receive a neutral bundled avatar so attribution remains visually consistent without inventing a
personal photograph.

Calls may contain at most five validated HTTP(S) author/project links. Discussions support top-level
comments and one reply level only; moderation, deletion, voting, and notifications are deferred.

Theme and English/Vietnamese choices are browser-local preferences, not account settings.

### Minimal live evaluation progress

Store a percentage and short stage on each contribution and poll an authenticated JSON endpoint.
This is sufficient for one-process background evaluation; WebSockets, Redis, and Celery remain
outside the MVP.

### One browser error surface

Browser-facing HTTP and unexpected errors use a one-use signed-session message, redirect to the
originating same-site page, and open the shared scrollable popup. API requests retain JSON errors so
vanilla JavaScript can open that same popup. This avoids maintaining separate error pages.

### Minimal contribution types

Accept image+text, typed UTF-8 CSV, or a segmentation package containing image+segmentation,
segmentation+text, or all three. CSV uses a small fixed schema language (`name:type`) with five
types, delimiter, required minimum and optional maximum rows, extra/missing flags, and optional uniqueness. Invalid CSV is
rejected deterministically before AI. Pre-payment CSV bytes remain hidden from reviewers, so the
hosted model provides the detailed assessment. The existing Qwen adapter accepts CSV text or the
one/two segmentation images and reuses the caller's detailed prompt. Larger dataset bundles,
archives, audio, video, and arbitrary file combinations remain deferred.

When both segmentation mask and source image are present, send the mask first as the primary file
and the source second as reference context. Explicitly prohibit mental compositing: a mask counts as
an overlay only when photographic/radiographic pixels are visible within the mask file itself.

Segmentation masks may use multiple colors and mild within-region variation. The deterministic
pre-check downsamples to at most 512×512, groups pixels into a 16-color adaptive palette, requires at
least two meaningful groups and distinct strong boundaries, limits average palette reconstruction
error to 18, and rejects masks where more than 45% of grouped neighboring pixels change color. This
accepts anti-aliased or lightly shaded semantic masks while rejecting photographs, heavy gradients,
checkerboards, and noisy coloring. Source and mask resolutions may differ; their relative aspect-ratio
difference may be at most 0.5% to accommodate integer resize rounding. Like typed CSV validation,
failure stops the contribution before persistence or hosted-model evaluation.

### Minimal review grouping and rejected repeats

Group contributions into exactly three user-facing tabs: undecided, accepted, and rejected. Accepted
means confirmed paid; an approval remains undecided until payment confirmation. Exact file hashes matching a
rejected contribution are rejected before AI evaluation. Semantic or perceptual duplicate detection
is deferred.

### Minimal delegated review and export

Callers may assign multiple existing accounts by email as per-call moderators. A moderator may only
view review data and make individual decisions; call edits, deletion, funding, payout, moderator
management, bulk AI approval, and export remain caller-only. Each decision stores its reviewer.

The caller can apply all decisive AI recommendations in one action and can download confirmed-paid files
plus a CSV manifest in one ZIP. Rejected and undecided files are excluded from that export. Reviewers
must be able to view pending/rejected data to evaluate it, so preventing them from saving browser-
visible content is not technically enforceable; this MVP provides authorization and export
separation, not DRM.

For strong image deterrence, reviewers never receive original undecided/rejected image bytes. The
server stores a versioned maximum 480×480 JPEG derivative with translucent repeated watermark
bands and contribution-specific labels. The UI uses its distinct URL, disables ordinary
image copy/drag/context-menu actions, sends `no-store` headers, and records the first preview access
per reviewer. Confirmed-paid pages switch to the original. Companion text remains readable without
watermarks. CSV bytes remain hidden before payment and are replaced by validation plus AI assessment.
This lowers image reuse/training
quality but cannot stop OS screenshots or external cameras.

### Two quality tiers

Support `standard` and optional `high` rewards. Avoid configurable weighted scoring systems in the MVP.

Allow 1–100,000 maximum accepted contributions. The original limit of 100 was an unnecessary
UI/backend restriction; the caller remains responsible for funding the resulting maximum escrow
liability.

### Draft-only call changes

Callers may edit or remove only an unfunded draft. Funding submission freezes all terms, and funded calls remain available for escrow and activity history.

### Escrow identifiers survive local resets

Assign each new call an independent random positive 63-bit escrow identifier instead of reusing its
SQLite row ID. The deployed Fuji contract is persistent, while the local demo database may be
cleared; separating the identifiers prevents a reset database from colliding with an older funded
call on-chain.

Use the same separation for payouts: every new contribution receives a persistent random `bytes32`
payout key instead of hashing its reusable SQLite row ID. Existing rows retain their legacy hashed
IDs during the additive migration so already-submitted Fuji payouts still reconcile correctly.
Once a payout transaction hash is recorded, hide the Pay action and poll for confirmation rather
than allowing a duplicate transaction.

## Still to choose

- Nothing required for the hackathon MVP.
