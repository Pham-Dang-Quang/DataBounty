# DataBounty

DataBounty is a minimal hackathon application for requesting image-text pairs, typed CSV files, or
image-segmentation-text packages, receiving
an AI review recommendation, and rewarding accepted contributors through an Avalanche Fuji escrow.

## What works

- Email/password signup and signin with a basic profile
- One signature-linked Fuji wallet per account
- Create image-text, typed CSV, or image-segmentation-text data calls
- Deterministic CSV schema/type/row validation before hosted AI assessment
- Image+Segmentation, Segmentation+Text, or Image+Segmentation+Text packages
- Private one-file contributions with validation and duplicate detection
- Manual or AI-assisted review
- Review-only moderators assigned by account email, with reviewer attribution
- Bulk application of decisive AI recommendations and reconsideration of rejected data
- Caller-only confirmed-paid-data ZIP export with a CSV manifest
- Standard and high reward tiers
- Caller-approved Fuji escrow payouts
- Responsive server-rendered UI
- Light/dark themes, English/Vietnamese switching, call discussions, and author links

AI never makes an unquestionable decision: the caller or an assigned moderator approves review
outcomes, and only the caller controls payouts. The application does not hold private keys or fiat.

The accepted-data ZIP includes only contributions with a confirmed payout; an approved contribution
remains **Undecided** until that confirmation. Callers and assigned
moderators see only reduced, recompressed, repeatedly watermarked raster previews while reviewing
images. The application stores a separate versioned derivative and switches back to the original
only after payout confirmation. Companion text remains readable and unwatermarked. The UI blocks
ordinary image copy, drag, and context-menu actions and logs protected image access. A web
application still cannot prevent OS screenshots or an external camera.

CSV contents are not shown or served to callers/moderators before confirmed payment. They review
the deterministic validation summary and the hosted model's detailed assessment instead.

## Deploy from a fresh clone

Install Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), Foundry, and the Core wallet on
Windows, macOS, or Linux. Core must use Avalanche Fuji (chain ID `43113`). No local GPU, CUDA,
PyTorch, or model download is required.

### 1. Install the application

From the repository root:

Windows PowerShell:

```powershell
Copy-Item .env.example .env
uv sync
```

macOS/Linux shell:

```bash
cp .env.example .env
uv sync
```

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
ENABLE_AI_API=true
AI_API_BASE_URL=https://openrouter.ai/api/v1
AI_API_KEY=replace-with-provider-key
AI_MODEL=qwen/qwen3-vl-8b-instruct
AI_API_TIMEOUT_SECONDS=60
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

An existing wallet-only user from an earlier DataBounty version can choose **Recover with wallet
signature** on the sign-in page, then add an email and password in Settings. New users should use
normal email signup and link one Fuji wallet from Settings.

## Configure AI evaluation

The default configuration calls Qwen3-VL-8B-Instruct through OpenRouter's OpenAI-compatible
`/chat/completions` API for all supported types. Create an OpenRouter key, put it in
`.env`, and set `ENABLE_AI_API=true`. Do not commit the key. Another compatible provider can be used
by changing `AI_API_BASE_URL` and `AI_MODEL` to that provider's values.

This avoids all local checkpoint, CUDA, VRAM, and model-cache requirements. When enabled,
contribution content and caller criteria are sent to the configured provider, so use only a provider
whose privacy and retention terms are acceptable for the demo. The model receives explicit
instructions to treat contributions as untrusted data, and its JSON result is validated before it is
stored.

Set `ENABLE_AI_API=false` to disable external inference. Missing configuration, timeout, HTTP error,
or invalid model output produces an explicit `unsure` recommendation and leaves the final decision
with the caller. The live progress bar shows preparation, API waiting, and result validation stages.

## Test Python

```text
uv run ruff check app tests
uv run pytest
```

Some restricted Windows sandboxes block Python event-loop socket initialization; run the tests in a normal terminal if they appear to hang before the first test.

Contract testing and deployment commands are in the fresh-clone instructions above and summarized
again in `contracts/README.md`.

## Demo sequence

1. Sign up as the caller, configure the profile, and link a Core wallet on Fuji.
2. Mint demo tokens from the configured mock token contract.
3. Fund the call; refresh after confirmation to open it.
4. Sign up as a second account, link its Fuji wallet, and upload one matching image-text pair.
5. Sign back into the caller account, inspect the AI recommendation, and accept a tier.
6. Optionally add registered moderator emails, apply decisive AI recommendations in bulk, and
   download the accepted-data ZIP.
7. Submit the payout and refresh after confirmation.
8. Show the confirmed transaction and contributor token balance in the wallet/explorer.

To expand a funded call, deploy the current escrow source (older deployments do not contain
`addFunds`), update `ESCROW_CONTRACT_ADDRESS`, and restart the app. The caller can then select a
number of additional acceptance slots, approve the calculated DBT amount, and add it to escrow.
Existing calls tied to an older immutable escrow cannot be topped up in place.

