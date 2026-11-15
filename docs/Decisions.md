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

### Demo evaluators

Use the Apache-2.0 `Horizon-Labs/multilingual-zeroshot-small` text model and CLIP image model behind
cached local adapters. Models are optional at runtime, never control payouts, and fall back to an
explicit `unsure` result. CLIP is a hackathon/research choice that must be benchmarked or replaced
before real deployment.

### Minimal live evaluation progress

Store a percentage and short stage on each contribution and poll an authenticated JSON endpoint.
This is sufficient for one-process background evaluation; WebSockets, Redis, and Celery remain
outside the MVP.

### Minimal contribution types

Accept one image or UTF-8 text file per contribution. Multiple files, archives, audio, video, and tables are deferred.

### Two quality tiers

Support `standard` and optional `high` rewards. Avoid configurable weighted scoring systems in the MVP.

### Draft-only call changes

Callers may edit or remove only an unfunded draft. Funding submission freezes all terms, and funded calls remain available for escrow and activity history.

## Still to choose

- Nothing required for the hackathon MVP.
