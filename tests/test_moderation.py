from __future__ import annotations

import hashlib
import zipfile
from io import BytesIO

from eth_account import Account
from PIL import Image
from sqlalchemy import select

from app.models import CallModerator, Contribution, ContributionStatus, DataCall, Event, User
from tests.conftest import ASGITestClient
from tests.test_app import create_call, open_call, sign_in


def account_email(address: str) -> str:
    return f"{address[2:].lower()}@wallet.test"


def review_image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (1200, 800), (50, 140, 190)).save(output, format="PNG")
    return output.getvalue()


def add_contribution(
    client: ASGITestClient,
    call_id: int,
    filename: str,
    status: ContributionStatus,
    recommendation: str | None = None,
) -> int:
    content = f"label,value\n{filename},usable\n".encode()
    database = client.app.state.database
    with database.session_factory() as db:
        data_call = db.get(DataCall, call_id)
        assert data_call is not None
        stored_filename = f"stored-{filename}"
        (client.app.state.settings.upload_dir / stored_filename).write_bytes(content)
        contribution = Contribution(
            call_id=call_id,
            contributor_id=data_call.caller_id,
            stored_filename=stored_filename,
            original_filename=filename,
            sha256=hashlib.sha256(content).hexdigest(),
            media_type="text/csv",
            size_bytes=len(content),
            status=status,
            ai_recommendation=recommendation,
            ai_tier="standard" if recommendation else None,
        )
        db.add(contribution)
        db.commit()
        return contribution.id


def test_moderator_can_review_but_cannot_manage_or_export(client: ASGITestClient) -> None:
    caller = Account.create()
    moderator = Account.create()
    caller_address = sign_in(client, caller.key.hex())
    call_id = create_call(client, "Shared moderation")
    open_call(client, call_id)
    contribution_id = add_contribution(client, call_id, "candidate.csv", ContributionStatus.READY)

    client.post("/api/auth/logout")
    moderator_address = sign_in(client, moderator.key.hex())
    client.post("/api/auth/logout")
    sign_in(client, caller.key.hex())
    added = client.post(
        f"/calls/{call_id}/moderators",
        data={"email": account_email(moderator_address)},
        follow_redirects=False,
    )
    assert added.status_code == 303

    client.post("/api/auth/logout")
    sign_in(client, moderator.key.hex())
    assert client.get(f"/calls/{call_id}/review").status_code == 200
    decided = client.post(
        f"/contributions/{contribution_id}/decision",
        data={"decision": "reject", "tier": "standard"},
        follow_redirects=False,
    )
    assert decided.status_code == 303
    assert client.post(f"/calls/{call_id}/review/apply-ai").status_code == 403
    assert client.get(f"/calls/{call_id}/accepted.zip").status_code == 403
    assert (
        client.post(
            f"/calls/{call_id}/moderators",
            data={"email": account_email(caller_address)},
        ).status_code
        == 403
    )

    database = client.app.state.database
    with database.session_factory() as db:
        item = db.get(Contribution, contribution_id)
        reviewer = db.scalar(select(User).where(User.email == account_email(moderator_address)))
        assert item is not None and reviewer is not None
        assert item.status == ContributionStatus.REJECTED
        assert item.reviewer_id == reviewer.id

    review_page = client.get(f"/calls/{call_id}/review?tab=rejected")
    assert "Test user" in review_page.text


def test_caller_can_remove_moderator_and_reaccept_rejected_data(
    client: ASGITestClient,
) -> None:
    caller = Account.create()
    moderator = Account.create()
    sign_in(client, caller.key.hex())
    call_id = create_call(client, "Reconsider data")
    open_call(client, call_id)

    client.post("/api/auth/logout")
    moderator_address = sign_in(client, moderator.key.hex())
    database = client.app.state.database
    with database.session_factory() as db:
        moderator_user = db.scalar(
            select(User).where(User.email == account_email(moderator_address))
        )
        assert moderator_user is not None
        moderator_id = moderator_user.id

    client.post("/api/auth/logout")
    sign_in(client, caller.key.hex())
    assert (
        client.post(
            f"/calls/{call_id}/moderators",
            data={"email": account_email(moderator_address)},
        ).status_code
        == 303
    )
    contribution_id = add_contribution(client, call_id, "rejected.csv", ContributionStatus.REJECTED)
    reaccepted = client.post(
        f"/contributions/{contribution_id}/decision",
        data={"decision": "accept", "tier": "standard"},
        follow_redirects=False,
    )
    assert reaccepted.status_code == 303
    removed = client.post(
        f"/calls/{call_id}/moderators/{moderator_id}/delete",
        follow_redirects=False,
    )
    assert removed.status_code == 303

    with database.session_factory() as db:
        item = db.get(Contribution, contribution_id)
        assert item is not None
        assert item.status == ContributionStatus.AWAITING_PAYOUT
        assert (
            db.scalar(
                select(CallModerator).where(
                    CallModerator.call_id == call_id,
                    CallModerator.user_id == moderator_id,
                )
            )
            is None
        )

    client.post("/api/auth/logout")
    sign_in(client, moderator.key.hex())
    assert client.get(f"/calls/{call_id}/review").status_code == 403


def test_bulk_ai_decisions_and_accepted_only_zip(client: ASGITestClient) -> None:
    caller = Account.create()
    sign_in(client, caller.key.hex())
    call_id = create_call(client, "Bulk review")
    open_call(client, call_id)
    accepted_id = add_contribution(
        client, call_id, "accept.csv", ContributionStatus.READY, "accept"
    )
    rejected_id = add_contribution(
        client, call_id, "reject.csv", ContributionStatus.READY, "reject"
    )
    unsure_id = add_contribution(client, call_id, "unsure.csv", ContributionStatus.READY, "unsure")

    applied = client.post(f"/calls/{call_id}/review/apply-ai", follow_redirects=False)
    assert applied.status_code == 303
    database = client.app.state.database
    with database.session_factory() as db:
        assert db.get(Contribution, accepted_id).status == ContributionStatus.AWAITING_PAYOUT
        assert db.get(Contribution, rejected_id).status == ContributionStatus.REJECTED
        assert db.get(Contribution, unsure_id).status == ContributionStatus.READY

    assert client.get(f"/calls/{call_id}/accepted.zip").status_code == 404
    with database.session_factory() as db:
        paid = db.get(Contribution, accepted_id)
        assert paid is not None
        paid.status = ContributionStatus.PAID
        db.commit()

    response = client.get(f"/calls/{call_id}/accepted.zip")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert f"data/{accepted_id}_accept.csv" in names
        assert not any("reject.csv" in name or "unsure.csv" in name for name in names)
        manifest = archive.read("manifest.csv").decode("utf-8-sig")
        assert "accept.csv" in manifest
        assert "reject.csv" not in manifest


def test_review_queue_filters_multiple_ai_recommendations(
    client: ASGITestClient, monkeypatch
) -> None:
    monkeypatch.setattr("app.main.hash_password", lambda _password: "test-password-hash")
    caller = Account.create()
    sign_in(client, caller.key.hex())
    call_id = create_call(client, "Filtered review")
    open_call(client, call_id)
    add_contribution(client, call_id, "accept-filter.csv", ContributionStatus.READY, "accept")
    add_contribution(client, call_id, "reject-filter.csv", ContributionStatus.READY, "reject")
    add_contribution(client, call_id, "unsure-filter.csv", ContributionStatus.READY, "unsure")

    filtered = client.get(
        f"/calls/{call_id}/review?tab=undecided&ai=accept&ai=unsure"
    )
    assert filtered.status_code == 200
    assert "accept-filter.csv" in filtered.text
    assert "unsure-filter.csv" in filtered.text
    assert "reject-filter.csv" not in filtered.text


def test_reviewer_gets_watermarked_preview_but_contributor_keeps_original(
    client: ASGITestClient,
) -> None:
    caller = Account.create()
    contributor = Account.create()
    sign_in(client, caller.key.hex())
    call_id = create_call(client, "Protected image review")
    open_call(client, call_id)

    client.post("/api/auth/logout")
    contributor_address = sign_in(client, contributor.key.hex())
    original = review_image_bytes()
    database = client.app.state.database
    with database.session_factory() as db:
        contributor_user = db.scalar(
            select(User).where(User.email == account_email(contributor_address))
        )
        assert contributor_user is not None
        stored_filename = "protected-original.png"
        (client.app.state.settings.upload_dir / stored_filename).write_bytes(original)
        contribution = Contribution(
            call_id=call_id,
            contributor_id=contributor_user.id,
            stored_filename=stored_filename,
            original_filename="private-training-image.png",
            sha256=hashlib.sha256(original).hexdigest(),
            media_type="image/png",
            size_bytes=len(original),
            companion_text="Sensitive exact training label",
            status=ContributionStatus.READY,
        )
        db.add(contribution)
        db.commit()
        contribution_id = contribution.id

    contributor_file = client.get(f"/contributions/{contribution_id}/file")
    assert contributor_file.content == original

    client.post("/api/auth/logout")
    sign_in(client, caller.key.hex())
    detail = client.get(f"/contributions/{contribution_id}")
    assert "data-protected-preview" in detail.text
    assert "protected-image-v4" in detail.text
    assert "Sensitive exact training label" in detail.text

    protected = client.get(f"/contributions/{contribution_id}/protected-image-v4")
    assert protected.status_code == 200
    assert protected.headers["content-type"] == "image/jpeg"
    assert protected.headers["cache-control"] == "no-store, private"
    assert protected.content != original
    with Image.open(BytesIO(protected.content)) as image:
        assert image.width <= 480
        assert image.height <= 480
        pixels = list(image.convert("RGB").get_flattened_data())
        red_watermark_pixels = sum(
            red > 60 and red > green * 1.25 and red > blue * 1.08 for red, green, blue in pixels
        )
        assert red_watermark_pixels > len(pixels) * 0.02

    stored_previews = list(client.app.state.settings.upload_dir.glob("review-v4-*.jpg"))
    assert len(stored_previews) == 1
    direct_file = client.get(f"/contributions/{contribution_id}/file")
    assert direct_file.content == protected.content
    assert client.get(f"/contributions/{contribution_id}/companion-preview").status_code == 404
    with database.session_factory() as db:
        events = db.scalars(
            select(Event).where(
                Event.contribution_id == contribution_id,
                Event.event_type == "protected_preview_viewed",
            )
        ).all()
        assert len(events) == 1
        item = db.get(Contribution, contribution_id)
        assert item is not None
        item.status = ContributionStatus.AWAITING_PAYOUT
        item.final_decision = "accept"
        db.commit()

    awaiting_file = client.get(f"/contributions/{contribution_id}/file")
    assert awaiting_file.content == protected.content
    awaiting_detail = client.get(f"/contributions/{contribution_id}")
    assert "protected-image-v4" in awaiting_detail.text
    assert 'class="badge undecided"' in awaiting_detail.text

    with database.session_factory() as db:
        item = db.get(Contribution, contribution_id)
        assert item is not None
        item.status = ContributionStatus.PAID
        db.commit()

    paid_file = client.get(f"/contributions/{contribution_id}/file")
    assert paid_file.content == original
    assert paid_file.headers["content-type"] == "image/png"
    paid_detail = client.get(f"/contributions/{contribution_id}")
    assert "protected-image-v4" not in paid_detail.text
    assert 'class="badge accepted"' in paid_detail.text
    assert f"/contributions/{contribution_id}/file" in paid_detail.text
