from __future__ import annotations

from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.config import Settings
from app.evaluation import _parse_model_result, evaluate_file, validate_upload


def test_validate_image_and_text() -> None:
    image_bytes = BytesIO()
    Image.new("RGB", (20, 10), "green").save(image_bytes, format="PNG")
    image = validate_upload(image_bytes.getvalue(), "image_text", "application/octet-stream")
    assert image.media_type == "image/png"
    assert image.size_bytes > 0

    csv_file = validate_upload(b"label,value\nsign,stop\n", "csv", "text/csv")
    assert csv_file.media_type == "text/csv"
    assert len(csv_file.sha256) == 64


@pytest.mark.parametrize("content", [b"", b" \n\t", b"\xff"])
def test_invalid_text_is_rejected(content: bytes) -> None:
    with pytest.raises(ValueError):
        validate_upload(content, "csv", "text/csv")


def test_csv_rows_must_have_consistent_columns() -> None:
    with pytest.raises(ValueError, match="same number of columns"):
        validate_upload(b"name,value\nsign,stop,extra\n", "csv", "text/csv")


def test_hosted_model_evaluates_image(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    contribution = tmp_path / "street-sign.png"
    Image.new("RGB", (20, 20), "blue").save(contribution)
    captured: dict[str, object] = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"recommendation":"accept","quality_tier":"high",'
                            '"explanation":"The sign is clear and readable."}'
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr("app.evaluation.httpx.post", fake_post)
    result = evaluate_file(
        contribution,
        "image_text",
        "a readable street sign",
        Settings(
            enable_ai_api=True,
            ai_api_base_url="https://provider.example/v1",
            ai_api_key="test-key",
            ai_model="Qwen/Qwen3-VL-8B-Instruct",
        ),
        companion_text="A blue rectangular road sign",
    )

    assert result.recommendation == "accept"
    assert result.tier == "high"
    assert result.model_name == "Qwen/Qwen3-VL-8B-Instruct"
    assert captured["url"] == "https://provider.example/v1/chat/completions"
    request_body = captured["json"]
    assert isinstance(request_body, dict)
    user_content = request_body["messages"][1]["content"]
    assert user_content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_hosted_model_failure_is_unsure(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    contribution = tmp_path / "sample.txt"
    contribution.write_text("label,value\nsign,readable\n", encoding="utf-8")
    updates: list[tuple[int, str]] = []

    def fail(*_args, **_kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr("app.evaluation.httpx.post", fail)
    result = evaluate_file(
        contribution,
        "csv",
        "a readable street sign",
        Settings(
            enable_ai_api=True,
            ai_api_base_url="https://provider.example/v1",
            ai_api_key="test-key",
        ),
        lambda percent, stage: updates.append((percent, stage)),
    )

    assert result.recommendation == "unsure"
    assert result.model_name == "deterministic-fallback"
    assert updates[-1] == (90, "AI API unavailable; using safe fallback")


def test_disabled_api_reports_fallback_progress(tmp_path) -> None:
    contribution = tmp_path / "sample.txt"
    contribution.write_text("label,value\nsign,readable\n", encoding="utf-8")
    updates: list[tuple[int, str]] = []

    result = evaluate_file(
        contribution,
        "csv",
        "a readable street sign",
        Settings(enable_ai_api=False),
        lambda percent, stage: updates.append((percent, stage)),
    )

    assert updates == [
        (10, "Checking contribution"),
        (90, "AI API disabled; using safe fallback"),
    ]
    assert result.model_name == "deterministic-fallback"


def test_non_accept_result_cannot_claim_high_tier() -> None:
    result = _parse_model_result(
        '{"recommendation":"reject","quality_tier":"high","explanation":"Wrong subject"}',
        "test-model",
    )
    assert result.recommendation == "reject"
    assert result.tier == "standard"
