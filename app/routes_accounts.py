from __future__ import annotations

import uuid
from collections.abc import Sequence
from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import (
    create_challenge,
    hash_password,
    normalize_email,
    verify_challenge,
    verify_password,
)
from app.blockchain import BlockchainService
from app.config import Settings
from app.db import Database
from app.evaluation import validate_upload
from app.models import (
    CallStatus,
    DataCall,
    User,
)
from app.schemas import ChallengeRequest, VerifyRequest
from app.web import current_user, get_db, render, require_user


def register_routes(
    app: FastAPI, app_settings: Settings, database: Database, chain: BlockchainService
) -> None:
    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
        user = current_user(request, db)
        open_calls_query = (
            select(DataCall)
            .options(selectinload(DataCall.caller))
            .where(DataCall.status == CallStatus.OPEN)
            .order_by(DataCall.created_at.desc())
        )
        if user:
            open_calls_query = open_calls_query.where(DataCall.caller_id != user.id)
        calls = db.scalars(open_calls_query).all()
        own_calls: Sequence[DataCall] = []
        if user:
            own_calls = db.scalars(
                select(DataCall)
                .options(selectinload(DataCall.caller))
                .where(DataCall.caller_id == user.id)
                .order_by(DataCall.created_at.desc())
            ).all()
        return render(request, "home.html", db=db, calls=calls, own_calls=own_calls)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/signup", response_class=HTMLResponse)
    def signup_form(request: Request, db: Session = Depends(get_db)) -> Response:
        if current_user(request, db):
            return RedirectResponse("/", status_code=303)
        return render(request, "auth_form.html", db=db, mode="signup")

    @app.post("/signup")
    def signup(
        request: Request,
        email: str = Form(),
        password: str = Form(),
        display_name: str = Form(),
        db: Session = Depends(get_db),
    ) -> RedirectResponse:
        try:
            normalized = normalize_email(email)
            password_digest = hash_password(password)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        name = display_name.strip()
        if not 2 <= len(name) <= 80:
            raise HTTPException(status_code=422, detail="Name must contain 2 to 80 characters")
        if db.scalar(select(User).where(User.email == normalized)):
            raise HTTPException(status_code=409, detail="An account already uses this email")
        user = User(
            wallet_address=f"local:{uuid.uuid4().hex}",
            email=normalized,
            password_hash=password_digest,
            display_name=name,
        )
        db.add(user)
        db.commit()
        request.session.clear()
        request.session["user_id"] = user.id
        return RedirectResponse("/settings", status_code=303)

    @app.get("/signin", response_class=HTMLResponse)
    def signin_form(request: Request, db: Session = Depends(get_db)) -> Response:
        if current_user(request, db):
            return RedirectResponse("/", status_code=303)
        return render(request, "auth_form.html", db=db, mode="signin")

    @app.post("/signin")
    def signin(
        request: Request,
        email: str = Form(),
        password: str = Form(),
        db: Session = Depends(get_db),
    ) -> RedirectResponse:
        try:
            normalized = normalize_email(email)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Email or password is incorrect") from exc
        user = db.scalar(select(User).where(User.email == normalized))
        if user is None or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Email or password is incorrect")
        request.session.clear()
        request.session["user_id"] = user.id
        return RedirectResponse("/", status_code=303)

    @app.get("/settings", response_class=HTMLResponse)
    def account_settings(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
        require_user(request, db)
        return render(request, "settings.html", db=db)

    @app.post("/settings")
    async def update_account_settings(
        request: Request,
        email: str = Form(),
        display_name: str = Form(),
        bio: str = Form(""),
        new_password: str = Form(""),
        profile_picture: UploadFile | None = File(None),
        db: Session = Depends(get_db),
    ) -> RedirectResponse:
        user = require_user(request, db)
        try:
            normalized_email = normalize_email(email)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        email_owner = db.scalar(
            select(User).where(User.email == normalized_email, User.id != user.id)
        )
        if email_owner:
            raise HTTPException(status_code=409, detail="An account already uses this email")
        name = display_name.strip()
        if not 2 <= len(name) <= 80 or len(bio.strip()) > 500:
            raise HTTPException(status_code=422, detail="Check the name and 500-character bio")
        user.email = normalized_email
        user.display_name = name
        user.bio = bio.strip() or None
        if new_password:
            try:
                user.password_hash = hash_password(new_password)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        if profile_picture and profile_picture.filename:
            content = await profile_picture.read(app_settings.max_upload_bytes + 1)
            if len(content) > app_settings.max_upload_bytes:
                raise HTTPException(status_code=413, detail="Profile picture is too large")
            try:
                validated = validate_upload(content, "image", profile_picture.content_type)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[
                validated.media_type
            ]
            filename = f"profile-{uuid.uuid4().hex}{extension}"
            (app_settings.upload_dir / filename).write_bytes(content)
            user.profile_image = filename
        db.commit()
        return RedirectResponse("/settings", status_code=303)

    @app.get("/profiles/{user_id}/picture")
    def profile_picture(user_id: int, db: Session = Depends(get_db)) -> FileResponse:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="Account not found")
        profile_path = app_settings.upload_dir / user.profile_image if user.profile_image else None
        if profile_path is None or not profile_path.is_file():
            return FileResponse(Path(__file__).parent / "static" / "images" / "default-avatar.svg")
        return FileResponse(profile_path)

    @app.post("/api/auth/challenge")
    def auth_challenge(
        request: Request, payload: ChallengeRequest, db: Session = Depends(get_db)
    ) -> dict[str, str]:
        try:
            message = create_challenge(db, payload.address, app_settings.chain_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"message": message}

    @app.post("/api/auth/verify")
    def auth_verify(
        request: Request, payload: VerifyRequest, db: Session = Depends(get_db)
    ) -> dict[str, str]:
        try:
            current = current_user(request, db)
            user = verify_challenge(db, current, payload.message, payload.signature)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        request.session.clear()
        request.session["user_id"] = user.id
        return {"wallet_address": user.wallet_address}

    @app.post("/api/auth/logout")
    def auth_logout(request: Request) -> dict[str, bool]:
        request.session.clear()
        return {"ok": True}
