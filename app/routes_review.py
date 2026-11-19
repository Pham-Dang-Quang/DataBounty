from __future__ import annotations

import csv
import zipfile
from io import BytesIO, StringIO
from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.blockchain import BlockchainService
from app.config import Settings
from app.constants import ACCEPTED_STATUSES, REVIEWABLE_STATUSES, UNDECIDED_STATUSES
from app.db import Database
from app.models import (
    Contribution,
    ContributionStatus,
    Event,
)
from app.review_service import (
    apply_contribution_decision,
    owned_call,
    reviewable_call,
    reviewer_name,
)
from app.web import get_db, render, require_user


def register_routes(
    app: FastAPI, app_settings: Settings, database: Database, chain: BlockchainService
) -> None:
    @app.get("/calls/{call_id}/review", response_class=HTMLResponse)
    def review_queue(
        call_id: int,
        request: Request,
        tab: str = "undecided",
        ai: list[str] | None = Query(None),
        db: Session = Depends(get_db),
    ) -> HTMLResponse:
        user = require_user(request, db)
        data_call = reviewable_call(db, call_id, user)
        if tab not in {"undecided", "accepted", "rejected"}:
            raise HTTPException(status_code=422, detail="Review tab is invalid")
        ai_filters = set(ai or [])
        if not ai_filters <= {"accept", "reject", "unsure"}:
            raise HTTPException(status_code=422, detail="AI recommendation filter is invalid")
        all_contributions = db.scalars(
            select(Contribution)
            .options(
                selectinload(Contribution.contributor),
                selectinload(Contribution.reviewer),
            )
            .where(Contribution.call_id == call_id)
            .order_by(Contribution.created_at.asc())
        ).all()
        grouped = {
            "undecided": [item for item in all_contributions if item.status in UNDECIDED_STATUSES],
            "accepted": [item for item in all_contributions if item.status in ACCEPTED_STATUSES],
            "rejected": [
                item for item in all_contributions if item.status == ContributionStatus.REJECTED
            ],
        }
        visible_contributions = grouped[tab]
        if ai_filters:
            visible_contributions = [
                item for item in visible_contributions if item.ai_recommendation in ai_filters
            ]
        committed_count = sum(item.final_decision == "accept" for item in all_contributions)
        filter_suffix = "".join(f"&ai={value}" for value in sorted(ai_filters))
        return render(
            request,
            "review_queue.html",
            db=db,
            data_call=data_call,
            contributions=visible_contributions,
            tab=tab,
            tab_counts={name: len(items) for name, items in grouped.items()},
            ai_filters=ai_filters,
            filter_suffix=filter_suffix,
            acceptance_full=committed_count >= data_call.max_acceptances,
            is_caller=data_call.caller_id == user.id,
        )

    @app.post("/calls/{call_id}/review/apply-ai")
    def apply_ai_recommendations(
        call_id: int, request: Request, db: Session = Depends(get_db)
    ) -> RedirectResponse:
        caller = require_user(request, db)
        data_call = owned_call(db, call_id, caller)
        candidates = db.scalars(
            select(Contribution)
            .where(
                Contribution.call_id == call_id,
                Contribution.status.in_(REVIEWABLE_STATUSES),
                Contribution.ai_recommendation.in_(("accept", "reject")),
            )
            .order_by(Contribution.created_at.asc())
        ).all()
        accepted_count = int(
            db.scalar(
                select(func.count(Contribution.id)).where(
                    Contribution.call_id == call_id,
                    Contribution.final_decision == "accept",
                )
            )
            or 0
        )
        remaining_slots = max(0, data_call.max_acceptances - accepted_count)
        applied = 0
        for contribution in candidates:
            recommendation = contribution.ai_recommendation
            if recommendation == "accept":
                if remaining_slots == 0:
                    continue
                tier = (
                    "high"
                    if contribution.ai_tier == "high" and data_call.high_reward is not None
                    else "standard"
                )
                apply_contribution_decision(db, contribution, caller, "accept", tier)
                remaining_slots -= 1
            else:
                apply_contribution_decision(db, contribution, caller, "reject", "standard")
            applied += 1
        db.add(
            Event(
                call_id=call_id,
                event_type="ai_recommendations_applied",
                message=f"{reviewer_name(caller)} applied {applied} AI recommendation(s)",
            )
        )
        db.commit()
        return RedirectResponse(f"/calls/{call_id}/review?tab=undecided", status_code=303)

    @app.get("/calls/{call_id}/accepted.zip")
    def download_accepted_data(
        call_id: int, request: Request, db: Session = Depends(get_db)
    ) -> Response:
        caller = require_user(request, db)
        data_call = owned_call(db, call_id, caller)
        accepted = db.scalars(
            select(Contribution)
            .options(selectinload(Contribution.contributor))
            .where(
                Contribution.call_id == call_id,
                Contribution.status.in_(ACCEPTED_STATUSES),
            )
            .order_by(Contribution.id.asc())
        ).all()
        if not accepted:
            raise HTTPException(status_code=404, detail="No accepted data is available")
        archive = BytesIO()
        manifest = StringIO(newline="")
        writer = csv.writer(manifest)
        writer.writerow(
            [
                "contribution_id",
                "file",
                "source_image",
                "companion_text",
                "quality_tier",
                "status",
            ]
        )
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for item in accepted:
                safe_name = Path(item.original_filename).name
                archive_name = f"data/{item.id}_{safe_name}"
                source = app_settings.upload_dir / item.stored_filename
                if source.is_file():
                    output.write(source, archive_name)
                source_archive_name = ""
                if item.source_stored_filename and item.source_original_filename:
                    source_safe_name = Path(item.source_original_filename).name
                    source_archive_name = f"data/{item.id}_source_{source_safe_name}"
                    source_image = app_settings.upload_dir / item.source_stored_filename
                    if source_image.is_file():
                        output.write(source_image, source_archive_name)
                writer.writerow(
                    [
                        item.id,
                        archive_name,
                        source_archive_name,
                        item.companion_text or "",
                        item.final_tier or "",
                        item.status,
                    ]
                )
            output.writestr("manifest.csv", manifest.getvalue().encode("utf-8-sig"))
        filename = f"call-{data_call.id}-accepted.zip"
        return Response(
            content=archive.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
