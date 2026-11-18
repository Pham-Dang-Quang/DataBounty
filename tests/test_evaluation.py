from __future__ import annotations

import base64
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.config import Settings
from app.evaluation import (
    _model_content,
    _parse_model_result,
    evaluate_file,
    validate_csv_requirements,
    validate_segmentation_mask,
    validate_upload,
)


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
        validate_csv_requirements(
            b"name,value\nsign,stop,extra\n",
            "name:string\nvalue:string",
            "comma",
            1,
            5,
            False,
            False,
            None,
        )


def test_csv_requirements_validate_schema_types_limits_and_uniqueness() -> None:
    content = b"id,label,score,active,date\n1,cat,0.9,true,2026-11-17\n"
    summary = validate_csv_requirements(
        content,
        "id:integer\nlabel:string\nscore:number\nactive:boolean\ndate:date",
        "comma",
        1,
        5,
        False,
        False,
        "id",
    )
    assert "1 records" in summary

    with pytest.raises(ValueError, match="must be number"):
        validate_csv_requirements(
            b"id,label,score\n1,cat,wrong\n",
            "id:integer\nlabel:string\nscore:number",
            "comma",
            1,
            5,
            False,
            False,
            "id",
        )
    with pytest.raises(ValueError, match="duplicates 'id'"):
        validate_csv_requirements(
            b"id,label\n1,cat\n1,dog\n",
            "id:integer\nlabel:string",
            "comma",
            1,
            5,
            False,
            False,
            "id",
        )
    with pytest.raises(ValueError, match="unexpected fields"):
        validate_csv_requirements(
            b"id,label,extra\n1,cat,x\n",
            "id:integer\nlabel:string",
            "comma",
            1,
            5,
            False,
            False,
            None,
        )
    with pytest.raises(ValueError, match="empty 'label'"):
        validate_csv_requirements(
            b"id,label\n1,\n",
            "id:integer\nlabel:string",
            "comma",
            1,
            5,
            False,
            False,
            None,
        )
    semicolon = validate_csv_requirements(
        b"id;label\n1;cat\n",
        "id:integer\nlabel:string",
        "semicolon",
        1,
        1,
        False,
        False,
        None,
    )
    assert "delimiter semicolon" in semicolon
    unlimited = validate_csv_requirements(
        b"id;label\n1;cat\n2;dog\n",
        "id:integer\nlabel:string",
        "semicolon",
        1,
        None,
        False,
        False,
        None,
    )
    assert "2 records" in unlimited


def test_segmentation_precheck_accepts_flat_colors_and_rejects_unusable_masks() -> None:
    flat = Image.new("RGB", (120, 80), "navy")
    for x in range(40, 80):
        for y in range(80):
            shade = y // 8
            flat.putpixel((x, y), (220 + shade, 40 + shade, 40 + shade))
    for x in range(80, 120):
        for y in range(80):
            shade = y // 8
            flat.putpixel((x, y), (40 + shade, 200 + shade, 80 + shade))
    flat_bytes = BytesIO()
    flat.save(flat_bytes, format="PNG")
    source = BytesIO()
    Image.new("RGB", (300, 200), "orange").save(source, format="PNG")
    summary = validate_segmentation_mask(flat_bytes.getvalue(), source.getvalue())
    assert "palette groups" in summary
    assert "aspect ratio matches" in summary
    assert "different allowed resolution" in summary

    rounded_mask = flat.resize((253, 169), Image.Resampling.NEAREST)
    rounded_mask_bytes = BytesIO()
    rounded_mask.save(rounded_mask_bytes, format="PNG")
    rounded_summary = validate_segmentation_mask(rounded_mask_bytes.getvalue(), source.getvalue())
    assert "aspect ratio matches" in rounded_summary

    gradient = Image.new("RGB", (120, 80))
    gradient.putdata([(x * 2, x * 2, 255 - x * 2) for _y in range(80) for x in range(120)])
    gradient_bytes = BytesIO()
    gradient.save(gradient_bytes, format="PNG")
    with pytest.raises(ValueError, match="distinct filled region boundaries"):
        validate_segmentation_mask(gradient_bytes.getvalue())

    checkerboard = Image.new("RGB", (40, 40))
    checkerboard.putdata(
        [(255, 0, 0) if (x + y) % 2 else (0, 0, 255) for y in range(40) for x in range(40)]
    )
    checkerboard_bytes = BytesIO()
    checkerboard.save(checkerboard_bytes, format="PNG")
    with pytest.raises(ValueError, match="too visually complex or noisy"):
        validate_segmentation_mask(checkerboard_bytes.getvalue())

    wrong_ratio = BytesIO()
    Image.new("RGB", (100, 100), "orange").save(wrong_ratio, format="PNG")
    with pytest.raises(ValueError, match="same aspect ratio"):
        validate_segmentation_mask(flat_bytes.getvalue(), wrong_ratio.getvalue())


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
        ai_prompt="Report readability and lighting in detail.",
    )

    assert result.recommendation == "accept"
    assert result.tier == "high"
    assert result.model_name == "Qwen/Qwen3-VL-8B-Instruct"
    assert captured["url"] == "https://provider.example/v1/chat/completions"
    request_body = captured["json"]
    assert isinstance(request_body, dict)
    user_content = request_body["messages"][1]["content"]
    assert "Report readability and lighting" in user_content[0]["text"]
    assert user_content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_hosted_model_reuses_vision_request_for_segmentation(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    mask = tmp_path / "mask.png"
    source = tmp_path / "source.png"
    Image.new("RGB", (20, 20), "black").save(mask)
    Image.new("RGB", (20, 20), "orange").save(source)
    captured: dict[str, object] = {}

    def fake_post(url, *, headers, json, timeout):
        captured["json"] = json
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"recommendation":"accept","quality_tier":"standard",'
                            '"explanation":"The mask follows the source subject boundary."}'
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr("app.evaluation.httpx.post", fake_post)
    result = evaluate_file(
        mask,
        "image_segmentation_text",
        "Mask the main animal",
        Settings(
            enable_ai_api=True,
            ai_api_base_url="https://provider.example/v1",
            ai_api_key="test-key",
        ),
        companion_text="Cat",
        ai_prompt="Assess boundary accuracy and label agreement.",
        source_image_path=source,
        segmentation_mode="image_seg_text",
        validation_summary="Package structure passed.",
    )
    assert result.recommendation == "accept"
    request_body = captured["json"]
    assert isinstance(request_body, dict)
    system_prompt = request_body["messages"][0]["content"]
    content = request_body["messages"][1]["content"]
    image_parts = [part for part in content if part["type"] == "image_url"]
    assert len(image_parts) == 2
    assert "never mentally composite" in system_prompt
    assert "separate file" in content[0]["text"]
    assert "PRIMARY FILE — SEGMENTATION MASK" in content[2]["text"]
    assert "SECONDARY FILE — SOURCE/REFERENCE IMAGE ONLY" in content[4]["text"]
    expected_mask = base64.b64encode(mask.read_bytes()).decode("ascii")
    expected_source = base64.b64encode(source.read_bytes()).decode("ascii")
    assert content[3]["image_url"]["url"].endswith(expected_mask)
    assert content[5]["image_url"]["url"].endswith(expected_source)


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


def test_hosted_model_can_explicitly_recommend_unsure() -> None:
    result = _parse_model_result(
        '{"recommendation":"unsure","quality_tier":"high",'
        '"explanation":"The submission does not provide enough evidence."}',
        "test/model",
    )

    assert result.recommendation == "unsure"
    assert result.tier == "standard"
    assert "not provide enough evidence" in result.explanation


def test_csv_model_request_contains_private_data_and_detailed_prompt(tmp_path) -> None:
    contribution = tmp_path / "private.csv"
    contribution.write_text("id,label\n1,cat\n", encoding="utf-8")
    content = _model_content(
        contribution,
        "csv",
        "Valid labels",
        ai_prompt="Assess class balance and suspicious values in detail.",
        validation_summary="Typed schema validation passed.",
    )
    assert "Assess class balance" in content[0]["text"]
    assert "Typed schema validation passed" in content[0]["text"]
    assert "do not quote raw records" in content[0]["text"]
    assert "id,label\n1,cat" in content[1]["text"]


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
