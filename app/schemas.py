from pydantic import BaseModel


class ChallengeRequest(BaseModel):
    address: str


class VerifyRequest(BaseModel):
    message: str
    signature: str


class TransactionRequest(BaseModel):
    tx_hash: str


class TopUpTransactionRequest(TransactionRequest):
    additional_slots: int
