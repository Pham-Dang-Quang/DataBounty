from __future__ import annotations

import re
import uuid
from collections.abc import Generator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from starlette.middleware.sessions import SessionMiddleware

from app.auth import create_challenge, verify_challenge
from app.blockchain import BlockchainService
from app.config import Settings, get_settings
from app.db import Database
from app.evaluation import evaluate_file, validate_upload
from app.models import (
    CallStatus,
    Contribution,
    ContributionStatus,
    DataCall,
    Event,
    User,
    utcnow,
)

TX_HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")


class ChallengeRequest(BaseModel):
    address: str


class VerifyRequest(BaseModel):
    message: str
    signature: str


class TransactionRequest(BaseModel):
    tx_hash: str


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
            raise HTTPException(status_code=401, detail="Connect and sign in with a wallet")
        return user

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
        calls = db.scalars(
            select(DataCall)
            .where(DataCall.status == CallStatus.OPEN)
            .order_by(DataCall.created_at.desc())
        ).all()
        user = current_user(request, db)
        own_calls: Sequence[DataCall] = []
        if user:
            own_calls = db.scalars(
                select(DataCall)
                .where(DataCall.caller_id == user.id)
                .order_by(DataCall.created_at.desc())
            ).all()
        return render(request, "home.html", db=db, calls=calls, own_calls=own_calls)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/auth/challenge")
    def auth_challenge(payload: ChallengeRequest, db: Session = Depends(get_db)) -> dict[str, str]:
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
            user = verify_challenge(db, payload.message, payload.signature)
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
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        data_call = DataCall(
            caller_id=user.id,
            title=title.strip(),
            description=description.strip(),
            data_type=data_type,
            acceptance_criteria=acceptance_criteria.strip(),
            review_mode=review_mode,
            standard_reward=standard,
            high_reward=high,
            max_acceptances=max_acceptances,
            deadline=parsed_deadline,
        )
        db.add(data_call)
        db.flush()
        data_call.escrow_call_id = data_call.id
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
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        data_call.title = title.strip()
        data_call.description = description.strip()
        data_call.data_type = data_type
        data_call.acceptance_criteria = acceptance_criteria.strip()
        data_call.review_mode = review_mode
        data_call.standard_reward = standard
        data_call.high_reward = high
        data_call.max_acceptances = max_acceptances
        data_call.deadline = parsed_deadline
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
            .options(selectinload(DataCall.caller), selectinload(DataCall.contributions))
            .where(DataCall.id == call_id)
        )
        if data_call is None:
            raise HTTPException(status_code=404, detail="Call not found")
        refresh_chain_state(db, data_call, chain)
        events = db.scalars(
            select(Event).where(Event.call_id == call_id).order_by(Event.created_at.desc())
        ).all()
        return render(request, "call_detail.html", db=db, data_call=data_call, events=events)

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

        extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(
            validated.media_type, ".txt"
        )
        stored_filename = f"{uuid.uuid4().hex}{extension}"
        path = app_settings.upload_dir / stored_filename
        path.write_bytes(content)
        contribution = Contribution(
            call_id=call_id,
            contributor_id=user.id,
            stored_filename=stored_filename,
            original_filename=Path(contribution_file.filename or "contribution").name[:255],
            sha256=validated.sha256,
            media_type=validated.media_type,
            size_bytes=validated.size_bytes,
            status=(
                ContributionStatus.EVALUATING
                if data_call.review_mode == "ai_assisted"
                else ContributionStatus.READY
            ),
        )
        db.add(contribution)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            path.unlink(missing_ok=True)
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

    @app.get("/calls/{call_id}/review", response_class=HTMLResponse)
    def review_queue(call_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
        user = require_user(request, db)
        data_call = owned_call(db, call_id, user)
        contributions = db.scalars(
            select(Contribution)
            .options(selectinload(Contribution.contributor))
            .where(Contribution.call_id == call_id)
            .order_by(Contribution.created_at.asc())
        ).all()
        return render(
            request,
            "review_queue.html",
            db=db,
            data_call=data_call,
            contributions=contributions,
        )

    @app.get("/contributions/{contribution_id}", response_class=HTMLResponse)
    def contribution_detail(
        contribution_id: int, request: Request, db: Session = Depends(get_db)
    ) -> HTMLResponse:
        user = require_user(request, db)
        contribution = db.scalar(
            select(Contribution)
            .options(selectinload(Contribution.data_call), selectinload(Contribution.contributor))
            .where(Contribution.id == contribution_id)
        )
        if contribution is None:
            raise HTTPException(status_code=404, detail="Contribution not found")
        if user.id not in (contribution.contributor_id, contribution.data_call.caller_id):
            raise HTTPException(status_code=403, detail="Not allowed to view this contribution")
        refresh_payout_state(db, contribution, chain)
        return render(request, "contribution_detail.html", db=db, contribution=contribution)

    @app.get("/contributions/{contribution_id}/file")
    def contribution_file(
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
        if user.id not in (contribution.contributor_id, contribution.data_call.caller_id):
            raise HTTPException(status_code=403, detail="Not allowed to read this file")
        return FileResponse(
            app_settings.upload_dir / contribution.stored_filename,
            media_type=contribution.media_type,
            filename=contribution.original_filename,
        )

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
        if contribution.data_call.caller_id != user.id:
            raise HTTPException(status_code=403, detail="Only the caller can decide")
        if contribution.status not in (
            ContributionStatus.READY,
            ContributionStatus.ERROR,
        ):
            raise HTTPException(status_code=409, detail="Contribution cannot be decided now")
        if decision not in ("accept", "reject"):
            raise HTTPException(status_code=422, detail="Invalid decision")

        contribution.final_decision = decision
        contribution.reviewed_at = utcnow()
        if decision == "reject":
            contribution.status = ContributionStatus.REJECTED
            contribution.final_tier = None
            contribution.reward_amount = None
            message = "Contribution rejected by caller"
        else:
            if tier not in ("standard", "high"):
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
                raise HTTPException(status_code=409, detail="The acceptance limit has been reached")
            contribution.final_tier = tier
            contribution.reward_amount = (
                contribution.data_call.high_reward
                if tier == "high"
                else contribution.data_call.standard_reward
            )
            contribution.status = ContributionStatus.AWAITING_PAYOUT
            message = f"Contribution accepted at {tier} tier"
        db.add(
            Event(
                call_id=contribution.call_id,
                contribution_id=contribution.id,
                event_type=f"contribution_{decision}",
                message=message,
            )
        )
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

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        if (
            request.url.path.startswith("/api/")
            or request.headers.get("content-type") == "application/json"
        ):
            return JSONResponse(
                {"error": {"code": exc.status_code, "message": exc.detail}}, exc.status_code
            )
        return templates.TemplateResponse(
            request,
            "error.html",
            {"request": request, "status": exc.status_code, "message": exc.detail},
            status_code=exc.status_code,
        )

    return app


def evaluate_contribution(database: Database, settings: Settings, contribution_id: int) -> None:
    with database.session_factory() as db:
        contribution = db.scalar(
            select(Contribution)
            .options(selectinload(Contribution.data_call))
            .where(Contribution.id == contribution_id)
        )
        if contribution is None or contribution.status != ContributionStatus.EVALUATING:
            return
        result = evaluate_file(
            settings.upload_dir / contribution.stored_filename,
            contribution.data_call.data_type,
            contribution.data_call.acceptance_criteria,
            settings,
        )
        contribution.ai_recommendation = result.recommendation
        contribution.ai_tier = result.tier
        contribution.ai_explanation = result.explanation
        contribution.model_name = result.model_name
        contribution.status = ContributionStatus.READY
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
    if state.state == "confirmed" and chain.contribution_is_paid(call_id, contribution.id):
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
) -> None:
    if not 3 <= len(title.strip()) <= 120:
        raise ValueError("Title must contain 3 to 120 characters")
    if not description.strip() or not criteria.strip():
        raise ValueError("Description and acceptance criteria are required")
    if data_type not in ("image", "text"):
        raise ValueError("Data type must be image or text")
    if review_mode not in ("manual", "ai_assisted"):
        raise ValueError("Review mode is invalid")
    if high is not None and high < standard:
        raise ValueError("High-tier reward cannot be below the standard reward")
    if not 1 <= max_acceptances <= 100:
        raise ValueError("Maximum acceptances must be between 1 and 100")
    if deadline <= datetime.now(UTC):
        raise ValueError("Deadline must be in the future")


def validate_tx_hash(value: str) -> None:
    if not TX_HASH.fullmatch(value):
        raise HTTPException(status_code=422, detail="Invalid transaction hash")


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


app = create_app()
