# DataBounty contracts

These contracts are only for the Fuji/local hackathon demo. `MockRewardToken` has a public faucet and no real value.

## Install dependencies

```powershell
forge install foundry-rs/forge-std --no-git
forge install OpenZeppelin/openzeppelin-contracts --no-git
```

## Test

```powershell
forge test
```

## Deploy to Fuji

Set `AVALANCHE_RPC_URL` and `DEPLOYER_PRIVATE_KEY` in the shell, then run:

```powershell
forge script script/Deploy.s.sol:Deploy --rpc-url fuji --broadcast
```

Copy the emitted token and escrow addresses to the root `.env`. Never commit the deployer key.

