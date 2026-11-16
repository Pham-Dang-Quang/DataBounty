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

Support manual and AI-assisted review. AI returns a recommendation; the caller decides and submits the payout. Fully automatic AI payout is deferred.

### Hosted criteria-aware evaluator

Use `Qwen/Qwen3-VL-8B-Instruct` through a configurable OpenAI-compatible chat-completions API for
both image-text and CSV contributions. This replaces CLIP because a vision-language model can reason
about caller-specific criteria. No checkpoint, CUDA runtime, or local model cache is required.
Uploaded contribution content is sent to the configured provider when API evaluation is enabled.
API failure always becomes an explicit `unsure` result; AI never controls payouts.

### Minimal accounts and community fields

Use email/password sessions and scrypt password hashes. Allow a name, bio, profile image, and one
signature-verified Fuji wallet per account. Multiple-wallet management is deferred because one
transaction wallet completes the hackathon flow with less identity and payout ambiguity.

Calls may contain at most five validated HTTP(S) author/project links. Discussions support top-level
comments and one reply level only; moderation, deletion, voting, and notifications are deferred.

Theme and English/Vietnamese choices are browser-local preferences, not account settings.

### Minimal live evaluation progress

Store a percentage and short stage on each contribution and poll an authenticated JSON endpoint.
This is sufficient for one-process background evaluation; WebSockets, Redis, and Celery remain
outside the MVP.

### Minimal contribution types

Accept either one image with a required text label/description, or one UTF-8 CSV file. The image
text is stored as metadata so the MVP still uploads only one file. Other archives, audio, video,
multiple files, and spreadsheet formats are deferred.

### Minimal review grouping and rejected repeats

Group contributions into undecided, accepted, and rejected tabs. The call-page counter includes only
undecided items; accepted includes awaiting-payout and paid states. Exact file hashes matching a
rejected contribution are rejected before AI evaluation. Semantic or perceptual duplicate detection
is deferred.

### Two quality tiers

Support `standard` and optional `high` rewards. Avoid configurable weighted scoring systems in the MVP.

### Draft-only call changes

Callers may edit or remove only an unfunded draft. Funding submission freezes all terms, and funded calls remain available for escrow and activity history.

### Escrow identifiers survive local resets

Assign each new call an independent random positive 63-bit escrow identifier instead of reusing its
SQLite row ID. The deployed Fuji contract is persistent, while the local demo database may be
cleared; separating the identifiers prevents a reset database from colliding with an older funded
call on-chain.

## Still to choose

- Nothing required for the hackathon MVP.
