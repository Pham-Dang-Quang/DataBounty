from __future__ import annotations

import secrets
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class CallStatus(StrEnum):
    DRAFT = "draft"
    FUNDING = "funding"
    OPEN = "open"
    CLOSED = "closed"


class ContributionStatus(StrEnum):
    EVALUATING = "evaluating"
    READY = "ready_for_review"
    REJECTED = "rejected"
    AWAITING_PAYOUT = "awaiting_payout"
    PAID = "paid"
    ERROR = "evaluation_error"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_address: Mapped[str] = mapped_column(String(42), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(300))
    display_name: Mapped[str | None] = mapped_column(String(80))
    bio: Mapped[str | None] = mapped_column(Text)
    profile_image: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthNonce(Base):
    __tablename__ = "auth_nonces"

    id: Mapped[int] = mapped_column(primary_key=True)
    wallet_address: Mapped[str] = mapped_column(String(42), index=True)
    nonce_hash: Mapped[str] = mapped_column(String(64), unique=True)
    message: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DataCall(Base):
    __tablename__ = "data_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    caller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    data_type: Mapped[str] = mapped_column(String(30))
    acceptance_criteria: Mapped[str] = mapped_column(Text)
    ai_evaluation_prompt: Mapped[str | None] = mapped_column(Text)
    csv_columns: Mapped[str | None] = mapped_column(Text)
    csv_delimiter: Mapped[str | None] = mapped_column(String(20))
    csv_min_records: Mapped[int | None]
    csv_max_records: Mapped[int | None]
    csv_allow_extra_columns: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    csv_allow_missing_values: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    csv_unique_column: Mapped[str | None] = mapped_column(String(120))
    segmentation_mode: Mapped[str | None] = mapped_column(String(30))
    review_mode: Mapped[str] = mapped_column(String(20))
    standard_reward: Mapped[int] = mapped_column(BigInteger)
    high_reward: Mapped[int | None] = mapped_column(BigInteger)
    max_acceptances: Mapped[int]
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default=CallStatus.DRAFT)
    escrow_call_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    funding_tx_hash: Mapped[str | None] = mapped_column(String(66), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    caller: Mapped[User] = relationship()
    contributions: Mapped[list[Contribution]] = relationship(back_populates="data_call")
    links: Mapped[list[CallLink]] = relationship(
        back_populates="data_call", cascade="all, delete-orphan"
    )
    comments: Mapped[list[Comment]] = relationship(
        back_populates="data_call", cascade="all, delete-orphan"
    )
    moderator_links: Mapped[list[CallModerator]] = relationship(
        back_populates="data_call", cascade="all, delete-orphan"
    )

    @property
    def maximum_reward(self) -> int:
        return self.high_reward or self.standard_reward

    @property
    def required_budget(self) -> int:
        return self.maximum_reward * self.max_acceptances


class Contribution(Base):
    __tablename__ = "contributions"
    __table_args__ = (UniqueConstraint("call_id", "sha256", name="uq_call_file_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("data_calls.id"), index=True)
    contributor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    stored_filename: Mapped[str] = mapped_column(String(80), unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    media_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    companion_text: Mapped[str | None] = mapped_column(Text)
    source_stored_filename: Mapped[str | None] = mapped_column(String(80), unique=True)
    source_original_filename: Mapped[str | None] = mapped_column(String(255))
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    source_media_type: Mapped[str | None] = mapped_column(String(100))
    source_size_bytes: Mapped[int | None]
    validation_summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default=ContributionStatus.EVALUATING)
    evaluation_progress: Mapped[int] = mapped_column(default=0, server_default="0")
    evaluation_stage: Mapped[str] = mapped_column(
        String(120), default="Queued for evaluation", server_default="Queued for evaluation"
    )
    ai_recommendation: Mapped[str | None] = mapped_column(String(20))
    ai_tier: Mapped[str | None] = mapped_column(String(20))
    ai_explanation: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(200))
    final_decision: Mapped[str | None] = mapped_column(String(20))
    final_tier: Mapped[str | None] = mapped_column(String(20))
    reward_amount: Mapped[int | None] = mapped_column(BigInteger)
    payout_key: Mapped[str] = mapped_column(
        String(66), unique=True, default=lambda: f"0x{secrets.token_hex(32)}"
    )
    payout_tx_hash: Mapped[str | None] = mapped_column(String(66), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    data_call: Mapped[DataCall] = relationship(back_populates="contributions")
    contributor: Mapped[User] = relationship(foreign_keys=[contributor_id])
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewer_id])


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("data_calls.id"), index=True)
    contribution_id: Mapped[int | None] = mapped_column(ForeignKey("contributions.id"))
    event_type: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(String(300))
    tx_hash: Mapped[str | None] = mapped_column(String(66))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CallLink(Base):
    __tablename__ = "call_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("data_calls.id"), index=True)
    label: Mapped[str] = mapped_column(String(80))
    url: Mapped[str] = mapped_column(String(500))

    data_call: Mapped[DataCall] = relationship(back_populates="links")


class CallModerator(Base):
    __tablename__ = "call_moderators"
    __table_args__ = (UniqueConstraint("call_id", "user_id", name="uq_call_moderator"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("data_calls.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    data_call: Mapped[DataCall] = relationship(back_populates="moderator_links")
    user: Mapped[User] = relationship()


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("data_calls.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("comments.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    data_call: Mapped[DataCall] = relationship(back_populates="comments")
    author: Mapped[User] = relationship()
    parent: Mapped[Comment | None] = relationship(
        remote_side="Comment.id", back_populates="replies"
    )
    replies: Mapped[list[Comment]] = relationship(back_populates="parent")
