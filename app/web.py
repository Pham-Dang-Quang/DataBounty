from __future__ import annotations

from collections.abc import Generator
from typing import Any, cast

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.models import User


def get_db(request: Request) -> Generator[Session, None, None]:
    yield from request.app.state.database.sessions()


def current_user(request: Request, db: Session | None) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id or db is None:
        return None
    return db.get(User, int(user_id))


def require_user(request: Request, db: Session) -> User:
    user = current_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    return user


def render(request: Request, name: str, **context: Any) -> HTMLResponse:
    settings = request.app.state.settings
    templates = request.app.state.templates
    db_value = context.pop("db", None)
    db_context = cast(Session | None, db_value if isinstance(db_value, Session) else None)
    user = current_user(request, db_context)
    linked_wallet = user.wallet_address if user and user.wallet_address.startswith("0x") else ""
    base: dict[str, Any] = {
        "request": request,
        "user": user,
        "app_name": settings.app_name,
        "chain_id": settings.chain_id,
        "escrow_address": settings.escrow_contract_address,
        "token_address": settings.token_contract_address,
        "token_symbol": settings.token_symbol,
        "token_decimals": settings.token_decimals,
        "explorer_url": settings.fuji_explorer_url.rstrip("/"),
        "max_upload_mb": settings.max_upload_bytes // (1024 * 1024),
        "linked_wallet": linked_wallet,
        "server_error": request.session.pop("error_popup", None),
    }
    base.update(context)
    return templates.TemplateResponse(request, name, base)
