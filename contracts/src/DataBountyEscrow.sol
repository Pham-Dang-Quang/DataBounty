// SPDX-License-Identifier: MIT
pragma solidity 0.8.27;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @notice Minimal single-token escrow for the DataBounty hackathon demo.
contract DataBountyEscrow is ReentrancyGuard {
    using SafeERC20 for IERC20;

    struct Call {
        address owner;
        uint256 remaining;
        uint64 deadline;
        bool exists;
    }

    IERC20 public immutable rewardToken;
    mapping(uint256 callId => Call dataCall) public calls;
    mapping(uint256 callId => mapping(bytes32 contributionId => bool wasPaid)) public paid;

    error CallAlreadyExists();
    error CallNotFound();
    error InvalidCall();
    error InvalidPayout();
    error NotCallOwner();
    error ContributionAlreadyPaid();
    error RefundTooEarly();
    error TokenTransferMismatch();

    event CallFunded(uint256 indexed callId, address indexed owner, uint256 amount, uint64 deadline);
    event ContributionPaid(
        uint256 indexed callId, bytes32 indexed contributionId, address indexed recipient, uint256 amount
    );
    event CallRefunded(uint256 indexed callId, address indexed owner, uint256 amount);

    constructor(IERC20 token) {
        if (address(token) == address(0)) revert InvalidCall();
        rewardToken = token;
    }

    function fundCall(uint256 callId, uint256 budget, uint64 deadline) external nonReentrant {
        if (calls[callId].exists) revert CallAlreadyExists();
        if (budget == 0 || deadline <= block.timestamp) revert InvalidCall();

        calls[callId] = Call({owner: msg.sender, remaining: budget, deadline: deadline, exists: true});

        uint256 balanceBefore = rewardToken.balanceOf(address(this));
        rewardToken.safeTransferFrom(msg.sender, address(this), budget);
        if (rewardToken.balanceOf(address(this)) - balanceBefore != budget) {
            revert TokenTransferMismatch();
        }
        emit CallFunded(callId, msg.sender, budget, deadline);
    }

    function pay(uint256 callId, bytes32 contributionId, address recipient, uint256 amount) external nonReentrant {
        Call storage dataCall = calls[callId];
        if (!dataCall.exists) revert CallNotFound();
        if (msg.sender != dataCall.owner) revert NotCallOwner();
        if (recipient == address(0) || amount == 0 || amount > dataCall.remaining) {
            revert InvalidPayout();
        }
        if (paid[callId][contributionId]) revert ContributionAlreadyPaid();

        paid[callId][contributionId] = true;
        dataCall.remaining -= amount;
        rewardToken.safeTransfer(recipient, amount);
        emit ContributionPaid(callId, contributionId, recipient, amount);
    }

    function refund(uint256 callId) external nonReentrant {
        Call storage dataCall = calls[callId];
        if (!dataCall.exists) revert CallNotFound();
        if (msg.sender != dataCall.owner) revert NotCallOwner();
        if (block.timestamp <= dataCall.deadline) revert RefundTooEarly();

        uint256 amount = dataCall.remaining;
        if (amount == 0) revert InvalidPayout();
        dataCall.remaining = 0;
        rewardToken.safeTransfer(dataCall.owner, amount);
        emit CallRefunded(callId, dataCall.owner, amount);
    }
}

