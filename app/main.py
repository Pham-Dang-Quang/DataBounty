from __future__ import annotations

import csv
import hashlib
import re
import secrets
import uuid
import zipfile
from collections.abc import Generator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.auth import (
    create_challenge,
    hash_password,
    normalize_email,
    verify_challenge,
    verify_password,
)
from app.blockchain import BlockchainService
from app.config import Settings, get_settings
from app.db import Database
from app.evaluation import (
    CSV_DELIMITERS,
    evaluate_file,
    parse_csv_columns_spec,
    validate_csv_requirements,
    validate_segmentation_mask,
    validate_upload,
)
from app.models import (
    CallLink,
    CallModerator,
    CallStatus,
    Comment,
    Contribution,
    ContributionStatus,
    DataCall,
    Event,
    User,
    utcnow,
)

TX_HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")
REVIEWABLE_STATUSES = {
    ContributionStatus.EVALUATING,
    ContributionStatus.READY,
    ContributionStatus.ERROR,
}
UNDECIDED_STATUSES = REVIEWABLE_STATUSES | {ContributionStatus.AWAITING_PAYOUT}
ACCEPTED_STATUSES = {ContributionStatus.PAID}


def apply_review_watermark(image: Image.Image, contribution_id: int) -> Image.Image:
    base = image.convert("RGBA")
    shortest_side = max(1, min(base.size))
    font_size = max(16, min(36, shortest_side // 10))
    font = ImageFont.load_default(size=font_size)
    label = f"REVIEW ONLY - NOT ACCEPTED - ID {contribution_id}"
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    watermark = ImageDraw.Draw(overlay)
    left, top, right, bottom = watermark.textbbox((0, 0), label, font=font, stroke_width=1)
    text_width = int(right - left)
    text_height = int(bottom - top)
    band_height = text_height + 18
    band_gap = max(150, base.height // 2)
    repeat_width = text_width + 36
    for index, y in enumerate(range(-band_height, base.height + band_gap, band_gap)):
        watermark.rectangle((0, y, base.width, y + band_height), fill=(115, 0, 0, 55))
        start_x = -(repeat_width // 2) if index % 2 else 8
        for x in range(start_x, base.width + repeat_width, repeat_width):
            watermark.text(
                (x, y + 8),
                label,
                font=font,
                fill=(255, 255, 255, 190),
                stroke_width=1,
                stroke_fill=(40, 0, 0, 255),
            )
    diagonal_width = max(7, base.width // 65)
    for x in range(-base.height, base.width + base.height, max(95, base.width // 4)):
        watermark.line(
            (x, 0, x + base.height, base.height),
            fill=(215, 0, 0, 28),
            width=diagonal_width,
        )
    combined = Image.alpha_composite(base, overlay)
    banner_height = max(30, min(54, base.height // 7))
    banner = ImageDraw.Draw(combined)
    banner.rectangle(
        (0, base.height - banner_height, base.width, base.height), fill=(120, 0, 0, 105)
    )
    banner.text(
        (10, base.height - banner_height + 7),
        label,
        font=font,
        fill=(255, 255, 255, 210),
        stroke_width=1,
        stroke_fill=(0, 0, 0, 220),
    )
    return combined.convert("RGB")


def encode_protected_preview(image: Image.Image, contribution_id: int) -> bytes:
    image.thumbnail((480, 480), Image.Resampling.LANCZOS)
    protected = apply_review_watermark(image, contribution_id)
    output = BytesIO()
    protected.save(output, format="JPEG", quality=40, optimize=True, subsampling=2)
    return output.getvalue()


def protected_image_preview(path: Path, contribution_id: int) -> bytes:
    with Image.open(path) as source:
        return encode_protected_preview(ImageOps.exif_transpose(source), contribution_id)


def stored_protected_image(upload_dir: Path, stored_filename: str, contribution_id: int) -> Path:
    versioned_name = f"review-v4-{Path(stored_filename).stem}-{contribution_id}.jpg"
    target = upload_dir / versioned_name
    if not target.is_file():
        original = upload_dir / stored_filename
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(protected_image_preview(original, contribution_id))
        temporary.replace(target)
    return target


class ChallengeRequest(BaseModel):
    address: str


class VerifyRequest(BaseModel):
    message: str
    signature: str


class TransactionRequest(BaseModel):
    tx_hash: str


class TopUpTransactionRequest(TransactionRequest):
    additional_slots: int


def required_remaining_liability(
    max_acceptances: int, paid_count: int, maximum_reward: int
) -> int:
    return max(0, max_acceptances - paid_count) * maximum_reward


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    app_settings.ensure_directories()
    database = Database(app_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        database.create_tables()
        yield

    app = FastAPI(title=app_settings.app_name, lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=app_settings.secret_key,
        https_only=app_settings.session_https_only,
        same_site="lax",
        max_age=60 * 60 * 8,
    )
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    templates = Jinja2Templates(directory="app/templates")
    templates.env.globals["format_token"] = format_token_amount
    templates.env.globals["unix_timestamp"] = unix_timestamp
    chain = BlockchainService(app_settings)

    app.state.settings = app_settings
    app.state.database = database
    app.state.chain = chain
    app.state.templates = templates

    def get_db() -> Generator[Session, None, None]:
        yield from database.sessions()

    def render(request: Request, name: str, **context: Any) -> HTMLResponse:
        db_value = context.pop("db", None)
        db_context = cast(Session | None, db_value if isinstance(db_value, Session) else None)
        user = current_user(request, db_context)
        linked_wallet = user.wallet_address if user and user.wallet_address.startswith("0x") else ""
        base: dict[str, Any] = {
            "request": request,
            "user": user,
            "app_name": app_settings.app_name,
            "chain_id": app_settings.chain_id,
            "escrow_address": app_settings.escrow_contract_address,
            "token_address": app_settings.token_contract_address,
            "token_symbol": app_settings.token_symbol,
            "token_decimals": app_settings.token_decimals,
            "explorer_url": app_settings.fuji_explorer_url.rstrip("/"),
            "max_upload_mb": app_settings.max_upload_bytes // (1024 * 1024),
            "linked_wallet": linked_wallet,
            "server_error": request.session.pop("error_popup", None),
        }
        base.update(context)
        return templates.TemplateResponse(request, name, base)

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
        accepted_count = sum(
            item.final_decision == "accept" for item in data_call.contributions
        )
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
        if db.get(DataCall, call_id) is None:
            raise HTTPException(status_code=404, detail="Call not found")
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

    @app.post("/calls/{call_id}/funding-tx")
    def record_funding(
        call_id: int,
        request: Request,
        payload: TransactionRequest,
        db: Session = Depends(get_db),
    ) -> dict[str, str]:
        user = require_user(request, db)
        data_call = owned_call(db, call_id, user)
        validate_tx_hash(payload.tx_hash)
        if data_call.status not in (CallStatus.DRAFT, CallStatus.FUNDING):
            raise HTTPException(status_code=409, detail="Call is not waiting for funding")
        if not user.wallet_address.startswith("0x"):
            raise HTTPException(status_code=409, detail="Link a Fuji wallet before funding")
        sender = chain.transaction_sender(payload.tx_hash) if chain.configured else None
        if chain.configured and sender is None:
            raise HTTPException(status_code=422, detail="Funding transaction was not found on Fuji")
        if sender and sender.lower() != data_call.caller.wallet_address.lower():
            raise HTTPException(
                status_code=409,
                detail="The funding wallet must match the wallet signed in to DataBounty",
            )
        data_call.funding_tx_hash = payload.tx_hash
        data_call.status = CallStatus.FUNDING
        db.add(
            Event(
                call_id=call_id,
                event_type="funding_submitted",
                message="Funding transaction submitted",
                tx_hash=payload.tx_hash,
            )
        )
        db.commit()
        refresh_chain_state(db, data_call, chain)
        return {"status": data_call.status}

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

    @app.post("/calls/{call_id}/top-up-tx")
    def record_call_top_up(
        call_id: int,
        request: Request,
        payload: TopUpTransactionRequest,
        db: Session = Depends(get_db),
    ) -> dict[str, int]:
        caller = require_user(request, db)
        data_call = owned_call(db, call_id, caller)
        if data_call.status != CallStatus.OPEN or as_utc(data_call.deadline) <= datetime.now(UTC):
            raise HTTPException(
                status_code=409, detail="Only an active call can receive more funding"
            )
        if not 1 <= payload.additional_slots <= 100_000 - data_call.max_acceptances:
            raise HTTPException(status_code=422, detail="Additional contributions are out of range")
        if not chain.configured:
            raise HTTPException(status_code=409, detail="Escrow contract is not configured")
        validate_tx_hash(payload.tx_hash)
        duplicate_tx = db.scalar(select(Event.id).where(Event.tx_hash == payload.tx_hash))
        if duplicate_tx is not None:
            raise HTTPException(status_code=409, detail="This funding transaction was already used")
        if chain.transaction_state(payload.tx_hash).state != "confirmed":
            raise HTTPException(
                status_code=409, detail="Additional funding is not confirmed on Fuji"
            )
        added_amount = payload.additional_slots * data_call.maximum_reward
        escrow_call_id = data_call.escrow_call_id or data_call.id
        if not chain.top_up_matches(
            payload.tx_hash,
            escrow_call_id,
            added_amount,
            data_call.caller.wallet_address,
        ):
            raise HTTPException(
                status_code=409,
                detail="The transaction does not match this call's additional funding",
            )

        paid_count = int(
            db.scalar(
                select(func.count(Contribution.id)).where(
                    Contribution.call_id == call_id,
                    Contribution.status == ContributionStatus.PAID,
                )
            )
            or 0
        )
        new_maximum = data_call.max_acceptances + payload.additional_slots
        required_remaining = required_remaining_liability(
            new_maximum, paid_count, data_call.maximum_reward
        )
        remaining = chain.call_remaining(
            escrow_call_id, data_call.caller.wallet_address
        )
        if remaining is None or remaining < required_remaining:
            raise HTTPException(
                status_code=409,
                detail="The confirmed escrow balance is insufficient for this expanded limit",
            )

        data_call.max_acceptances = new_maximum
        db.add(
            Event(
                call_id=call_id,
                event_type="funding_added",
                message=(
                    f"Caller funded {payload.additional_slots} additional acceptance slot(s); "
                    f"maximum is now {new_maximum}"
                ),
                tx_hash=payload.tx_hash,
            )
        )
        db.commit()
        return {"max_acceptances": new_maximum}

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
        committed_count = sum(
            item.final_decision == "accept" for item in all_contributions
        )
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

    @app.get("/api/contributions/{contribution_id}/evaluation")
    def evaluation_status(
        contribution_id: int, request: Request, db: Session = Depends(get_db)
    ) -> dict[str, str | int | None]:
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
            raise HTTPException(status_code=403, detail="Not allowed to view this evaluation")
        return {
            "status": str(contribution.status),
            "progress": max(0, min(100, contribution.evaluation_progress)),
            "stage": contribution.evaluation_stage,
            "recommendation": contribution.ai_recommendation,
        }

    @app.post("/contributions/{contribution_id}/decision")
    def decide_contribution(
        contribution_id: int,
        request: Request,
        decision: str = Form(),
        tier: str = Form("standard"),
        db: Session = Depends(get_db),
    ) -> RedirectResponse:
        user = require_user(request, db)
        contribution = db.scalar(
            select(Contribution)
            .options(selectinload(Contribution.data_call))
            .where(Contribution.id == contribution_id)
        )
        if contribution is None:
            raise HTTPException(status_code=404, detail="Contribution not found")
        if not can_review_call(db, contribution.data_call, user):
            raise HTTPException(status_code=403, detail="Only the caller or a moderator can decide")
        apply_contribution_decision(db, contribution, user, decision, tier)
        db.commit()
        return RedirectResponse(f"/contributions/{contribution.id}", status_code=303)

    @app.post("/contributions/{contribution_id}/payout-tx")
    def record_payout(
        contribution_id: int,
        request: Request,
        payload: TransactionRequest,
        db: Session = Depends(get_db),
    ) -> dict[str, str]:
        user = require_user(request, db)
        contribution = db.scalar(
            select(Contribution)
            .options(selectinload(Contribution.data_call))
            .where(Contribution.id == contribution_id)
        )
        if contribution is None:
            raise HTTPException(status_code=404, detail="Contribution not found")
        if contribution.data_call.caller_id != user.id:
            raise HTTPException(status_code=403, detail="Only the caller can submit payout")
        if contribution.status != ContributionStatus.AWAITING_PAYOUT:
            raise HTTPException(status_code=409, detail="Contribution is not awaiting payout")
        validate_tx_hash(payload.tx_hash)
        contribution.payout_tx_hash = payload.tx_hash
        db.add(
            Event(
                call_id=contribution.call_id,
                contribution_id=contribution.id,
                event_type="payout_submitted",
                message="Payout transaction submitted",
                tx_hash=payload.tx_hash,
            )
        )
        db.commit()
        refresh_payout_state(db, contribution, chain)
        return {"status": contribution.status}

    def error_response(request: Request, status_code: int, message: str):
        if (
            request.url.path.startswith("/api/")
            or request.headers.get("content-type") == "application/json"
            or "text/html" not in request.headers.get("accept", "")
        ):
            return JSONResponse({"error": {"code": status_code, "message": message}}, status_code)
        request.session["error_popup"] = message
        return RedirectResponse(error_return_path(request), status_code=303)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return error_response(request, exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(request: Request, exc: RequestValidationError):
        messages = [str(error.get("msg", "Invalid value")) for error in exc.errors()]
        message = "Invalid request: " + "; ".join(dict.fromkeys(messages))
        return error_response(request, 422, message)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, _exc: Exception):
        message = "An unexpected error occurred. Please try again."
        return error_response(request, 500, message)

    return app


def error_return_path(request: Request) -> str:
    referer = request.headers.get("referer", "")
    if referer:
        parsed = urlparse(referer)
        if parsed.netloc in {"", request.url.netloc} and parsed.path.startswith("/"):
            query = f"?{parsed.query}" if parsed.query else ""
            return f"{parsed.path}{query}"
    return "/"


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
            (
                settings.upload_dir / contribution.source_stored_filename
                if contribution.source_stored_filename
                else None
            ),
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
    if state.state == "confirmed" and chain.contribution_is_paid(
        call_id, contribution.payout_key
    ):
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
    db: Session,
    contribution: Contribution,
    reviewer: User,
    decision: str,
    tier: str,
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
        message = f"Contribution approved for payout at {tier} tier by {name}"
    db.add(
        Event(
            call_id=contribution.call_id,
            contribution_id=contribution.id,
            event_type=f"contribution_{decision}",
            message=message,
        )
    )


def editable_draft(db: Session, call_id: int, user: User) -> DataCall:
    data_call = owned_call(db, call_id, user)
    if data_call.status != CallStatus.DRAFT or data_call.funding_tx_hash is not None:
        raise HTTPException(
            status_code=409,
            detail="Only an unfunded draft call can be edited or removed",
        )
    return data_call


def parse_token_amount(value: str, decimals: int) -> int:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Reward must be a valid number") from exc
    if amount <= 0:
        raise ValueError("Reward must be positive")
    scale = Decimal(10) ** decimals
    minor = amount * scale
    if minor != minor.to_integral_value():
        raise ValueError(f"Reward supports at most {decimals} decimal places")
    return int(minor)


def format_token_amount(value: int | None, decimals: int) -> str:
    if value is None:
        return "0"
    whole = Decimal(value) / (Decimal(10) ** decimals)
    return format(whole.normalize(), "f")


def unix_timestamp(value: datetime) -> int:
    return int(as_utc(value).timestamp())


def parse_deadline(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Deadline is invalid") from exc
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def validate_call_fields(
    title: str,
    description: str,
    criteria: str,
    data_type: str,
    review_mode: str,
    standard: int,
    high: int | None,
    max_acceptances: int,
    deadline: datetime,
    ai_evaluation_prompt: str = "",
    csv_columns: str = "",
    csv_delimiter: str = "comma",
    csv_min_records: int = 1,
    csv_max_records: int | None = None,
    csv_allow_extra_columns: bool = False,
    csv_allow_missing_values: bool = False,
    csv_unique_column: str = "",
    segmentation_mode: str = "",
) -> None:
    if not 3 <= len(title.strip()) <= 120:
        raise ValueError("Title must contain 3 to 120 characters")
    if not description.strip() or not criteria.strip():
        raise ValueError("Description and acceptance criteria are required")
    if data_type not in {"image_text", "csv", "image_segmentation_text"}:
        raise ValueError("Data type is invalid")
    if review_mode not in ("manual", "ai_assisted"):
        raise ValueError("Review mode is invalid")
    if high is not None and high < standard:
        raise ValueError("High-tier reward cannot be below the standard reward")
    if not 1 <= max_acceptances <= 100_000:
        raise ValueError("Maximum acceptances must be between 1 and 100000")
    if deadline <= datetime.now(UTC):
        raise ValueError("Deadline must be in the future")
    if len(ai_evaluation_prompt.strip()) > 3000:
        raise ValueError("AI evaluation prompt cannot exceed 3000 characters")
    if data_type in {"csv", "image_segmentation_text"}:
        if review_mode != "ai_assisted":
            raise ValueError("CSV and segmentation calls require AI-assisted review")
        if not ai_evaluation_prompt.strip():
            raise ValueError("A detailed AI evaluation prompt is required for this data type")
    if data_type == "csv":
        columns = parse_csv_columns_spec(csv_columns)
        if csv_delimiter not in CSV_DELIMITERS:
            raise ValueError("CSV delimiter is invalid")
        if not 1 <= csv_min_records <= 100_000:
            raise ValueError("CSV minimum records must be between 1 and 100000")
        if csv_max_records is not None and not csv_min_records <= csv_max_records <= 100_000:
            raise ValueError("CSV maximum records must be blank or between the minimum and 100000")
        unique = csv_unique_column.strip()
        if unique and unique not in {name for name, _value_type in columns}:
            raise ValueError("CSV unique field must be one of the required fields")
    if data_type == "image_segmentation_text" and segmentation_mode not in {
        "image_seg",
        "seg_text",
        "image_seg_text",
    }:
        raise ValueError("Segmentation package mode is invalid")


def validate_tx_hash(value: str) -> None:
    if not TX_HASH.fullmatch(value):
        raise HTTPException(status_code=422, detail="Invalid transaction hash")


def parse_call_links(value: str) -> list[tuple[str, str]]:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if len(lines) > 5:
        raise ValueError("A call can contain at most five links")
    links: list[tuple[str, str]] = []
    for line in lines:
        label, separator, raw_url = line.partition("|")
        if not separator:
            raw_url = label
            label = urlparse(raw_url).netloc or "Link"
        url = raw_url.strip()
        parsed = urlparse(url)
        clean_label = label.strip()
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Links must use a complete http:// or https:// URL")
        if not 1 <= len(clean_label) <= 80 or len(url) > 500:
            raise ValueError("Link labels or URLs are too long")
        links.append((clean_label, url))
    return links


def allocate_escrow_call_id(db: Session) -> int:
    """Return an ID that remains unique even when the local SQLite database is reset."""
    for _ in range(5):
        candidate = secrets.randbelow(2**63 - 1) + 1
        in_use = db.scalar(select(DataCall.id).where(DataCall.escrow_call_id == candidate))
        if in_use is None:
            return candidate
    raise RuntimeError("Could not allocate a unique escrow call ID")


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


app = create_app()
