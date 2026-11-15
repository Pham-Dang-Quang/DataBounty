from __future__ import annotations

import os
from io import BytesIO

import pytest
from PIL import Image

from app.config import Settings
from app.evaluation import (
    _evaluate_image,
    _evaluate_text,
    _model_pipeline,
    evaluate_file,
    validate_upload,
)


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
    model_cache = tmp_path / "model-cache"
    loaded_with: list[tuple[str, str, object]] = []

    def fake_pipeline(_content, *, candidate_labels, hypothesis_template):
        assert hypothesis_template
        return {"labels": candidate_labels, "scores": [0.91, 0.09]}

    def fake_loader(task, model_name, cache_dir):
        loaded_with.append((task, model_name, cache_dir))
        return fake_pipeline

    monkeypatch.setattr("app.evaluation._model_pipeline", fake_loader)
    result = _evaluate_text(
        contribution,
        "a readable street sign",
        "test-text-model",
        cache_dir=model_cache,
    )

    assert result.recommendation == "accept"
    assert result.tier == "high"
    assert result.model_name == "test-text-model"
    assert loaded_with == [("zero-shot-classification", "test-text-model", model_cache)]


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


def test_enabled_model_cache_environment_is_created(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cache_dir = tmp_path / "chosen-model-cache"
    hf_home = cache_dir / "hf-home"
    hf_hub = cache_dir / "hf-hub"
    transformers_cache = cache_dir / "transformers"
    torch_home = cache_dir / "torch"
    temporary = cache_dir / "tmp"
    environment_names = (
        "HF_HOME",
        "HF_HUB_CACHE",
        "TRANSFORMERS_CACHE",
        "TORCH_HOME",
        "TMPDIR",
        "TEMP",
        "TMP",
    )
    for name in environment_names:
        monkeypatch.setenv(name, "before-test")
    settings = Settings(
        enable_hf_models=True,
        upload_dir=tmp_path / "uploads",
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        model_cache_dir=cache_dir,
        hf_home=hf_home,
        hf_hub_cache=hf_hub,
        transformers_cache=transformers_cache,
        torch_home=torch_home,
        tmpdir=temporary,
    )

    settings.ensure_directories()

    for directory in (
        cache_dir,
        hf_home,
        hf_hub,
        transformers_cache,
        torch_home,
        temporary,
    ):
        assert directory.is_dir()
    assert os.environ["HF_HOME"] == str(hf_home.resolve())
    assert os.environ["HF_HUB_CACHE"] == str(hf_hub.resolve())
    assert os.environ["TRANSFORMERS_CACHE"] == str(transformers_cache.resolve())
    assert os.environ["TORCH_HOME"] == str(torch_home.resolve())
    for name in ("TMPDIR", "TEMP", "TMP"):
        assert os.environ[name] == str(temporary.resolve())


def test_hugging_face_pipeline_receives_configured_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    captured: dict[str, object] = {}

    def fake_pipeline(task, **kwargs):
        captured.update({"task": task, **kwargs})
        return object()

    monkeypatch.setattr("app.evaluation._pipeline_factory", lambda: fake_pipeline)
    _model_pipeline.cache_clear()
    try:
        _model_pipeline("zero-shot-classification", "test-model", tmp_path)
    finally:
        _model_pipeline.cache_clear()

    assert captured["task"] == "zero-shot-classification"
    assert captured["model_kwargs"] == {"cache_dir": str(tmp_path.resolve())}
