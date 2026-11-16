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

### Browser

Use HTML, CSS, and vanilla JavaScript. `viem` handles wallet connection, signatures, funding, and payout transactions. No SPA framework is needed.

### SQLite and local files

SQLite stores users, calls, contributions, AI results, and transaction references. Uploaded files live outside the public static directory under opaque generated names.

### AI evaluator

A Python adapter sends the contribution, image companion text when present, caller criteria, and data type to the configured
OpenAI-compatible API using `Qwen/Qwen3-VL-8B-Instruct`. It validates the returned recommendation,
tier, and explanation. Run it outside the request path with a simple background task.

Evaluation progress and its current stage are stored on the contribution. The contribution page
polls one authenticated JSON endpoint while evaluation runs; no WebSocket or job-queue service is
needed for the MVP.

No local checkpoint or GPU runtime is used. If the API is unavailable, evaluation becomes `unsure`
and remains available for manual review.

### Avalanche Fuji

One small escrow contract holds the demo ERC-20 for calls. It records call funding and prevents duplicate or excessive payouts. The browser submits user-authorized transactions; Python reads events and updates the UI.

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
- The caller remains responsible for the final acceptance decision.
- The hackathon app is a demonstration, not a production custody or compliance system.

## Contract responsibilities

The contract should only:

- create/register a funded call;
- track remaining reward balance;
- pay a contribution ID once to a recipient;
- reject unauthorized, duplicate, or excessive payouts;
- return unused funds after the deadline;
- emit funding, payout, and refund events.

Do not put uploads, AI logic, criteria interpretation, user profiles, or general application state in Solidity.

## Minimal security

- Validate upload extension, detected type, size, and UTF-8/image readability.
- Validate required image companion text and CSV headers/row widths.
- Use generated storage names and never execute uploaded content.
- Hash passwords with scrypt, use short sessions, and use one-time nonces for wallet linking.
- Check ownership on every caller/contributor action.
- Never store wallet private keys.
- Test escrow balance conservation and duplicate payout rejection.

## Later, only if needed

PostgreSQL, object storage, job queues, local GPU inference, mainnet, automatic payouts, disputes,
multiple wallets per account, and production security operations are deferred.
