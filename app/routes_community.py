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

from app.auth import (
    normalize_email,
)
from app.blockchain import BlockchainService
from app.config import Settings
from app.db import Database
from app.models import (
    CallModerator,
    CallStatus,
    Comment,
    DataCall,
    Event,
    User,
)
from app.review_service import (
    can_review_call,
    owned_call,
    reviewer_name,
)
from app.web import get_db, require_user


def register_routes(
    app: FastAPI, app_settings: Settings, database: Database, chain: BlockchainService
) -> None:
    @app.post("/calls/{call_id}/moderators")
    def add_moderator(
        call_id: int,
        request: Request,
        email: str = Form(),
        db: Session = Depends(get_db),
    ) -> RedirectResponse:
        caller = require_user(request, db)
        data_call = owned_call(db, call_id, caller)
        try:
            normalized = normalize_email(email)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        moderator = db.scalar(select(User).where(User.email == normalized))
        if moderator is None:
            raise HTTPException(status_code=404, detail="No account uses this email")
        if moderator.id == caller.id:
            raise HTTPException(status_code=422, detail="The caller is already a reviewer")
        existing = db.scalar(
            select(CallModerator).where(
                CallModerator.call_id == call_id,
                CallModerator.user_id == moderator.id,
            )
        )
        if existing:
            raise HTTPException(status_code=409, detail="This account is already a moderator")
        db.add(CallModerator(call_id=call_id, user_id=moderator.id))
        db.add(
            Event(
                call_id=call_id,
                event_type="moderator_added",
                message=f"Moderator {reviewer_name(moderator)} added",
            )
        )
        db.commit()
        return RedirectResponse(f"/calls/{data_call.id}#moderators", status_code=303)

    @app.post("/calls/{call_id}/moderators/{user_id}/delete")
    def remove_moderator(
        call_id: int,
        user_id: int,
        request: Request,
        db: Session = Depends(get_db),
    ) -> RedirectResponse:
        caller = require_user(request, db)
        data_call = owned_call(db, call_id, caller)
        link = db.scalar(
            select(CallModerator)
            .options(selectinload(CallModerator.user))
            .where(CallModerator.call_id == call_id, CallModerator.user_id == user_id)
        )
        if link is None:
            raise HTTPException(status_code=404, detail="Moderator not found")
        name = reviewer_name(link.user)
        db.delete(link)
        db.add(
            Event(
                call_id=call_id,
                event_type="moderator_removed",
                message=f"Moderator {name} removed",
            )
        )
        db.commit()
        return RedirectResponse(f"/calls/{data_call.id}#moderators", status_code=303)

    @app.post("/calls/{call_id}/comments")
    def add_comment(
        call_id: int,
        request: Request,
        body: str = Form(),
        parent_id: int | None = Form(None),
        db: Session = Depends(get_db),
    ) -> RedirectResponse:
        user = require_user(request, db)
        data_call = db.get(DataCall, call_id)
        if data_call is None:
            raise HTTPException(status_code=404, detail="Call not found")
        if data_call.status == CallStatus.DRAFT and not can_review_call(db, data_call, user):
            raise HTTPException(
                status_code=403,
                detail="Only the caller or an assigned moderator can comment on a draft call",
            )
        text_body = body.strip()
        if not 1 <= len(text_body) <= 1000:
            raise HTTPException(status_code=422, detail="Comment must contain 1 to 1000 characters")
        if parent_id is not None:
            parent = db.get(Comment, parent_id)
            if parent is None or parent.call_id != call_id or parent.parent_id is not None:
                raise HTTPException(
                    status_code=422, detail="Replies must target a top-level comment"
                )
        db.add(Comment(call_id=call_id, author_id=user.id, parent_id=parent_id, body=text_body))
        db.commit()
        return RedirectResponse(f"/calls/{call_id}#discussion", status_code=303)
