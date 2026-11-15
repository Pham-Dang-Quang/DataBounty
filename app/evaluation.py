from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.config import Settings


@dataclass(frozen=True)
class ValidatedUpload:
    sha256: str
    media_type: str
    size_bytes: int


@dataclass(frozen=True)
class EvaluationResult:
    recommendation: str
    tier: str
    explanation: str
    model_name: str


def validate_upload(content: bytes, data_type: str, declared_type: str | None) -> ValidatedUpload:
    if not content:
        raise ValueError("The uploaded file is empty")

    if data_type == "text":
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Text contributions must be UTF-8") from exc
        if not text.strip():
            raise ValueError("The text file contains no readable content")
        media_type = "text/plain"
    elif data_type == "image":
        try:
            from io import BytesIO

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


def evaluate_file(
    path: Path, data_type: str, criteria: str, settings: Settings
) -> EvaluationResult:
    """Run the configured model, falling back to an explicit manual-review recommendation."""
    if not settings.enable_hf_models:
        return _safe_fallback(path, data_type, criteria, "models disabled")
    try:
        if data_type == "text":
            return _evaluate_text(path, criteria, settings.text_model)
        return _evaluate_image(path, criteria, settings.image_model)
    except Exception as exc:
        return _safe_fallback(path, data_type, criteria, type(exc).__name__)


def _evaluate_text(path: Path, criteria: str, model_name: str) -> EvaluationResult:
    from transformers import pipeline

    content = path.read_text(encoding="utf-8")[:4000]
    classifier = pipeline("zero-shot-classification", model=model_name)
    output = classifier(
        content,
        candidate_labels=[criteria[:300], "unrelated to the requested data"],
        hypothesis_template="This contribution is {}.",
    )
    score = float(output["scores"][0])
    matched = output["labels"][0] == criteria[:300]
    recommendation = "accept" if matched and score >= 0.65 else "unsure"
    tier = "high" if matched and score >= 0.85 else "standard"
    return EvaluationResult(
        recommendation,
        tier,
        f"Zero-shot relevance score: {score:.0%}. Caller review is required.",
        model_name,
    )


def _evaluate_image(path: Path, criteria: str, model_name: str) -> EvaluationResult:
    from transformers import pipeline

    classifier = pipeline("zero-shot-image-classification", model=model_name)
    output = classifier(str(path), candidate_labels=[criteria[:200], "unrelated or unusable image"])
    best = output[0]
    score = float(best["score"])
    matched = best["label"] == criteria[:200]
    recommendation = "accept" if matched and score >= 0.65 else "unsure"
    tier = "high" if matched and score >= 0.85 else "standard"
    return EvaluationResult(
        recommendation,
        tier,
        f"Image-to-criteria similarity: {score:.0%}. Caller review is required.",
        model_name,
    )


def _safe_fallback(path: Path, data_type: str, criteria: str, reason: str) -> EvaluationResult:
    if data_type == "text":
        words = set(path.read_text(encoding="utf-8").lower().split())
        criteria_words = {word for word in criteria.lower().split() if len(word) >= 4}
        overlap = len(words & criteria_words)
        explanation = (
            f"Model unavailable ({reason}). Basic text check found {overlap} criteria keyword(s); "
            "manual judgment is required."
        )
    else:
        with Image.open(path) as image:
            width, height = image.size
        explanation = (
            f"Model unavailable ({reason}). Image is readable at {width}×{height}; "
            "manual judgment is required."
        )
    return EvaluationResult("unsure", "standard", explanation, "deterministic-fallback")
