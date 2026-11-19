# Minimal Architecture

Status: Hackathon MVP

## Components

### FastAPI application

One Python application provides:

- Jinja2-rendered pages;
- small JSON endpoints used by browser JavaScript;
- email/password sessions and signature-based wallet linking;
- data-call and contribution logic;
- upload validation;
- AI evaluation;
- Avalanche event reads.

Keep code separated into small modules, but deploy it as one application.

`app/main.py` only assembles the application. Route modules are grouped by user flow (accounts,
calls, community, funding, submissions, review, and contribution access/actions). Shared business
rules live in small modules for call rules, upload validation, evaluation, preview generation,
review decisions, and chain-state lifecycle updates. Every Python source file in `app/` stays at or
below roughly 300 lines so the complete request path remains easy to follow.

### Browser

Use HTML, CSS, and vanilla JavaScript. `viem` handles wallet connection, signatures, funding, and payout transactions. No SPA framework is needed.

### SQLite and local files

SQLite stores users, calls, per-call moderator assignments, contributions, reviewer attribution,
AI results, and transaction references. Uploaded files live outside the public static directory
under opaque generated names.

### AI evaluator

A Python adapter sends the applicable image/mask/CSV, companion text, caller criteria, deterministic
validation summary, and detailed assessment prompt to the configured
OpenAI-compatible API using `Qwen/Qwen3-VL-8B-Instruct`. It validates the returned recommendation,
tier, and explanation. Run it outside the request path with a simple background task.

For two-image segmentation packages, the mask is sent first as the primary artifact and the source
image second as context only. The prompt states that they are separate files and that overlay status
must be judged only from pixels inside the mask, preventing the model from mentally compositing them.

Evaluation progress and its current stage are stored on the contribution. The contribution page
polls one authenticated JSON endpoint while evaluation runs; no WebSocket or job-queue service is
needed for the MVP.

No local checkpoint or GPU runtime is used. If the API is unavailable, evaluation becomes `unsure`
and remains available for manual review.

### Avalanche Fuji

One small escrow contract holds the demo ERC-20 for calls. It records initial and additional call
funding and prevents duplicate or excessive payouts. The browser submits user-authorized
transactions; Python verifies confirmed balances and updates the UI.

## Main data flow

```text
Browser -> FastAPI -> SQLite/local uploads -> hosted AI API
   |                                      
   +---------- wallet transaction -> Fuji escrow
```

## Trust boundary

- Files and AI results are off-chain and controlled by the application.
- When AI review is enabled, contribution content is disclosed to the configured API provider.
- Funds are held and transferred by the escrow contract.
- The caller controls reviewer membership, bulk AI approval, export, and payouts. Assigned
  moderators may make individual review decisions.
- The accepted ZIP is caller-only, contains confirmed-paid data, and excludes rejected and
  undecided data, including approved data whose payment is not confirmed. Authorized review display
  cannot prevent a reviewer from saving browser-visible content.
- Undecided/rejected images use a versioned derivative stored privately after server-side
  downscaling, recompression, and repeated watermarking. Confirmed-paid pages switch to the original.
  Companion text stays readable. CSV bytes remain hidden from reviewers until confirmed payment;
  responses use `no-store` headers.
- The hackathon app is a demonstration, not a production custody or compliance system.

## Contract responsibilities

The contract should only:

- create/register a funded call;
- track remaining reward balance;
- let only the call owner add funding to an existing call;
- pay a persistent random contribution key once to a recipient;
- reject unauthorized, duplicate, or excessive payouts;
- return unused funds after the deadline;
- emit initial funding, added funding, payout, and refund events.

Do not put uploads, AI logic, criteria interpretation, user profiles, or general application state in Solidity.

## Minimal security

- Validate upload extension, detected type, size, and UTF-8/image readability.
- Validate image readability and required component combinations. Validate CSV encoding, delimiter,
  headers, typed values, row limits, extra/missing rules, and optional uniqueness before AI.
- Use generated storage names and never execute uploaded content.
- Hash passwords with scrypt, use short sessions, and use one-time nonces for wallet linking.
- Check caller, moderator, or contributor authorization on every private action.
- Never store wallet private keys.
- Test escrow balance conservation and duplicate payout rejection.

## Later, only if needed

PostgreSQL, object storage, job queues, local GPU inference, mainnet, automatic payouts, disputes,
multiple wallets per account, and production security operations are deferred.
