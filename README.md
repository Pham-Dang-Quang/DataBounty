# DataBounty

DataBounty is a minimal hackathon application for requesting image or text data, receiving an AI review recommendation, and rewarding accepted contributors through an Avalanche Fuji escrow.

## What works

- Wallet-signature login
- Create image or text data calls
- Private one-file contributions with validation and duplicate detection
- Manual or AI-assisted review
- Standard and high reward tiers
- Caller-approved Fuji escrow payouts
- Responsive server-rendered UI

The caller always makes the final decision. The application does not hold private keys or fiat.

## Run the web application

Requirements: Python 3.12 or 3.13 for optional PyTorch models; Python 3.14 works with the deterministic manual-review fallback.

```powershell
Copy-Item .env.example .env
uv sync
uv run uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. For wallet transactions, configure the deployed Fuji token and escrow addresses in `.env`.

## Enable Hugging Face evaluation

On Python 3.12/3.13:

```powershell
uv sync --extra ai
```

Then set `ENABLE_HF_MODELS=true`. Model artifacts download on first use. If a model is unavailable or fails, the contribution remains reviewable and shows an explicit `unsure` fallback instead of silently accepting or rejecting it.

The default text evaluator is the Apache-2.0 `Horizon-Labs/multilingual-zeroshot-small`. The image evaluator is CLIP and should be treated as a hackathon/research demonstration; benchmark or replace either model before any real deployment.

## Test Python

```powershell
uv run ruff check app tests
uv run pytest
```

Some restricted Windows sandboxes block Python event-loop socket initialization; run the tests in a normal terminal if they appear to hang before the first test.

## Test contracts

The repository-local Foundry binary used during development is ignored by Git. With Foundry installed:

```powershell
Set-Location contracts
forge install foundry-rs/forge-std --no-git
forge install OpenZeppelin/openzeppelin-contracts --no-git
forge test
```

See `contracts/README.md` for the Fuji deployment command. Deployment requires a funded Fuji wallet; never commit its key.

## Demo sequence

1. Connect the caller wallet and create a call.
2. Mint demo tokens from the configured mock token contract.
3. Fund the call; refresh after confirmation to open it.
4. Sign in with a second wallet and upload one matching file.
5. Return to the caller wallet, inspect the AI recommendation, and accept a tier.
6. Submit the payout and refresh after confirmation.
7. Show the confirmed transaction and contributor token balance in the wallet/explorer.

