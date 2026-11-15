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

## Deploy from a fresh clone

Install Python 3.12 or 3.13, [uv](https://docs.astral.sh/uv/), Foundry, and the Core wallet on
Windows, macOS, or Linux.
Core must use Avalanche Fuji (chain ID `43113`). Python 3.14 can run the web application only
with the deterministic fallback because the optional PyTorch models target Python 3.12/3.13.

### 1. Install the application

From the repository root:

Windows PowerShell:

```powershell
Copy-Item .env.example .env
uv sync --extra ai
```

macOS/Linux shell:

```bash
cp .env.example .env
uv sync --extra ai
```

Use `uv sync` without `--extra ai` only when AI inference will remain disabled.

### 2. Test and deploy the Fuji contracts

The deployer needs Fuji test AVAX for gas. Never paste a mainnet key, seed phrase, or private key
into the application, source code, or committed files.

Install and test the contracts on every OS:

```text
cd contracts
forge install foundry-rs/forge-std --no-git
forge install OpenZeppelin/openzeppelin-contracts --no-git
forge test
cd ..
```

Deploy from Windows PowerShell:

```powershell
Set-Location contracts
$env:AVALANCHE_RPC_URL = "https://api.avax-test.network/ext/bc/C/rpc"
$env:DEPLOYER_PRIVATE_KEY = "YOUR_FUJI_TEST_WALLET_PRIVATE_KEY"
forge script script/Deploy.s.sol:Deploy --rpc-url fuji --broadcast
Remove-Item Env:DEPLOYER_PRIVATE_KEY
Set-Location ..
```

Deploy from a macOS/Linux shell:

```bash
cd contracts
export AVALANCHE_RPC_URL="https://api.avax-test.network/ext/bc/C/rpc"
export DEPLOYER_PRIVATE_KEY="YOUR_FUJI_TEST_WALLET_PRIVATE_KEY"
forge script script/Deploy.s.sol:Deploy --rpc-url fuji --broadcast
unset DEPLOYER_PRIVATE_KEY
cd ..
```

Copy the emitted `MockRewardToken` and `DataBountyEscrow` addresses into `.env` as
`TOKEN_CONTRACT_ADDRESS` and `ESCROW_CONTRACT_ADDRESS`. The included addresses may be reused only
while those demo contracts remain available.

### 3. Configure the application

At minimum, review these `.env` values:

```dotenv
SECRET_KEY=replace-with-a-random-local-secret
AVALANCHE_RPC_URL=https://api.avax-test.network/ext/bc/C/rpc
CHAIN_ID=43113
TOKEN_CONTRACT_ADDRESS=0x...
ESCROW_CONTRACT_ADDRESS=0x...
ENABLE_HF_MODELS=true
TEXT_MODEL=Horizon-Labs/multilingual-zeroshot-small
IMAGE_MODEL=openai/clip-vit-base-patch32
```

Generate a local session secret with:

```text
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Do not commit `.env`; it is ignored by Git.

### 4. Start the web application

```text
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. SQLite tables and the private upload directory are created
automatically. For local development, add `--reload` to the command.

## Configure AI evaluation

Set `ENABLE_HF_MODELS=true` and install `uv sync --extra ai` to run both evaluators locally.
Hugging Face downloads model artifacts on the first evaluation and caches them for later runs.
Contributed files are processed locally and are not sent to an inference API. The live progress bar
shows model-loading and evaluation stages.

Set `ENABLE_HF_MODELS=false` to avoid model downloads. If a configured model is unavailable or
fails, the contribution remains reviewable and receives an explicit `unsure` fallback instead of
being silently accepted or rejected.

The default text evaluator is the Apache-2.0 `Horizon-Labs/multilingual-zeroshot-small`. The image
evaluator is CLIP and should be treated as a hackathon/research demonstration. The contribution
page shows coarse live progress while background evaluation runs. Benchmark or replace either
model before any real deployment.

## Test Python

```text
uv run ruff check app tests
uv run pytest
```

Some restricted Windows sandboxes block Python event-loop socket initialization; run the tests in a normal terminal if they appear to hang before the first test.

Contract testing and deployment commands are in the fresh-clone instructions above and summarized
again in `contracts/README.md`.

## Demo sequence

1. Connect the caller wallet and create a call.
2. Mint demo tokens from the configured mock token contract.
3. Fund the call; refresh after confirmation to open it.
4. Sign in with a second wallet and upload one matching file.
5. Return to the caller wallet, inspect the AI recommendation, and accept a tier.
6. Submit the payout and refresh after confirmation.
7. Show the confirmed transaction and contributor token balance in the wallet/explorer.

