from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO

from eth_account import Account
from PIL import Image
from sqlalchemy import select

from app.models import CallStatus, Contribution, ContributionStatus, DataCall
from tests.conftest import ASGITestClient
from tests.test_app import sign_in


def image_bytes(color: str, size: tuple[int, int] = (120, 80)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
    return output.getvalue()


def segmentation_mask_bytes(size: tuple[int, int] = (120, 80)) -> bytes:
    image = Image.new("RGB", size, "#123f8c")
    width, height = size
    for x in range(width // 3, 2 * width // 3):
        for y in range(height):
            image.putpixel((x, y), (220, 35, 45))
    for x in range(2 * width // 3, width):
        for y in range(height):
            image.putpixel((x, y), (25, 180, 90))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def gradient_mask_bytes() -> bytes:
    image = Image.new("RGB", (120, 80))
    image.putdata([(x * 2, x * 2, 255 - x * 2) for _y in range(80) for x in range(120)])
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def create_typed_call(
    client: ASGITestClient,
    data_type: str,
    *,
    csv_columns: str = "",
    segmentation_mode: str = "",
    csv_max_records: str = "3",
) -> int:
    response = client.post(
        "/calls",
        data={
            "title": f"{data_type} dataset",
            "description": "Collect one carefully validated contribution.",
            "data_type": data_type,
            "acceptance_criteria": "Accurate, relevant, and internally consistent data",
            "ai_evaluation_prompt": "Report schema quality, correctness, and any suspicious data.",
            "csv_columns": csv_columns,
            "csv_delimiter": "comma",
            "csv_min_records": "1",
            "csv_max_records": csv_max_records,
            "csv_unique_column": "id" if csv_columns else "",
            "segmentation_mode": segmentation_mode,
            "review_mode": "ai_assisted",
            "standard_reward": "1",
            "high_reward": "2",
            "max_acceptances": "2",
            "deadline": (datetime.now(UTC) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    return int(response.headers["location"].rsplit("/", 1)[-1])


def open_call(client: ASGITestClient, call_id: int) -> None:
    with client.app.state.database.session_factory() as db:
        data_call = db.get(DataCall, call_id)
        assert data_call is not None
        data_call.status = CallStatus.OPEN
        db.commit()


def test_csv_is_deterministically_checked_and_hidden_before_payment(
    client: ASGITestClient,
) -> None:
    caller = Account.create()
    contributor = Account.create()
    sign_in(client, caller.key.hex())
    call_id = create_typed_call(
        client, "csv", csv_columns="id:integer\nlabel:string", csv_max_records=""
    )
    open_call(client, call_id)
    with client.app.state.database.session_factory() as db:
        data_call = db.get(DataCall, call_id)
        assert data_call is not None
        assert data_call.csv_max_records is None

    client.post("/api/auth/logout")
    sign_in(client, contributor.key.hex())
    invalid = client.post(
        f"/calls/{call_id}/contributions",
        files={"contribution_file": ("bad.csv", b"id,label\nwrong,cat\n", "text/csv")},
    )
    assert invalid.status_code == 422
    assert "must be integer" in invalid.text
    with client.app.state.database.session_factory() as db:
        assert db.scalars(select(Contribution)).all() == []

    valid = client.post(
        f"/calls/{call_id}/contributions",
        files={"contribution_file": ("good.csv", b"id,label\n1,cat\n", "text/csv")},
        follow_redirects=False,
    )
    assert valid.status_code == 303
    contribution_id = int(valid.headers["location"].rsplit("/", 1)[-1])

    client.post("/api/auth/logout")
    sign_in(client, caller.key.hex())
    detail = client.get(f"/contributions/{contribution_id}")
    assert "CSV contents are hidden until payment is confirmed" in detail.text
    assert "Deterministic CSV validation passed" in detail.text
    assert client.get(f"/contributions/{contribution_id}/file").status_code == 403

    with client.app.state.database.session_factory() as db:
        item = db.scalar(select(Contribution).where(Contribution.id == contribution_id))
        assert item is not None
        assert item.status == ContributionStatus.READY
        assert item.ai_recommendation == "unsure"
        item.status = ContributionStatus.PAID
        item.final_decision = "accept"
        db.commit()
    assert client.get(f"/contributions/{contribution_id}/file").status_code == 200


def test_segmentation_package_requires_components_and_protects_both_images(
    client: ASGITestClient,
) -> None:
    caller = Account.create()
    contributor = Account.create()
    sign_in(client, caller.key.hex())
    call_id = create_typed_call(
        client, "image_segmentation_text", segmentation_mode="image_seg_text"
    )
    open_call(client, call_id)

    client.post("/api/auth/logout")
    sign_in(client, contributor.key.hex())
    missing_source = client.post(
        f"/calls/{call_id}/contributions",
        data={"companion_text": "cat mask"},
        files={"contribution_file": ("mask.png", image_bytes("black"), "image/png")},
    )
    assert missing_source.status_code == 422
    assert "source image is required" in missing_source.text

    gradient_mask = client.post(
        f"/calls/{call_id}/contributions",
        data={"companion_text": "cat mask"},
        files={
            "contribution_file": ("mask.png", gradient_mask_bytes(), "image/png"),
            "source_image_file": ("cat.png", image_bytes("orange"), "image/png"),
        },
    )
    assert gradient_mask.status_code == 422
    assert "distinct filled region boundaries" in gradient_mask.text

    wrong_ratio = client.post(
        f"/calls/{call_id}/contributions",
        data={"companion_text": "cat mask"},
        files={
            "contribution_file": ("mask.png", segmentation_mask_bytes(), "image/png"),
            "source_image_file": (
                "cat.png",
                image_bytes("orange", (100, 100)),
                "image/png",
            ),
        },
    )
    assert wrong_ratio.status_code == 422
    assert "same aspect ratio" in wrong_ratio.text
    with client.app.state.database.session_factory() as db:
        assert db.scalars(select(Contribution)).all() == []

    submitted = client.post(
        f"/calls/{call_id}/contributions",
        data={"companion_text": "Each flat color identifies one region."},
        files={
            "contribution_file": ("mask.png", segmentation_mask_bytes(), "image/png"),
            "source_image_file": (
                "cat.png",
                image_bytes("orange", (300, 200)),
                "image/png",
            ),
        },
        follow_redirects=False,
    )
    assert submitted.status_code == 303
    contribution_id = int(submitted.headers["location"].rsplit("/", 1)[-1])

    client.post("/api/auth/logout")
    sign_in(client, caller.key.hex())
    detail = client.get(f"/contributions/{contribution_id}")
    assert "Segmentation mask" in detail.text
    assert "Source image" in detail.text
    assert "palette groups" in detail.text
    assert "aspect ratio matches" in detail.text
    assert "different allowed resolution" in detail.text
    assert "protected-image-v4" in detail.text
    assert "source-protected-image-v1" in detail.text
    mask = client.get(f"/contributions/{contribution_id}/protected-image-v4")
    source = client.get(f"/contributions/{contribution_id}/source-protected-image-v1")
    assert mask.headers["content-type"] == "image/jpeg"
    assert source.headers["content-type"] == "image/jpeg"
