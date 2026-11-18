// SPDX-License-Identifier: MIT
pragma solidity 0.8.27;

import {Test} from "forge-std/Test.sol";
import {DataBountyEscrow} from "../src/DataBountyEscrow.sol";
import {MockRewardToken} from "../src/MockRewardToken.sol";

contract DataBountyEscrowTest is Test {
    MockRewardToken private token;
    DataBountyEscrow private escrow;
    address private caller = makeAddr("caller");
    address private contributor = makeAddr("contributor");
    uint256 private constant CALL_ID = 7;
    uint256 private constant BUDGET = 5_000_000;
    uint64 private deadline;

    function setUp() public {
        token = new MockRewardToken();
        escrow = new DataBountyEscrow(token);
        deadline = uint64(block.timestamp + 7 days);
        vm.prank(caller);
        token.faucet(BUDGET);
        vm.prank(caller);
        token.approve(address(escrow), BUDGET);
    }

    function testFundAndPayOnce() public {
        _fund();
        bytes32 contributionId = keccak256("1");

        vm.prank(caller);
        escrow.pay(CALL_ID, contributionId, contributor, 2_000_000);

        assertEq(token.balanceOf(contributor), 2_000_000);
        (, uint256 remaining,,) = escrow.calls(CALL_ID);
        assertEq(remaining, 3_000_000);
        assertTrue(escrow.paid(CALL_ID, contributionId));

        vm.expectRevert(DataBountyEscrow.ContributionAlreadyPaid.selector);
        vm.prank(caller);
        escrow.pay(CALL_ID, contributionId, contributor, 1);
    }

    function testRejectsExcessAndUnauthorizedPayouts() public {
        _fund();
        vm.expectRevert(DataBountyEscrow.InvalidPayout.selector);
        vm.prank(caller);
        escrow.pay(CALL_ID, keccak256("1"), contributor, BUDGET + 1);

        vm.expectRevert(DataBountyEscrow.NotCallOwner.selector);
        vm.prank(contributor);
        escrow.pay(CALL_ID, keccak256("2"), contributor, 1);
    }

    function testOwnerCanAddFunding() public {
        _fund();
        uint256 added = 2_000_000;
        vm.prank(caller);
        token.faucet(added);
        vm.prank(caller);
        token.approve(address(escrow), added);

        vm.prank(caller);
        escrow.addFunds(CALL_ID, added);

        (, uint256 remaining,,) = escrow.calls(CALL_ID);
        assertEq(remaining, BUDGET + added);
        assertEq(token.balanceOf(address(escrow)), BUDGET + added);
    }

    function testOnlyOwnerCanAddFunding() public {
        _fund();
        vm.expectRevert(DataBountyEscrow.NotCallOwner.selector);
        vm.prank(contributor);
        escrow.addFunds(CALL_ID, 1);
    }

    function testRefundAfterDeadline() public {
        _fund();
        vm.expectRevert(DataBountyEscrow.RefundTooEarly.selector);
        vm.prank(caller);
        escrow.refund(CALL_ID);

        vm.warp(deadline + 1);
        vm.prank(caller);
        escrow.refund(CALL_ID);

        assertEq(token.balanceOf(caller), BUDGET);
        (, uint256 remaining,,) = escrow.calls(CALL_ID);
        assertEq(remaining, 0);
    }

    function testFuzzPayoutNeverExceedsBudget(uint256 amount) public {
        _fund();
        amount = bound(amount, 1, BUDGET);
        vm.prank(caller);
        escrow.pay(CALL_ID, keccak256("fuzz"), contributor, amount);
        assertEq(token.balanceOf(contributor), amount);
        assertEq(token.balanceOf(address(escrow)), BUDGET - amount);
    }

    function _fund() private {
        vm.prank(caller);
        escrow.fundCall(CALL_ID, BUDGET, deadline);
    }
}

