from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.blockchain import BlockchainService
from app.call_rules import (
    as_utc,
)
from app.config import Settings
from app.db import Database
from app.evaluation import validate_csv_requirements, validate_segmentation_mask, validate_upload
from app.lifecycle import evaluate_contribution
from app.models import (
    CallStatus,
    Contribution,
    ContributionStatus,
    DataCall,
    Event,
)
from app.web import get_db, require_user


def register_routes(
    app: FastAPI, app_settings: Settings, database: Database, chain: BlockchainService
) -> None:
    @app.post("/calls/{call_id}/contributions")
    async def submit_contribution(
        call_id: int,
        request: Request,
        background_tasks: BackgroundTasks,
        contribution_file: UploadFile = File(),
        source_image_file: UploadFile | None = File(None),
        companion_text: str = Form(""),
        db: Session = Depends(get_db),
    ) -> RedirectResponse:
        user = require_user(request, db)
        data_call = db.get(DataCall, call_id)
        if data_call is None:
            raise HTTPException(status_code=404, detail="Call not found")
        if data_call.status != CallStatus.OPEN or as_utc(data_call.deadline) <= datetime.now(UTC):
            raise HTTPException(status_code=409, detail="This call is not accepting contributions")

        content = await contribution_file.read(app_settings.max_upload_bytes + 1)
        if len(content) > app_settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="The uploaded file is too large")
        try:
            validated = validate_upload(
                content, data_call.data_type, contribution_file.content_type
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        clean_companion_text = companion_text.strip()
        validation_summary: str | None = None
        source_content: bytes | None = None
        source_validated = None
        if data_call.data_type == "image_text" and not 1 <= len(clean_companion_text) <= 2000:
            raise HTTPException(
                status_code=422,
                detail="Image-text contributions require 1 to 2000 characters of text",
            )
        if data_call.data_type == "csv":
            try:
                validation_summary = validate_csv_requirements(
                    content,
                    data_call.csv_columns or "",
                    data_call.csv_delimiter or "comma",
                    data_call.csv_min_records or 1,
                    data_call.csv_max_records,
                    data_call.csv_allow_extra_columns,
                    data_call.csv_allow_missing_values,
                    data_call.csv_unique_column,
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        if data_call.data_type == "image_segmentation_text":
            mode = data_call.segmentation_mode
            requires_source = mode in {"image_seg", "image_seg_text"}
            requires_text = mode in {"seg_text", "image_seg_text"}
            if requires_source and source_image_file is None:
                raise HTTPException(status_code=422, detail="A source image is required")
            if not requires_source and source_image_file is not None:
                raise HTTPException(
                    status_code=422, detail="This call accepts a segmentation mask and text only"
                )
            if requires_text and not 1 <= len(clean_companion_text) <= 2000:
                raise HTTPException(
                    status_code=422,
                    detail="This segmentation package requires 1 to 2000 characters of text",
                )
            if not requires_text and clean_companion_text:
                raise HTTPException(
                    status_code=422, detail="This segmentation package does not accept text"
                )
            if source_image_file is not None:
                source_content = await source_image_file.read(app_settings.max_upload_bytes + 1)
                if len(source_content) > app_settings.max_upload_bytes:
                    raise HTTPException(status_code=413, detail="The source image is too large")
                try:
                    source_validated = validate_upload(
                        source_content, "image_text", source_image_file.content_type
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
            try:
                mask_validation = validate_segmentation_mask(content, source_content)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            validation_summary = (
                f"{mask_validation} Segmentation package structure passed for mode {mode}."
            )

        package_hash = validated.sha256
        if data_call.data_type == "image_segmentation_text":
            digest = hashlib.sha256()
            digest.update(content)
            digest.update(b"\0")
            digest.update(source_content or b"")
            digest.update(b"\0")
            digest.update(clean_companion_text.encode("utf-8"))
            package_hash = digest.hexdigest()
        duplicate = db.scalar(
            select(Contribution).where(
                Contribution.call_id == call_id,
                Contribution.sha256 == package_hash,
            )
        )
        if duplicate is not None:
            if duplicate.status == ContributionStatus.REJECTED:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "This data matches a previously rejected contribution and was rejected "
                        "without AI reevaluation"
                    ),
                )
            raise HTTPException(status_code=409, detail="This file was already submitted")

        extension = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "text/csv": ".csv",
        }.get(validated.media_type, ".bin")
        stored_filename = f"{uuid.uuid4().hex}{extension}"
        path = app_settings.upload_dir / stored_filename
        path.write_bytes(content)
        source_path: Path | None = None
        source_stored_filename: str | None = None
        if source_content is not None and source_validated is not None:
            source_extension = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp",
            }.get(source_validated.media_type, ".bin")
            source_stored_filename = f"{uuid.uuid4().hex}{source_extension}"
            source_path = app_settings.upload_dir / source_stored_filename
            source_path.write_bytes(source_content)
        contribution = Contribution(
            call_id=call_id,
            contributor_id=user.id,
            stored_filename=stored_filename,
            original_filename=Path(contribution_file.filename or "contribution").name[:255],
            sha256=package_hash,
            media_type=validated.media_type,
            size_bytes=validated.size_bytes,
            companion_text=clean_companion_text or None,
            source_stored_filename=source_stored_filename,
            source_original_filename=(
                Path(source_image_file.filename or "source-image").name[:255]
                if source_image_file is not None
                else None
            ),
            source_sha256=(source_validated.sha256 if source_validated is not None else None),
            source_media_type=(
                source_validated.media_type if source_validated is not None else None
            ),
            source_size_bytes=(
                source_validated.size_bytes if source_validated is not None else None
            ),
            validation_summary=validation_summary,
            status=(
                ContributionStatus.EVALUATING
                if data_call.review_mode == "ai_assisted"
                else ContributionStatus.READY
            ),
            evaluation_progress=5 if data_call.review_mode == "ai_assisted" else 100,
            evaluation_stage=(
                "Queued for evaluation"
                if data_call.review_mode == "ai_assisted"
                else "Manual review"
            ),
        )
        db.add(contribution)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            path.unlink(missing_ok=True)
            if source_path is not None:
                source_path.unlink(missing_ok=True)
            raise HTTPException(status_code=409, detail="This file was already submitted") from exc
        db.add(
            Event(
                call_id=call_id,
                contribution_id=contribution.id,
                event_type="contribution_submitted",
                message="Contribution submitted",
            )
        )
        db.commit()
        if data_call.review_mode == "ai_assisted":
            background_tasks.add_task(
                evaluate_contribution,
                database,
                app_settings,
                contribution.id,
            )
        return RedirectResponse(f"/contributions/{contribution.id}", status_code=303)
