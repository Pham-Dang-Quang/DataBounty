from __future__ import annotations

from fastapi import (
    Depends,
    FastAPI,
    Form,
    HTTPException,
    Request,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.blockchain import BlockchainService
from app.call_rules import (
    parse_call_links,
    parse_deadline,
    parse_token_amount,
    validate_call_fields,
)
from app.config import Settings
from app.constants import UNDECIDED_STATUSES
from app.db import Database
from app.lifecycle import refresh_chain_state
from app.models import (
    CallLink,
    CallModerator,
    Comment,
    Contribution,
    DataCall,
    Event,
)
from app.review_service import (
    can_review_call,
    editable_draft,
)
from app.web import current_user, get_db, render, require_user


def register_routes(
    app: FastAPI, app_settings: Settings, database: Database, chain: BlockchainService
) -> None:
    @app.get("/calls/{call_id}/edit", response_class=HTMLResponse)
    def edit_call_form(
        call_id: int, request: Request, db: Session = Depends(get_db)
    ) -> HTMLResponse:
        user = require_user(request, db)
        data_call = editable_draft(db, call_id, user)
        return render(
            request,
            "call_form.html",
            db=db,
            data_call=data_call,
            form_action=f"/calls/{call_id}/edit",
            form_title="Edit data call",
            submit_label="Save changes",
        )

    @app.post("/calls/{call_id}/edit")
    def edit_call(
        call_id: int,
        request: Request,
        title: str = Form(),
        description: str = Form(),
        data_type: str = Form(),
        acceptance_criteria: str = Form(),
        review_mode: str = Form(),
        standard_reward: str = Form(),
        high_reward: str = Form(""),
        max_acceptances: int = Form(),
        deadline: str = Form(),
        links_text: str = Form(""),
        ai_evaluation_prompt: str = Form(""),
        csv_columns: str = Form(""),
        csv_delimiter: str = Form("comma"),
        csv_min_records: int = Form(1),
        csv_max_records: int | None = Form(None),
        csv_allow_extra_columns: bool = Form(False),
        csv_allow_missing_values: bool = Form(False),
        csv_unique_column: str = Form(""),
        segmentation_mode: str = Form(""),
        db: Session = Depends(get_db),
    ) -> RedirectResponse:
        user = require_user(request, db)
        data_call = editable_draft(db, call_id, user)
        try:
            standard = parse_token_amount(standard_reward, app_settings.token_decimals)
            high = (
                parse_token_amount(high_reward, app_settings.token_decimals)
                if high_reward
                else None
            )
            parsed_deadline = parse_deadline(deadline)
            validate_call_fields(
                title,
                description,
                acceptance_criteria,
                data_type,
                review_mode,
                standard,
                high,
                max_acceptances,
                parsed_deadline,
                ai_evaluation_prompt,
                csv_columns,
                csv_delimiter,
                csv_min_records,
                csv_max_records,
                csv_allow_extra_columns,
                csv_allow_missing_values,
                csv_unique_column,
                segmentation_mode,
            )
            links = parse_call_links(links_text)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        data_call.title = title.strip()
        data_call.description = description.strip()
        data_call.data_type = data_type
        data_call.acceptance_criteria = acceptance_criteria.strip()
        data_call.ai_evaluation_prompt = ai_evaluation_prompt.strip() or None
        data_call.csv_columns = csv_columns.strip() or None
        data_call.csv_delimiter = csv_delimiter if data_type == "csv" else None
        data_call.csv_min_records = csv_min_records if data_type == "csv" else None
        data_call.csv_max_records = csv_max_records if data_type == "csv" else None
        data_call.csv_allow_extra_columns = csv_allow_extra_columns if data_type == "csv" else False
        data_call.csv_allow_missing_values = (
            csv_allow_missing_values if data_type == "csv" else False
        )
        data_call.csv_unique_column = csv_unique_column.strip() or None
        data_call.segmentation_mode = (
            segmentation_mode if data_type == "image_segmentation_text" else None
        )
        data_call.review_mode = review_mode
        data_call.standard_reward = standard
        data_call.high_reward = high
        data_call.max_acceptances = max_acceptances
        data_call.deadline = parsed_deadline
        db.execute(delete(CallLink).where(CallLink.call_id == call_id))
        for label, url in links:
            db.add(CallLink(call_id=call_id, label=label, url=url))
        db.add(Event(call_id=call_id, event_type="call_updated", message="Draft updated"))
        db.commit()
        return RedirectResponse(f"/calls/{call_id}", status_code=303)

    @app.post("/calls/{call_id}/delete")
    def delete_call(
        call_id: int, request: Request, db: Session = Depends(get_db)
    ) -> RedirectResponse:
        user = require_user(request, db)
        data_call = editable_draft(db, call_id, user)
        contribution_count = db.scalar(
            select(func.count(Contribution.id)).where(Contribution.call_id == call_id)
        )
        if contribution_count:
            raise HTTPException(
                status_code=409, detail="A call with contributions cannot be removed"
            )
        db.execute(delete(Event).where(Event.call_id == call_id))
        db.delete(data_call)
        db.commit()
        return RedirectResponse("/", status_code=303)

    @app.get("/calls/{call_id}", response_class=HTMLResponse)
    def call_detail(call_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
        data_call = db.scalar(
            select(DataCall)
            .options(
                selectinload(DataCall.caller),
                selectinload(DataCall.contributions),
                selectinload(DataCall.links),
                selectinload(DataCall.moderator_links).selectinload(CallModerator.user),
            )
            .where(DataCall.id == call_id)
        )
        if data_call is None:
            raise HTTPException(status_code=404, detail="Call not found")
        refresh_chain_state(db, data_call, chain)
        events = db.scalars(
            select(Event).where(Event.call_id == call_id).order_by(Event.created_at.desc())
        ).all()
        comments = db.scalars(
            select(Comment)
            .options(
                selectinload(Comment.author),
                selectinload(Comment.replies).selectinload(Comment.author),
            )
            .where(Comment.call_id == call_id, Comment.parent_id.is_(None))
            .order_by(Comment.created_at.asc())
        ).all()
        user = current_user(request, db)
        accepted_count = sum(item.final_decision == "accept" for item in data_call.contributions)
        return render(
            request,
            "call_detail.html",
            db=db,
            data_call=data_call,
            events=events,
            comments=comments,
            undecided_count=sum(
                item.status in UNDECIDED_STATUSES for item in data_call.contributions
            ),
            accepted_count=accepted_count,
            can_review=bool(user and can_review_call(db, data_call, user)),
        )
