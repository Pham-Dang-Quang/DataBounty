from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from eth_typing import HexStr
from web3 import Web3
from web3.contract import Contract

from app.config import Settings

ESCROW_ABI = [
    {
        "inputs": [{"name": "callId", "type": "uint256"}],
        "name": "calls",
        "outputs": [
            {"name": "owner", "type": "address"},
            {"name": "remaining", "type": "uint256"},
            {"name": "deadline", "type": "uint64"},
            {"name": "exists", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "callId", "type": "uint256"},
            {"name": "contributionId", "type": "bytes32"},
        ],
        "name": "paid",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]


@dataclass(frozen=True)
class TransactionState:
    state: str
    confirmations: int = 0


class BlockchainService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.web3 = Web3(Web3.HTTPProvider(settings.avalanche_rpc_url))

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.escrow_contract_address
            and self.settings.token_contract_address
            and Web3.is_address(self.settings.escrow_contract_address)
        )

    @property
    def contract(self) -> Contract:
        if not self.configured:
            raise RuntimeError("Escrow contract is not configured")
        return self.web3.eth.contract(
            address=Web3.to_checksum_address(self.settings.escrow_contract_address),
            abi=ESCROW_ABI,
        )

    def transaction_state(self, tx_hash: str) -> TransactionState:
        try:
            receipt = self.web3.eth.get_transaction_receipt(cast(HexStr, tx_hash))
        except Exception:
            return TransactionState("pending")
        if receipt["status"] != 1:
            return TransactionState("failed")
        confirmations = max(0, self.web3.eth.block_number - receipt["blockNumber"] + 1)
        if confirmations < self.settings.required_confirmations:
            return TransactionState("pending", confirmations)
        return TransactionState("confirmed", confirmations)

    def transaction_sender(self, tx_hash: str) -> str | None:
        try:
            transaction = self.web3.eth.get_transaction(cast(HexStr, tx_hash))
        except Exception:
            return None
        sender = transaction.get("from")
        return Web3.to_checksum_address(sender) if sender else None

    def call_is_funded(self, call_id: int, minimum_balance: int, owner: str) -> bool:
        chain_owner, remaining, _deadline, exists = self.contract.functions.calls(call_id).call()
        return (
            bool(exists)
            and Web3.to_checksum_address(chain_owner) == Web3.to_checksum_address(owner)
            and int(remaining) >= minimum_balance
        )

    def contribution_is_paid(self, call_id: int, contribution_id: int) -> bool:
        key = Web3.keccak(text=str(contribution_id))
        return bool(self.contract.functions.paid(call_id, key).call())
