# Minimal Architecture

Status: Hackathon MVP

## Components

### FastAPI application

One Python application provides:

- Jinja2-rendered pages;
- small JSON endpoints used by browser JavaScript;
- wallet-signature authentication;
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

A Python adapter accepts the contribution, caller criteria, and data type. It returns validated structured output: recommendation, tier, and explanation. Run it outside the request path with a simple background task if inference is slow.

### Avalanche Fuji

One small escrow contract holds the demo ERC-20 for calls. It records call funding and prevents duplicate or excessive payouts. The browser submits user-authorized transactions; Python reads events and updates the UI.

## Main data flow

```text
Browser -> FastAPI -> SQLite/local uploads -> AI evaluator
   |                                      
   +---------- wallet transaction -> Fuji escrow
```

## Trust boundary

- Files and AI results are off-chain and controlled by the application.
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
- Use generated storage names and never execute uploaded content.
- Use one-time login nonces and short sessions.
- Check ownership on every caller/contributor action.
- Never store wallet private keys.
- Test escrow balance conservation and duplicate payout rejection.

## Later, only if needed

PostgreSQL, object storage, job queues, external model servers, mainnet, automatic payouts, disputes, and production security operations are deferred.
