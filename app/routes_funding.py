from __future__ import annotations

from datetime import UTC, datetime

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.blockchain import BlockchainService
from app.call_rules import (
    as_utc,
    required_remaining_liability,
    validate_tx_hash,
)
from app.config import Settings
from app.db import Database
from app.lifecycle import refresh_chain_state
from app.models import (
    CallStatus,
    Contribution,
    ContributionStatus,
    Event,
)
from app.review_service import (
    owned_call,
)
from app.schemas import TopUpTransactionRequest, TransactionRequest
from app.web import get_db, require_user


def register_routes(
    app: FastAPI, app_settings: Settings, database: Database, chain: BlockchainService
) -> None:
    @app.post("/calls/{call_id}/funding-tx")
    def record_funding(
        call_id: int,
        request: Request,
        payload: TransactionRequest,
        db: Session = Depends(get_db),
    ) -> dict[str, str]:
        user = require_user(request, db)
        data_call = owned_call(db, call_id, user)
        validate_tx_hash(payload.tx_hash)
        if data_call.status not in (CallStatus.DRAFT, CallStatus.FUNDING):
            raise HTTPException(status_code=409, detail="Call is not waiting for funding")
        if not user.wallet_address.startswith("0x"):
            raise HTTPException(status_code=409, detail="Link a Fuji wallet before funding")
        sender = chain.transaction_sender(payload.tx_hash) if chain.configured else None
        if chain.configured and sender is None:
            raise HTTPException(status_code=422, detail="Funding transaction was not found on Fuji")
        if sender and sender.lower() != data_call.caller.wallet_address.lower():
            raise HTTPException(
                status_code=409,
                detail="The funding wallet must match the wallet signed in to DataBounty",
            )
        data_call.funding_tx_hash = payload.tx_hash
        data_call.status = CallStatus.FUNDING
        db.add(
            Event(
                call_id=call_id,
                event_type="funding_submitted",
                message="Funding transaction submitted",
                tx_hash=payload.tx_hash,
            )
        )
        db.commit()
        refresh_chain_state(db, data_call, chain)
        return {"status": data_call.status}

    @app.post("/calls/{call_id}/top-up-tx")
    def record_call_top_up(
        call_id: int,
        request: Request,
        payload: TopUpTransactionRequest,
        db: Session = Depends(get_db),
    ) -> dict[str, int]:
        caller = require_user(request, db)
        data_call = owned_call(db, call_id, caller)
        if data_call.status != CallStatus.OPEN or as_utc(data_call.deadline) <= datetime.now(UTC):
            raise HTTPException(
                status_code=409, detail="Only an active call can receive more funding"
            )
        if not 1 <= payload.additional_slots <= 100_000 - data_call.max_acceptances:
            raise HTTPException(status_code=422, detail="Additional contributions are out of range")
        if not chain.configured:
            raise HTTPException(status_code=409, detail="Escrow contract is not configured")
        validate_tx_hash(payload.tx_hash)
        duplicate_tx = db.scalar(select(Event.id).where(Event.tx_hash == payload.tx_hash))
        if duplicate_tx is not None:
            raise HTTPException(status_code=409, detail="This funding transaction was already used")
        if chain.transaction_state(payload.tx_hash).state != "confirmed":
            raise HTTPException(
                status_code=409, detail="Additional funding is not confirmed on Fuji"
            )
        added_amount = payload.additional_slots * data_call.maximum_reward
        escrow_call_id = data_call.escrow_call_id or data_call.id
        if not chain.top_up_matches(
            payload.tx_hash,
            escrow_call_id,
            added_amount,
            data_call.caller.wallet_address,
        ):
            raise HTTPException(
                status_code=409,
                detail="The transaction does not match this call's additional funding",
            )

        paid_count = int(
            db.scalar(
                select(func.count(Contribution.id)).where(
                    Contribution.call_id == call_id,
                    Contribution.status == ContributionStatus.PAID,
                )
            )
            or 0
        )
        new_maximum = data_call.max_acceptances + payload.additional_slots
        required_remaining = required_remaining_liability(
            new_maximum, paid_count, data_call.maximum_reward
        )
        remaining = chain.call_remaining(escrow_call_id, data_call.caller.wallet_address)
        if remaining is None or remaining < required_remaining:
            raise HTTPException(
                status_code=409,
                detail="The confirmed escrow balance is insufficient for this expanded limit",
            )

        data_call.max_acceptances = new_maximum
        db.add(
            Event(
                call_id=call_id,
                event_type="funding_added",
                message=(
                    f"Caller funded {payload.additional_slots} additional acceptance slot(s); "
                    f"maximum is now {new_maximum}"
                ),
                tx_hash=payload.tx_hash,
            )
        )
        db.commit()
        return {"max_acceptances": new_maximum}
