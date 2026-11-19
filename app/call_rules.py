from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evaluation import CSV_DELIMITERS, parse_csv_columns_spec
from app.models import DataCall

TX_HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")


def parse_token_amount(value: str, decimals: int) -> int:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Reward must be a valid number") from exc
    if amount <= 0:
        raise ValueError("Reward must be positive")
    minor = amount * (Decimal(10) ** decimals)
    if minor != minor.to_integral_value():
        raise ValueError(f"Reward supports at most {decimals} decimal places")
    return int(minor)


def format_token_amount(value: int | None, decimals: int) -> str:
    if value is None:
        return "0"
    return format((Decimal(value) / (Decimal(10) ** decimals)).normalize(), "f")


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


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
    del csv_allow_extra_columns, csv_allow_missing_values
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
            raw_url, label = label, urlparse(label).netloc or "Link"
        url, clean_label = raw_url.strip(), label.strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Links must use a complete http:// or https:// URL")
        if not 1 <= len(clean_label) <= 80 or len(url) > 500:
            raise ValueError("Link labels or URLs are too long")
        links.append((clean_label, url))
    return links


def allocate_escrow_call_id(db: Session) -> int:
    for _ in range(5):
        candidate = secrets.randbelow(2**63 - 1) + 1
        if db.scalar(select(DataCall.id).where(DataCall.escrow_call_id == candidate)) is None:
            return candidate
    raise RuntimeError("Could not allocate a unique escrow call ID")


def required_remaining_liability(max_acceptances: int, paid_count: int, maximum_reward: int) -> int:
    return max(0, max_acceptances - paid_count) * maximum_reward
