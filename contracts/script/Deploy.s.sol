// SPDX-License-Identifier: MIT
pragma solidity 0.8.27;

import {Script} from "forge-std/Script.sol";
import {DataBountyEscrow} from "../src/DataBountyEscrow.sol";
import {MockRewardToken} from "../src/MockRewardToken.sol";

contract Deploy is Script {
    function run() external returns (MockRewardToken token, DataBountyEscrow escrow) {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        vm.startBroadcast(deployerKey);
        token = new MockRewardToken();
        escrow = new DataBountyEscrow(token);
        token.faucet(1_000_000 * 10 ** token.decimals());
        vm.stopBroadcast();
    }
}

