from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.blockchain import BlockchainService
from app.config import Settings
from app.db import Database
from app.evaluation import evaluate_file
from app.models import CallStatus, Contribution, ContributionStatus, DataCall, Event


def evaluate_contribution(database: Database, settings: Settings, contribution_id: int) -> None:
    with database.session_factory() as db:
        contribution = db.scalar(
            select(Contribution)
            .options(selectinload(Contribution.data_call))
            .where(Contribution.id == contribution_id)
        )
        if contribution is None or contribution.status != ContributionStatus.EVALUATING:
            return

        def report_progress(percent: int, stage: str) -> None:
            contribution.evaluation_progress = max(
                contribution.evaluation_progress, min(99, percent)
            )
            contribution.evaluation_stage = stage[:120]
            db.commit()

        result = evaluate_file(
            settings.upload_dir / contribution.stored_filename,
            contribution.data_call.data_type,
            contribution.data_call.acceptance_criteria,
            settings,
            report_progress,
            contribution.companion_text,
            contribution.data_call.ai_evaluation_prompt,
            settings.upload_dir / contribution.source_stored_filename
            if contribution.source_stored_filename
            else None,
            contribution.data_call.segmentation_mode,
            contribution.validation_summary,
        )
        contribution.ai_recommendation = result.recommendation
        contribution.ai_tier = result.tier
        contribution.ai_explanation = result.explanation
        contribution.model_name = result.model_name
        contribution.status = ContributionStatus.READY
        contribution.evaluation_progress = 100
        contribution.evaluation_stage = "Evaluation complete"
        db.add(
            Event(
                call_id=contribution.call_id,
                contribution_id=contribution.id,
                event_type="evaluation_completed",
                message=f"AI recommendation: {result.recommendation}",
            )
        )
        db.commit()


def refresh_chain_state(db: Session, data_call: DataCall, chain: BlockchainService) -> None:
    if (
        data_call.status != CallStatus.FUNDING
        or not data_call.funding_tx_hash
        or not chain.configured
    ):
        return
    state = chain.transaction_state(data_call.funding_tx_hash)
    if state.state == "confirmed" and chain.call_is_funded(
        data_call.escrow_call_id or data_call.id,
        data_call.required_budget,
        data_call.caller.wallet_address,
    ):
        data_call.status = CallStatus.OPEN
        db.add(
            Event(
                call_id=data_call.id,
                event_type="funding_confirmed",
                message="Funding confirmed; call opened",
                tx_hash=data_call.funding_tx_hash,
            )
        )
        db.commit()


def refresh_payout_state(db: Session, contribution: Contribution, chain: BlockchainService) -> None:
    if (
        contribution.status != ContributionStatus.AWAITING_PAYOUT
        or not contribution.payout_tx_hash
        or not chain.configured
    ):
        return
    state = chain.transaction_state(contribution.payout_tx_hash)
    call_id = contribution.data_call.escrow_call_id or contribution.call_id
    if state.state == "confirmed" and chain.contribution_is_paid(call_id, contribution.payout_key):
        contribution.status = ContributionStatus.PAID
        db.add(
            Event(
                call_id=contribution.call_id,
                contribution_id=contribution.id,
                event_type="payout_confirmed",
                message="Payout confirmed on Fuji",
                tx_hash=contribution.payout_tx_hash,
            )
        )
        db.commit()
