from __future__ import annotations

from fastapi import (
    Depends,
    FastAPI,
    Form,
    HTTPException,
    Request,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.blockchain import BlockchainService
from app.call_rules import (
    allocate_escrow_call_id,
    parse_call_links,
    parse_deadline,
    parse_token_amount,
    validate_call_fields,
)
from app.config import Settings
from app.db import Database
from app.models import (
    CallLink,
    DataCall,
    Event,
)
from app.web import get_db, render, require_user


def register_routes(
    app: FastAPI, app_settings: Settings, database: Database, chain: BlockchainService
) -> None:
    @app.get("/calls/new", response_class=HTMLResponse)
    def new_call(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
        require_user(request, db)
        return render(
            request,
            "call_form.html",
            db=db,
            form_action="/calls",
            form_title="New data call",
            submit_label="Create draft",
        )

    @app.post("/calls")
    def create_call_route(
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

        data_call = DataCall(
            caller_id=user.id,
            escrow_call_id=allocate_escrow_call_id(db),
            title=title.strip(),
            description=description.strip(),
            data_type=data_type,
            acceptance_criteria=acceptance_criteria.strip(),
            ai_evaluation_prompt=ai_evaluation_prompt.strip() or None,
            csv_columns=csv_columns.strip() or None,
            csv_delimiter=csv_delimiter if data_type == "csv" else None,
            csv_min_records=csv_min_records if data_type == "csv" else None,
            csv_max_records=csv_max_records if data_type == "csv" else None,
            csv_allow_extra_columns=csv_allow_extra_columns if data_type == "csv" else False,
            csv_allow_missing_values=csv_allow_missing_values if data_type == "csv" else False,
            csv_unique_column=csv_unique_column.strip() or None,
            segmentation_mode=(
                segmentation_mode if data_type == "image_segmentation_text" else None
            ),
            review_mode=review_mode,
            standard_reward=standard,
            high_reward=high,
            max_acceptances=max_acceptances,
            deadline=parsed_deadline,
        )
        db.add(data_call)
        db.flush()
        for label, url in links:
            db.add(CallLink(call_id=data_call.id, label=label, url=url))
        db.add(Event(call_id=data_call.id, event_type="call_created", message="Call created"))
        db.commit()
        return RedirectResponse(f"/calls/{data_call.id}", status_code=303)
