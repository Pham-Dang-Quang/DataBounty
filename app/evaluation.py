from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

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


ProgressReporter = Callable[[int, str], None]


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
    path: Path,
    data_type: str,
    criteria: str,
    settings: Settings,
    report_progress: ProgressReporter | None = None,
) -> EvaluationResult:
    """Run the configured model, falling back to an explicit manual-review recommendation."""
    report = report_progress or (lambda _percent, _stage: None)
    report(10, "Checking contribution")
    if not settings.enable_hf_models:
        report(90, "Using safe fallback")
        return _safe_fallback(path, data_type, criteria, "models disabled")
    try:
        if data_type == "text":
            return _evaluate_text(
                path, criteria, settings.text_model, report, settings.hf_hub_cache_path
            )
        return _evaluate_image(
            path, criteria, settings.image_model, report, settings.hf_hub_cache_path
        )
    except Exception as exc:
        report(90, "Model unavailable; using safe fallback")
        return _safe_fallback(path, data_type, criteria, type(exc).__name__)


def _evaluate_text(
    path: Path,
    criteria: str,
    model_name: str,
    report: ProgressReporter | None = None,
    cache_dir: Path | None = None,
) -> EvaluationResult:
    update = report or (lambda _percent, _stage: None)
    content = path.read_text(encoding="utf-8")[:4000]
    update(30, "Loading text model")
    classifier = _model_pipeline("zero-shot-classification", model_name, cache_dir)
    update(60, "Comparing text with criteria")
    output = classifier(
        content,
        candidate_labels=[criteria[:300], "unrelated to the requested data"],
        hypothesis_template="This contribution is {}.",
    )
    labels = [str(label) for label in output["labels"]]
    scores = [float(score) for score in output["scores"]]
    relevance = dict(zip(labels, scores, strict=True)).get(criteria[:300], 0.0)
    update(90, "Formatting recommendation")
    return _result_from_relevance(
        relevance, model_name, f"Zero-shot relevance score: {relevance:.0%}."
    )


def _evaluate_image(
    path: Path,
    criteria: str,
    model_name: str,
    report: ProgressReporter | None = None,
    cache_dir: Path | None = None,
) -> EvaluationResult:
    update = report or (lambda _percent, _stage: None)
    update(30, "Loading image model")
    classifier = _model_pipeline("zero-shot-image-classification", model_name, cache_dir)
    update(60, "Comparing image with criteria")
    output = classifier(str(path), candidate_labels=[criteria[:200], "unrelated or unusable image"])
    relevance = next(
        (float(item["score"]) for item in output if item["label"] == criteria[:200]),
        0.0,
    )
    update(90, "Formatting recommendation")
    return _result_from_relevance(
        relevance, model_name, f"Image-to-criteria similarity: {relevance:.0%}."
    )


@lru_cache(maxsize=4)
def _model_pipeline(task: str, model_name: str, cache_dir: Path | None) -> Any:
    """Load each configured model once per process instead of once per contribution."""
    pipeline = _pipeline_factory()
    model_kwargs = {"cache_dir": str(cache_dir.resolve())} if cache_dir else None
    if task == "zero-shot-classification":
        return pipeline(
            "zero-shot-classification",
            model=model_name,
            device=-1,
            model_kwargs=model_kwargs,
        )
    if task == "zero-shot-image-classification":
        return pipeline(
            "zero-shot-image-classification",
            model=model_name,
            device=-1,
            model_kwargs=model_kwargs,
        )
    raise ValueError(f"Unsupported model task: {task}")


def _pipeline_factory() -> Any:
    from transformers import pipeline

    return pipeline


def _result_from_relevance(score: float, model_name: str, explanation: str) -> EvaluationResult:
    if score >= 0.65:
        recommendation = "accept"
    elif score <= 0.35:
        recommendation = "reject"
    else:
        recommendation = "unsure"
    tier = "high" if recommendation == "accept" and score >= 0.85 else "standard"
    return EvaluationResult(
        recommendation,
        tier,
        f"{explanation} Caller review is required.",
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
