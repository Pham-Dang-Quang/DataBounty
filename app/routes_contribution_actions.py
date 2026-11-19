from __future__ import annotations

from fastapi import (
    Depends,
    FastAPI,
    Form,
    HTTPException,
    Request,
)
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.blockchain import BlockchainService
from app.call_rules import (
    validate_tx_hash,
)
from app.config import Settings
from app.db import Database
from app.lifecycle import refresh_payout_state
from app.models import (
    Contribution,
    ContributionStatus,
    Event,
)
from app.review_service import (
    apply_contribution_decision,
    can_review_call,
)
from app.schemas import TransactionRequest
from app.web import get_db, require_user


def register_routes(
    app: FastAPI, app_settings: Settings, database: Database, chain: BlockchainService
) -> None:
    @app.get("/api/contributions/{contribution_id}/evaluation")
    def evaluation_status(
        contribution_id: int, request: Request, db: Session = Depends(get_db)
    ) -> dict[str, str | int | None]:
        user = require_user(request, db)
        contribution = db.scalar(
            select(Contribution)
            .options(selectinload(Contribution.data_call))
            .where(Contribution.id == contribution_id)
        )
        if contribution is None:
            raise HTTPException(status_code=404, detail="Contribution not found")
        if user.id != contribution.contributor_id and not can_review_call(
            db, contribution.data_call, user
        ):
            raise HTTPException(status_code=403, detail="Not allowed to view this evaluation")
        return {
            "status": str(contribution.status),
            "progress": max(0, min(100, contribution.evaluation_progress)),
            "stage": contribution.evaluation_stage,
            "recommendation": contribution.ai_recommendation,
        }

    @app.post("/contributions/{contribution_id}/decision")
    def decide_contribution(
        contribution_id: int,
        request: Request,
        decision: str = Form(),
        tier: str = Form("standard"),
        db: Session = Depends(get_db),
    ) -> RedirectResponse:
        user = require_user(request, db)
        contribution = db.scalar(
            select(Contribution)
            .options(selectinload(Contribution.data_call))
            .where(Contribution.id == contribution_id)
        )
        if contribution is None:
            raise HTTPException(status_code=404, detail="Contribution not found")
        if not can_review_call(db, contribution.data_call, user):
            raise HTTPException(status_code=403, detail="Only the caller or a moderator can decide")
        apply_contribution_decision(db, contribution, user, decision, tier)
        db.commit()
        return RedirectResponse(f"/contributions/{contribution.id}", status_code=303)

    @app.post("/contributions/{contribution_id}/payout-tx")
    def record_payout(
        contribution_id: int,
        request: Request,
        payload: TransactionRequest,
        db: Session = Depends(get_db),
    ) -> dict[str, str]:
        user = require_user(request, db)
        contribution = db.scalar(
            select(Contribution)
            .options(selectinload(Contribution.data_call))
            .where(Contribution.id == contribution_id)
        )
        if contribution is None:
            raise HTTPException(status_code=404, detail="Contribution not found")
        if contribution.data_call.caller_id != user.id:
            raise HTTPException(status_code=403, detail="Only the caller can submit payout")
        if contribution.status != ContributionStatus.AWAITING_PAYOUT:
            raise HTTPException(status_code=409, detail="Contribution is not awaiting payout")
        validate_tx_hash(payload.tx_hash)
        contribution.payout_tx_hash = payload.tx_hash
        db.add(
            Event(
                call_id=contribution.call_id,
                contribution_id=contribution.id,
                event_type="payout_submitted",
                message="Payout transaction submitted",
                tx_hash=payload.tx_hash,
            )
        )
        db.commit()
        refresh_payout_state(db, contribution, chain)
        return {"status": contribution.status}
