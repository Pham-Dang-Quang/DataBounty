# Implementation Progress

Last updated: 2026-11-15

## Current status

- Phase: Phase 4 — final two-wallet demo
- State: MVP deployed to Fuji; funding verified end to end
- Implementation: Core MVP complete; contribution and payout demo remains

## Completed

- Created the locked Python environment and minimal FastAPI/Jinja2 application.
- Implemented replay-safe wallet challenge/signature login.
- Implemented call creation, listing, ownership checks, and lifecycle states.
- Implemented private one-file image/text uploads, validation, and duplicate rejection.
- Implemented manual and AI-assisted review, caller decisions, tiers, and payout-pending state.
- Added lazy Hugging Face text/image adapters with explicit manual-review fallback.
- Added responsive server-rendered pages and vanilla JavaScript wallet interactions.
- Added Python-side Fuji transaction confirmation and escrow-state readers.
- Added eight focused integration/unit tests.
- Implemented the minimal OpenZeppelin-based escrow and permissionless Fuji demo token.
- Added funding, caller-only payout, duplicate prevention, balance conservation, and deadline refund.
- Added four Foundry tests including a 256-run fuzz payout invariant.
- Verified the deployment script on a disposable local Anvil chain (chain ID 43113).
- Verified the Python `web3.py` ABI against the locally deployed escrow.
- Installed Python 3.13 optional AI dependencies and ran a real synthetic inference with the selected text model.
- Added a sample call and contribution for the demo.
- Bound the viem wallet client and all contract writes explicitly to Avalanche Fuji; Core now receives a Fuji switch request when connected to another chain.
- Added caller-only editing and removal of unfunded draft calls; funding submission freezes both operations.
- Added a caller-facing demo-token faucet button that mints exactly the call budget and waits for Fuji confirmation.
- Added a wallet-script cache version so newly deployed wallet controls cannot load with stale JavaScript.
- Serialized ERC-20 approval and escrow funding, then assigned the current pending Fuji nonce to prevent Core nonce reuse.
- Enforced that Core's active transaction account and the Fuji funding sender match the wallet signed in to DataBounty.
- Reconciled call 1 to its confirmed Fuji funder and recorded the successful funding event; the call is now open with 45 DBT escrowed.
- Enabled the Hugging Face evaluators, cached model pipelines per process, and completed the required three-way `accept`/`unsure`/`reject` classification thresholds.
- Added matching and unrelated synthetic text contributions plus documented traffic-sign image dataset suggestions.
- Added persistent evaluation percentage/stage fields, an authenticated polling endpoint, and a responsive live progress bar.
- Attempted Qwen3-VL replacement, then stopped its 4.3 GB download and restored CLIP at the owner's request.
- Added cross-platform fresh-clone deployment, Fuji contract, and AI configuration instructions to `README.md`.
- Added explicit `MODEL_CACHE_DIR`, `HF_HOME`, `HF_HUB_CACHE`, `TRANSFORMERS_CACHE`, `TORCH_HOME`,
  and `TMPDIR` configuration before lazy AI-library imports; both evaluators also receive the Hub
  cache directly.

## Files changed

- `.env.example`, `.gitignore`, `pyproject.toml`, `uv.lock`
- `app/` Python, templates, CSS, and wallet JavaScript
- `tests/`
- `contracts/` sources, tests, deployment script, and Foundry configuration
- `demo/`
- `README.md`
- `docs/progress.md`

## Verification

- Python 3.13.16, Ruff formatting/lint, and mypy all pass.
- `pytest`: 11 passed in 0.97 seconds, including rendered controls, ownership, and lifecycle tests for call editing/removal.
- `node --check` confirms the updated wallet module is syntactically valid.
- The call-page faucet flow is covered by a focused frontend asset test.
- Focused faucet and call-management verification: `4 passed`; wallet JavaScript syntax check passed.
- Cache repair verification: `2 passed`; the running server returned the versioned script with the faucet handler (`HTTP 200`).
- Nonce repair verification: `5 passed`; JavaScript syntax passed and the running server returned wallet script v3 with approval waiting and pending-nonce logic.
- Wallet consistency repair: Ruff and mypy passed, `10 passed`, JavaScript syntax passed, and live Fuji transaction `0xaa43…f506` opened call 1.
- AI verification: full Ruff and mypy checks passed; `16 passed`.
- Live text inference scored the matching sample at 89% (`accept/high`) and the unrelated sample at 10% (`reject/standard`).
- Progress-interface verification before the rollback: Ruff and mypy passed, both JavaScript files passed syntax checks, and `19 passed`.
- Existing SQLite database was migrated additively with `evaluation_progress` and `evaluation_stage`.
- Rollback verification: Ruff and mypy pass, both JavaScript syntax checks pass, `19 passed`, and live CLIP inference returned 40% (`unsure/standard`).
- The partial Qwen cache (1.5 GB) and Qwen-only `torchvision` dependency were removed.
- Configurable model-cache verification: Ruff and mypy pass, both JavaScript syntax checks pass, and `21 passed`, including explicit Transformers `cache_dir` routing.
- Process-level cache verification exported the configured absolute Hugging Face, Transformers,
  PyTorch, and cross-OS temporary paths from a fresh settings load.
- `forge test`: 4 passed, including 256 fuzz cases.
- Local Anvil deployment succeeded; token and escrow bytecode deployed and Python getter call matched the contract ABI.
- Real text-model check returned a structured `unsure`/`standard` result with a 61% relevance explanation; the caller remains the decision-maker.
- Test coverage includes auth replay, core contribution/review flow, duplicate/invalid uploads, ownership, amount calculation, and file validation.
- Python tests must run outside the Windows sandbox because its socket restriction blocks asyncio event-loop initialization.

## Runtime configuration

- Product name is `DataBounty` for the demo.
- AI implementation status: text and image Hugging Face adapters are implemented; a real text-model inference has been verified.
- Current runtime status: `ENABLE_HF_MODELS=true`; model loading is cached per process and failures still produce the explicit deterministic `unsure` fallback.
- Text model is `Horizon-Labs/multilingual-zeroshot-small` (Apache-2.0); image model is CLIP for research/demo use.
- Model checkpoints and temporary files default to ignored `./models-cache` subdirectories and may
  be redirected independently through `.env`.
- AI recommendations never trigger payment; the caller makes the final decision.
- Fuji token and escrow addresses are configured; live funding for call 1 is confirmed.

## Known issues or blockers

- None for the funding flow. A pre-recovery database copy is stored at `data/databounty.pre-funding-recovery-20261115.db`.

## Exact next step

Complete the two-wallet contribution and payout demo using the restored CLIP evaluator and live progress interface.
