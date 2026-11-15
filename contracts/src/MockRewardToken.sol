// SPDX-License-Identifier: MIT
pragma solidity 0.8.27;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/// @notice Permissionless test token for Fuji/local demos. It has no real value.
contract MockRewardToken is ERC20 {
    constructor() ERC20("DataBounty Test Token", "DBT") {}

    function decimals() public pure override returns (uint8) {
        return 6;
    }

    function faucet(uint256 amount) external {
        _mint(msg.sender, amount);
    }
}

