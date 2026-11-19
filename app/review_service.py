from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    CallModerator,
    CallStatus,
    Contribution,
    ContributionStatus,
    DataCall,
    Event,
    User,
    utcnow,
)


def owned_call(db: Session, call_id: int, user: User) -> DataCall:
    data_call = db.get(DataCall, call_id)
    if data_call is None:
        raise HTTPException(status_code=404, detail="Call not found")
    if data_call.caller_id != user.id:
        raise HTTPException(status_code=403, detail="Only the caller can perform this action")
    return data_call


def can_review_call(db: Session, data_call: DataCall, user: User) -> bool:
    if data_call.caller_id == user.id:
        return True
    moderator_id = db.scalar(
        select(CallModerator.id).where(
            CallModerator.call_id == data_call.id,
            CallModerator.user_id == user.id,
        )
    )
    return moderator_id is not None


def reviewable_call(db: Session, call_id: int, user: User) -> DataCall:
    data_call = db.get(DataCall, call_id)
    if data_call is None:
        raise HTTPException(status_code=404, detail="Call not found")
    if not can_review_call(db, data_call, user):
        raise HTTPException(status_code=403, detail="Only the caller or a moderator can review")
    return data_call


def editable_draft(db: Session, call_id: int, user: User) -> DataCall:
    data_call = owned_call(db, call_id, user)
    if data_call.status != CallStatus.DRAFT or data_call.funding_tx_hash is not None:
        raise HTTPException(
            status_code=409, detail="Only an unfunded draft call can be edited or removed"
        )
    return data_call


def reviewer_name(user: User) -> str:
    if user.display_name:
        return user.display_name
    if user.wallet_address.startswith("0x"):
        return f"{user.wallet_address[:6]}…{user.wallet_address[-4:]}"
    return "Account"


def record_protected_preview_access(
    db: Session, contribution: Contribution, reviewer: User
) -> None:
    message = f"Protected preview viewed by {reviewer_name(reviewer)} (account {reviewer.id})"
    existing = db.scalar(
        select(Event.id).where(
            Event.contribution_id == contribution.id,
            Event.event_type == "protected_preview_viewed",
            Event.message == message,
        )
    )
    if existing is None:
        db.add(
            Event(
                call_id=contribution.call_id,
                contribution_id=contribution.id,
                event_type="protected_preview_viewed",
                message=message,
            )
        )
        db.commit()


def apply_contribution_decision(
    db: Session, contribution: Contribution, reviewer: User, decision: str, tier: str
) -> None:
    if decision not in {"accept", "reject"}:
        raise HTTPException(status_code=422, detail="Invalid decision")
    if contribution.status == ContributionStatus.REJECTED:
        if decision != "accept":
            raise HTTPException(status_code=409, detail="Rejected data can only be reconsidered")
    elif contribution.status not in {ContributionStatus.READY, ContributionStatus.ERROR}:
        raise HTTPException(status_code=409, detail="Contribution cannot be decided now")
    contribution.final_decision = decision
    contribution.reviewer_id = reviewer.id
    contribution.reviewed_at = utcnow()
    name = reviewer_name(reviewer)
    if decision == "reject":
        contribution.status = ContributionStatus.REJECTED
        contribution.final_tier = None
        contribution.reward_amount = None
        message = f"Contribution rejected by {name}"
    else:
        _approve_contribution(db, contribution, tier)
        message = f"Contribution approved for payout at {tier} tier by {name}"
    db.add(
        Event(
            call_id=contribution.call_id,
            contribution_id=contribution.id,
            event_type=f"contribution_{decision}",
            message=message,
        )
    )


def _approve_contribution(db: Session, contribution: Contribution, tier: str) -> None:
    if tier not in {"standard", "high"}:
        raise HTTPException(status_code=422, detail="Invalid reward tier")
    if tier == "high" and contribution.data_call.high_reward is None:
        raise HTTPException(status_code=422, detail="This call has no high tier")
    accepted = db.scalar(
        select(func.count(Contribution.id)).where(
            Contribution.call_id == contribution.call_id,
            Contribution.final_decision == "accept",
            Contribution.id != contribution.id,
        )
    )
    if int(accepted or 0) >= contribution.data_call.max_acceptances:
        raise HTTPException(
            status_code=409,
            detail="Fund more DBT and expand the acceptance limit before accepting more data",
        )
    contribution.final_tier = tier
    contribution.reward_amount = (
        contribution.data_call.high_reward
        if tier == "high"
        else contribution.data_call.standard_reward
    )
    contribution.status = ContributionStatus.AWAITING_PAYOUT
