from __future__ import annotations

import csv
import hashlib
import math
from dataclasses import dataclass
from datetime import date
from io import BytesIO, StringIO
from typing import cast

from PIL import Image, ImageChops, ImageStat, UnidentifiedImageError

CSV_TYPES = {"string", "integer", "number", "boolean", "date"}
CSV_DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t"}
SEGMENTATION_PALETTE_COLORS = 16
MAX_SEGMENTATION_COLOR_ERROR = 18.0
MAX_SEGMENTATION_BOUNDARY_RATIO = 0.45
MIN_SEGMENTATION_REGION_FRACTION = 0.001
MIN_SEGMENTATION_STRONG_BOUNDARY_RATIO = 0.001
MAX_SEGMENTATION_ASPECT_RATIO_DIFFERENCE = 0.005


@dataclass(frozen=True)
class ValidatedUpload:
    sha256: str
    media_type: str
    size_bytes: int


def parse_csv_columns_spec(spec: str) -> list[tuple[str, str]]:
    columns: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw_line in spec.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        name, separator, raw_type = line.partition(":")
        name = name.strip()
        value_type = raw_type.strip().lower()
        if not separator or not name or value_type not in CSV_TYPES:
            raise ValueError(
                "Each CSV field must use name:type with type string, integer, number, "
                "boolean, or date"
            )
        if name in seen:
            raise ValueError(f"CSV field '{name}' is duplicated")
        seen.add(name)
        columns.append((name, value_type))
    if not columns:
        raise ValueError("At least one required CSV field is needed")
    return columns


def validate_csv_requirements(
    content: bytes,
    columns_spec: str,
    delimiter_name: str,
    min_records: int,
    max_records: int | None,
    allow_extra_columns: bool,
    allow_missing_values: bool,
    unique_column: str | None,
) -> str:
    columns = parse_csv_columns_spec(columns_spec)
    delimiter = CSV_DELIMITERS.get(delimiter_name)
    if delimiter is None:
        raise ValueError("CSV delimiter is invalid")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV contributions must be UTF-8") from exc
    try:
        rows = list(csv.reader(StringIO(text), delimiter=delimiter))
    except csv.Error as exc:
        raise ValueError("The file is not valid CSV") from exc
    if not rows or not rows[0]:
        raise ValueError("CSV must contain a header row")
    header = [cell.strip() for cell in rows[0]]
    if any(not cell for cell in header) or len(set(header)) != len(header):
        raise ValueError("CSV header fields must be non-empty and unique")
    if any(len(row) != len(header) for row in rows[1:]):
        raise ValueError("All CSV rows must contain the same number of columns as the header")
    required_names = [name for name, _value_type in columns]
    missing_columns = [name for name in required_names if name not in header]
    if missing_columns:
        raise ValueError(f"CSV is missing required fields: {', '.join(missing_columns)}")
    extra_columns = [name for name in header if name not in required_names]
    if extra_columns and not allow_extra_columns:
        raise ValueError(f"CSV contains unexpected fields: {', '.join(extra_columns)}")
    records = rows[1:]
    if len(records) < min_records:
        raise ValueError(f"CSV must contain at least {min_records} records")
    if max_records is not None and len(records) > max_records:
        raise ValueError(f"CSV must contain at most {max_records} records")

    positions = {name: header.index(name) for name in required_names}
    unique_values: set[str] = set()
    for row_number, row in enumerate(records, start=2):
        for name, value_type in columns:
            value = row[positions[name]].strip()
            if not value:
                if not allow_missing_values:
                    raise ValueError(f"CSV row {row_number} has an empty '{name}' value")
                continue
            _validate_csv_value(value, value_type, row_number, name)
        if unique_column:
            value = row[positions[unique_column]].strip()
            if value and value in unique_values:
                raise ValueError(
                    f"CSV row {row_number} duplicates '{unique_column}' value '{value}'"
                )
            if value:
                unique_values.add(value)
    return (
        f"Deterministic CSV validation passed: {len(records)} records, "
        f"{len(header)} fields, delimiter {delimiter_name}."
    )


def _validate_csv_value(value: str, value_type: str, row: int, field: str) -> None:
    try:
        if value_type == "integer":
            int(value)
        elif value_type == "number":
            if not math.isfinite(float(value)):
                raise ValueError
        elif value_type == "boolean":
            if value.lower() not in {"true", "false", "1", "0", "yes", "no"}:
                raise ValueError
        elif value_type == "date":
            date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"CSV row {row} field '{field}' must be {value_type}") from exc


def validate_segmentation_mask(content: bytes, source_content: bytes | None = None) -> str:
    """Require palette-like regions while tolerating mild shading and edge smoothing."""
    try:
        with Image.open(BytesIO(content)) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            sample = rgb.copy()
            sample.thumbnail((512, 512), Image.Resampling.LANCZOS)
            grouped = sample.quantize(
                colors=SEGMENTATION_PALETTE_COLORS,
                method=Image.Quantize.MEDIANCUT,
                dither=Image.Dither.NONE,
            )
            grouped_colors = grouped.getcolors() or []
            sample_pixels = sample.width * sample.height
            meaningful_colors = sum(
                count / sample_pixels >= MIN_SEGMENTATION_REGION_FRACTION
                for count, _color in grouped_colors
            )
            if meaningful_colors < 2:
                raise ValueError(
                    "Segmentation masks must contain at least two meaningful filled color regions"
                )
            reconstructed = grouped.convert("RGB")
            color_error = sum(ImageStat.Stat(ImageChops.difference(sample, reconstructed)).mean) / 3
            if color_error > MAX_SEGMENTATION_COLOR_ERROR:
                raise ValueError(
                    "The segmentation mask has too much continuous shading or photographic "
                    "detail; use distinguishable filled color regions"
                )
            strong_boundary_ratio = _strong_color_boundary_ratio(sample)
            if strong_boundary_ratio < MIN_SEGMENTATION_STRONG_BOUNDARY_RATIO:
                raise ValueError(
                    "The segmentation mask does not contain distinct filled region boundaries"
                )
            boundary_ratio = _segmentation_boundary_ratio(grouped)
            if boundary_ratio > MAX_SEGMENTATION_BOUNDARY_RATIO:
                raise ValueError(
                    "The segmentation mask is too visually complex or noisy; use simple "
                    "flat-color filled regions"
                )
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("The segmentation mask is not a readable image") from exc

    aspect_summary = "."
    if source_content is not None:
        try:
            with Image.open(BytesIO(source_content)) as source:
                source_width, source_height = source.size
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("The source image is not readable") from exc
        difference = abs(width / height - source_width / source_height) / (
            source_width / source_height
        )
        if difference > MAX_SEGMENTATION_ASPECT_RATIO_DIFFERENCE:
            raise ValueError(
                "The segmentation mask and source image must have the same aspect ratio; "
                "their resolutions may differ"
            )
        aspect_summary = (
            f", aspect ratio matches {source_width}×{source_height} at a different allowed "
            f"resolution ({difference:.2%} difference)."
        )
    return (
        f"Segmentation pre-check passed: {width}×{height}, {meaningful_colors} palette groups, "
        f"average color variation {color_error:.1f}, {boundary_ratio:.1%} boundary complexity"
        f"{aspect_summary}"
    )


def _segmentation_boundary_ratio(image: Image.Image) -> float:
    sample = image.copy()
    sample.thumbnail((512, 512), Image.Resampling.NEAREST)
    pixels = sample.load()
    if pixels is None:
        return 1.0
    width, height = sample.size
    transitions = comparisons = 0
    for y in range(height):
        for x in range(width):
            current = pixels[x, y]
            if x:
                transitions += current != pixels[x - 1, y]
                comparisons += 1
            if y:
                transitions += current != pixels[x, y - 1]
                comparisons += 1
    return transitions / comparisons if comparisons else 0.0


def _strong_color_boundary_ratio(image: Image.Image) -> float:
    pixels = image.load()
    if pixels is None:
        return 0.0
    width, height = image.size
    strong_boundaries = comparisons = 0
    for y in range(height):
        for x in range(width):
            current = cast(tuple[int, int, int], pixels[x, y])
            for adjacent in (
                cast(tuple[int, int, int], pixels[x - 1, y]) if x else None,
                cast(tuple[int, int, int], pixels[x, y - 1]) if y else None,
            ):
                if adjacent is not None:
                    strong_boundaries += (
                        max(abs(current[channel] - adjacent[channel]) for channel in range(3)) > 32
                    )
                    comparisons += 1
    return strong_boundaries / comparisons if comparisons else 0.0


def validate_upload(content: bytes, data_type: str, declared_type: str | None) -> ValidatedUpload:
    if not content:
        raise ValueError("The uploaded file is empty")
    if data_type == "csv":
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("CSV contributions must be UTF-8") from exc
        if not text.strip():
            raise ValueError("The uploaded file is empty")
        media_type = "text/csv"
    elif data_type in {"image", "image_text", "image_segmentation_text"}:
        try:
            with Image.open(BytesIO(content)) as image:
                image.verify()
                detected = (image.format or "").lower()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("The file is not a readable image") from exc
        allowed = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
        if detected not in allowed:
            raise ValueError("Only JPEG, PNG, and WebP images are supported")
        media_type = allowed[detected]
    else:
        raise ValueError("Unsupported call data type")
    return ValidatedUpload(
        sha256=hashlib.sha256(content).hexdigest(),
        media_type=media_type if declared_type != media_type else declared_type,
        size_bytes=len(content),
    )
