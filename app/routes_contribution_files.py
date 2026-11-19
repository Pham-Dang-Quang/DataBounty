from __future__ import annotations

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
)
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.blockchain import BlockchainService
from app.config import Settings
from app.constants import ACCEPTED_STATUSES
from app.db import Database
from app.lifecycle import refresh_payout_state
from app.models import (
    Contribution,
    User,
)
from app.previews import stored_protected_image
from app.review_service import (
    can_review_call,
    record_protected_preview_access,
)
from app.web import get_db, render, require_user


def register_routes(
    app: FastAPI, app_settings: Settings, database: Database, chain: BlockchainService
) -> None:
    @app.get("/contributions/{contribution_id}", response_class=HTMLResponse)
    def contribution_detail(
        contribution_id: int, request: Request, db: Session = Depends(get_db)
    ) -> HTMLResponse:
        user = require_user(request, db)
        contribution = db.scalar(
            select(Contribution)
            .options(
                selectinload(Contribution.data_call),
                selectinload(Contribution.contributor),
                selectinload(Contribution.reviewer),
            )
            .where(Contribution.id == contribution_id)
        )
        if contribution is None:
            raise HTTPException(status_code=404, detail="Contribution not found")
        can_review = can_review_call(db, contribution.data_call, user)
        if user.id != contribution.contributor_id and not can_review:
            raise HTTPException(status_code=403, detail="Not allowed to view this contribution")
        refresh_payout_state(db, contribution, chain)
        return render(
            request,
            "contribution_detail.html",
            db=db,
            contribution=contribution,
            can_review=can_review,
            is_caller=contribution.data_call.caller_id == user.id,
            is_contributor=contribution.contributor_id == user.id,
            is_protected_image=(
                contribution.contributor_id != user.id
                and contribution.status not in ACCEPTED_STATUSES
                and contribution.media_type.startswith("image/")
            ),
            is_csv_hidden=(
                contribution.data_call.data_type == "csv"
                and contribution.contributor_id != user.id
                and contribution.status not in ACCEPTED_STATUSES
            ),
            is_source_protected=(
                bool(contribution.source_stored_filename)
                and contribution.contributor_id != user.id
                and contribution.status not in ACCEPTED_STATUSES
            ),
        )

    def protected_image_response(
        contribution: Contribution,
        reviewer: User,
        db: Session,
        stored_filename: str | None = None,
    ) -> FileResponse:
        record_protected_preview_access(db, contribution, reviewer)
        try:
            preview_path = stored_protected_image(
                app_settings.upload_dir,
                stored_filename or contribution.stored_filename,
                contribution.id,
            )
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Could not create review preview") from exc
        return FileResponse(
            preview_path,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-store, private",
                "Content-Disposition": "inline",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get("/contributions/{contribution_id}/protected-image-v4")
    def contribution_protected_image(
        contribution_id: int, request: Request, db: Session = Depends(get_db)
    ) -> FileResponse:
        user = require_user(request, db)
        contribution = db.scalar(
            select(Contribution)
            .options(selectinload(Contribution.data_call))
            .where(Contribution.id == contribution_id)
        )
        if contribution is None:
            raise HTTPException(status_code=404, detail="Contribution not found")
        if user.id == contribution.contributor_id or not can_review_call(
            db, contribution.data_call, user
        ):
            raise HTTPException(status_code=403, detail="Not allowed to read this preview")
        if contribution.status in ACCEPTED_STATUSES or not contribution.media_type.startswith(
            "image/"
        ):
            raise HTTPException(status_code=404, detail="Protected image is not available")
        return protected_image_response(contribution, user, db)

    @app.get("/contributions/{contribution_id}/file")
    def contribution_file(
        contribution_id: int, request: Request, db: Session = Depends(get_db)
    ) -> Response:
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
            raise HTTPException(status_code=403, detail="Not allowed to read this file")
        if (
            contribution.data_call.data_type == "csv"
            and user.id != contribution.contributor_id
            and contribution.status not in ACCEPTED_STATUSES
        ):
            raise HTTPException(
                status_code=403, detail="CSV contents are hidden until payment is confirmed"
            )
        protected_image = (
            user.id != contribution.contributor_id
            and contribution.status not in ACCEPTED_STATUSES
            and contribution.media_type.startswith("image/")
        )
        if protected_image:
            return protected_image_response(contribution, user, db)
        return FileResponse(
            app_settings.upload_dir / contribution.stored_filename,
            media_type=contribution.media_type,
            headers={"Cache-Control": "no-store, private", "X-Content-Type-Options": "nosniff"},
            filename=(
                contribution.original_filename if user.id == contribution.contributor_id else None
            ),
            content_disposition_type=(
                "attachment" if user.id == contribution.contributor_id else "inline"
            ),
        )

    @app.get("/contributions/{contribution_id}/source-protected-image-v1")
    def contribution_protected_source_image(
        contribution_id: int, request: Request, db: Session = Depends(get_db)
    ) -> FileResponse:
        user = require_user(request, db)
        contribution = db.scalar(
            select(Contribution)
            .options(selectinload(Contribution.data_call))
            .where(Contribution.id == contribution_id)
        )
        if contribution is None or not contribution.source_stored_filename:
            raise HTTPException(status_code=404, detail="Source image not found")
        if user.id == contribution.contributor_id or not can_review_call(
            db, contribution.data_call, user
        ):
            raise HTTPException(status_code=403, detail="Not allowed to read this preview")
        if contribution.status in ACCEPTED_STATUSES:
            raise HTTPException(status_code=404, detail="Protected image is not available")
        return protected_image_response(contribution, user, db, contribution.source_stored_filename)

    @app.get("/contributions/{contribution_id}/source-file")
    def contribution_source_file(
        contribution_id: int, request: Request, db: Session = Depends(get_db)
    ) -> Response:
        user = require_user(request, db)
        contribution = db.scalar(
            select(Contribution)
            .options(selectinload(Contribution.data_call))
            .where(Contribution.id == contribution_id)
        )
        if contribution is None or not contribution.source_stored_filename:
            raise HTTPException(status_code=404, detail="Source image not found")
        can_review = can_review_call(db, contribution.data_call, user)
        if user.id != contribution.contributor_id and not can_review:
            raise HTTPException(status_code=403, detail="Not allowed to read this file")
        if user.id != contribution.contributor_id and contribution.status not in ACCEPTED_STATUSES:
            return protected_image_response(
                contribution, user, db, contribution.source_stored_filename
            )
        return FileResponse(
            app_settings.upload_dir / contribution.source_stored_filename,
            media_type=contribution.source_media_type or "application/octet-stream",
            headers={"Cache-Control": "no-store, private", "X-Content-Type-Options": "nosniff"},
            filename=(
                contribution.source_original_filename
                if user.id == contribution.contributor_id
                else None
            ),
            content_disposition_type=(
                "attachment" if user.id == contribution.contributor_id else "inline"
            ),
        )
