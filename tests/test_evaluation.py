from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from app.config import Settings
from app.evaluation import _evaluate_image, _evaluate_text, evaluate_file, validate_upload


def test_validate_image_and_text() -> None:
    image_bytes = BytesIO()
    Image.new("RGB", (20, 10), "green").save(image_bytes, format="PNG")
    image = validate_upload(image_bytes.getvalue(), "image", "application/octet-stream")
    assert image.media_type == "image/png"
    assert image.size_bytes > 0

    text = validate_upload(b"a useful text sample", "text", "text/plain")
    assert text.media_type == "text/plain"
    assert len(text.sha256) == 64


@pytest.mark.parametrize("content", [b"", b" \n\t", b"\xff"])
def test_invalid_text_is_rejected(content: bytes) -> None:
    with pytest.raises(ValueError):
        validate_upload(content, "text", "text/plain")


def test_text_model_result_is_structured(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    contribution = tmp_path / "matching.txt"
    contribution.write_text("A clear and readable red stop sign.", encoding="utf-8")

    def fake_pipeline(_content, *, candidate_labels, hypothesis_template):
        assert hypothesis_template
        return {"labels": candidate_labels, "scores": [0.91, 0.09]}

    monkeypatch.setattr("app.evaluation._model_pipeline", lambda *_args: fake_pipeline)
    result = _evaluate_text(contribution, "a readable street sign", "test-text-model")

    assert result.recommendation == "accept"
    assert result.tier == "high"
    assert result.model_name == "test-text-model"


def test_image_model_can_reject_unrelated_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    contribution = tmp_path / "unrelated.png"
    Image.new("RGB", (20, 20), "blue").save(contribution)

    def fake_pipeline(_path, *, candidate_labels):
        return [
            {"label": candidate_labels[1], "score": 0.9},
            {"label": candidate_labels[0], "score": 0.1},
        ]

    monkeypatch.setattr("app.evaluation._model_pipeline", lambda *_args: fake_pipeline)
    result = _evaluate_image(contribution, "a readable street sign", "test-image-model")

    assert result.recommendation == "reject"
    assert result.tier == "standard"


def test_disabled_model_reports_fallback_progress(tmp_path) -> None:
    contribution = tmp_path / "sample.txt"
    contribution.write_text("A readable sign", encoding="utf-8")
    updates: list[tuple[int, str]] = []

    result = evaluate_file(
        contribution,
        "text",
        "a readable street sign",
        Settings(enable_hf_models=False),
        lambda percent, stage: updates.append((percent, stage)),
    )

    assert updates == [(10, "Checking contribution"), (90, "Using safe fallback")]
    assert result.model_name == "deterministic-fallback"
