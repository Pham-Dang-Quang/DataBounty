# Implementation Progress

Last updated: 2026-11-11

## Current status

- Phase: Phase 4 — Fuji publication and final two-wallet demo
- State: MVP implementation complete locally; external Fuji deployment pending
- Implementation: Complete except for wallet-owned Fuji publication

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
- `pytest`: 9 passed in 0.37 seconds, including a regression check that viem contract writes are bound to Fuji.
- `node --check` confirms the updated wallet module is syntactically valid.
- `forge test`: 4 passed, including 256 fuzz cases.
- Local Anvil deployment succeeded; token and escrow bytecode deployed and Python getter call matched the contract ABI.
- Real text-model check returned a structured `unsure`/`standard` result with a 61% relevance explanation; the caller remains the decision-maker.
- Test coverage includes auth replay, core contribution/review flow, duplicate/invalid uploads, ownership, amount calculation, and file validation.
- Python tests must run outside the Windows sandbox because its socket restriction blocks asyncio event-loop initialization.

## Runtime configuration

- Product name is `DataBounty` for the demo.
- Text model is `Horizon-Labs/multilingual-zeroshot-small` (Apache-2.0); image model is CLIP for research/demo use.
- Hugging Face execution is opt-in; deterministic fallback keeps manual review usable without model artifacts.
- Fuji contract addresses must be added after deployment.

## Known issues or blockers

- Fuji deployment requires a user-controlled funded Fuji deployer wallet; no private key is available or stored.

## Exact next step

Using a locally controlled funded Fuji wallet, run the command in `contracts/README.md`, copy the emitted token and escrow addresses into `.env`, start the web app, and complete the README’s two-wallet demo sequence. Do not share or commit the deployer private key.
