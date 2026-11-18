from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from io import BytesIO

from eth_account import Account
from eth_account.messages import encode_defunct
from PIL import Image
from sqlalchemy import select

from app.models import CallStatus, Contribution, ContributionStatus, DataCall, User
from tests.conftest import ASGITestClient


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (16, 16), "green").save(buffer, format="PNG")
    return buffer.getvalue()


def sign_in(client: ASGITestClient, private_key: str) -> str:
    account = Account.from_key(private_key)
    email = f"{account.address[2:].lower()}@wallet.test"
    password = "hackathon-test-password"
    created = client.post(
        "/signup",
        data={"email": email, "password": password, "display_name": "Test user"},
        follow_redirects=False,
    )
    if created.status_code == 409:
        signed_in = client.post(
            "/signin",
            data={"email": email, "password": password},
            follow_redirects=False,
        )
        assert signed_in.status_code == 303
    else:
        assert created.status_code == 303
    challenge = client.post("/api/auth/challenge", json={"address": account.address})
    assert challenge.status_code == 200
    message = challenge.json()["message"]
    signature = Account.sign_message(encode_defunct(text=message), private_key).signature.hex()
    verified = client.post("/api/auth/verify", json={"message": message, "signature": signature})
    assert verified.status_code == 200
    return account.address


def create_call(client: ASGITestClient, title: str = "Useful city trees") -> int:
    response = client.post(
        "/calls",
        data={
            "title": title,
            "description": "Collect short descriptions of healthy street trees.",
            "data_type": "image_text",
            "acceptance_criteria": "Clear images of healthy street trees with accurate text",
            "review_mode": "ai_assisted",
            "standard_reward": "1",
            "high_reward": "2",
            "max_acceptances": "3",
            "deadline": (datetime.now(UTC) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    return int(response.headers["location"].rsplit("/", 1)[-1])


def open_call(client: ASGITestClient, call_id: int) -> None:
    database = client.app.state.database
    with database.session_factory() as db:
        data_call = db.get(DataCall, call_id)
        assert data_call is not None
        data_call.status = CallStatus.OPEN
        db.commit()


def test_health_and_home_render(client: ASGITestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    response = client.get("/")
    assert response.status_code == 200
    assert "AI-assisted data bounties" in response.text


def test_new_call_form_offers_extended_data_types(client: ASGITestClient) -> None:
    account = Account.create()
    sign_in(client, account.key.hex())
    form = client.get("/calls/new")
    assert 'value="image_text"' in form.text
    assert '<option value="csv"' in form.text
    assert '<option value="image_segmentation_text"' in form.text

    rejected = client.post(
        "/calls",
        data={
            "title": "Unsupported CSV call",
            "description": "This datatype is intentionally omitted.",
            "data_type": "csv",
            "acceptance_criteria": "Valid CSV rows",
            "review_mode": "manual",
            "standard_reward": "1",
            "high_reward": "",
            "max_acceptances": "2",
            "deadline": (datetime.now(UTC) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
        },
    )
    assert rejected.status_code == 422
    assert "require AI-assisted review" in rejected.text


def test_other_account_sees_open_call_caller(client: ASGITestClient) -> None:
    caller = Account.create()
    visitor = Account.create()
    sign_in(client, caller.key.hex())
    call_id = create_call(client, "Visible public call")
    database = client.app.state.database
    with database.session_factory() as db:
        data_call = db.get(DataCall, call_id)
        assert data_call is not None
        data_call.caller.display_name = "Visible caller"
        data_call.caller.bio = "Collects careful public datasets."
        data_call.status = CallStatus.OPEN
        db.commit()

    client.post("/api/auth/logout")
    sign_in(client, visitor.key.hex())
    home = client.get("/")
    assert home.status_code == 200
    assert "Visible public call" in home.text
    assert "Visible caller" in home.text
    assert "/static/images/default-avatar.svg" in home.text
    detail = client.get(f"/calls/{call_id}")
    assert "Collects careful public datasets." in detail.text
    assert "/static/images/default-avatar.svg" in detail.text


def test_account_without_uploaded_picture_receives_default_avatar(
    client: ASGITestClient,
) -> None:
    account = Account.create()
    sign_in(client, account.key.hex())
    with client.app.state.database.session_factory() as db:
        user = db.scalar(select(User).where(User.wallet_address == account.address))
        assert user is not None
        user_id = user.id
        assert user.profile_image is None

    response = client.get(f"/profiles/{user_id}/picture")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    home = client.get("/")
    assert "/static/images/default-avatar.svg" in home.text


def test_owner_open_call_is_not_listed_twice(client: ASGITestClient) -> None:
    caller = Account.create()
    sign_in(client, caller.key.hex())
    call_id = create_call(client, "One visible card only")
    open_call(client, call_id)

    home = client.get("/")
    assert home.status_code == 200
    assert home.text.count("One visible card only") == 1


def test_browser_http_error_returns_to_page_and_opens_popup(
    client: ASGITestClient,
) -> None:
    response = client.get(
        "/calls/999999",
        headers={"accept": "text/html", "referer": "http://testserver/"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"

    home = client.get("/", headers={"accept": "text/html"})
    assert "Call not found" in home.text
    popup = home.text.split('id="error-popup"', 1)[1].split(">", 1)[0]
    assert "hidden" not in popup
    assert "error-page" not in home.text


def test_browser_request_validation_error_uses_popup(client: ASGITestClient) -> None:
    response = client.post(
        "/signup",
        data={},
        headers={"accept": "text/html", "referer": "http://testserver/signup"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/signup"

    signup = client.get("/signup", headers={"accept": "text/html"})
    assert "Invalid request" in signup.text
    popup = signup.text.split('id="error-popup"', 1)[1].split(">", 1)[0]
    assert "hidden" not in popup


def test_review_counter_and_three_state_tabs(client: ASGITestClient) -> None:
    caller = Account.create()
    sign_in(client, caller.key.hex())
    call_id = create_call(client, "Tabbed review")
    open_call(client, call_id)
    database = client.app.state.database
    with database.session_factory() as db:
        data_call = db.get(DataCall, call_id)
        assert data_call is not None
        for filename, status, decision in (
            ("undecided.csv", ContributionStatus.READY, None),
            ("awaiting.csv", ContributionStatus.AWAITING_PAYOUT, "accept"),
            ("accepted.csv", ContributionStatus.PAID, "accept"),
            ("rejected.csv", ContributionStatus.REJECTED, "reject"),
        ):
            db.add(
                Contribution(
                    call_id=call_id,
                    contributor_id=data_call.caller_id,
                    stored_filename=filename,
                    original_filename=filename,
                    sha256=hashlib.sha256(filename.encode()).hexdigest(),
                    media_type="text/csv",
                    size_bytes=20,
                    status=status,
                    final_decision=decision,
                )
            )
        db.commit()

    detail = client.get(f"/calls/{call_id}")
    assert "Review contributions (2)" in detail.text
    assert '<details class="activity-dropdown">' in detail.text
    assert 'class="activity-count"' in detail.text

    undecided = client.get(f"/calls/{call_id}/review?tab=undecided")
    assert ">Undecided</span> (2)" in undecided.text
    assert ">Accepted</span> (1)" in undecided.text
    assert ">Rejected</span> (1)" in undecided.text
    assert "undecided.csv" in undecided.text
    assert "awaiting.csv" in undecided.text
    assert "accepted.csv" not in undecided.text
    assert 'class="badge undecided"' in undecided.text
    assert client.get(f"/calls/{call_id}/review?tab=awaiting_payout").status_code == 422

    accepted = client.get(f"/calls/{call_id}/review?tab=accepted")
    assert "accepted.csv" in accepted.text
    assert 'class="badge accepted"' in accepted.text
    assert "undecided.csv" not in accepted.text
    assert "awaiting.csv" not in accepted.text
    rejected = client.get(f"/calls/{call_id}/review?tab=rejected")
    assert "rejected.csv" in rejected.text
    assert "accepted.csv" not in rejected.text


def test_repeat_of_rejected_data_skips_evaluation(client: ASGITestClient) -> None:
    caller = Account.create()
    sign_in(client, caller.key.hex())
    call_id = create_call(client, "Rejected duplicate")
    open_call(client, call_id)
    content = _png_bytes()
    database = client.app.state.database
    with database.session_factory() as db:
        data_call = db.get(DataCall, call_id)
        assert data_call is not None
        db.add(
            Contribution(
                call_id=call_id,
                contributor_id=data_call.caller_id,
                stored_filename="rejected-original.png",
                original_filename="rejected-original.png",
                sha256=hashlib.sha256(content).hexdigest(),
                media_type="image/png",
                size_bytes=len(content),
                status=ContributionStatus.REJECTED,
                final_decision="reject",
            )
        )
        db.commit()

    repeated = client.post(
        f"/calls/{call_id}/contributions",
        data={"companion_text": "Repeated rejected street sign"},
        files={"contribution_file": ("repeat.png", content, "image/png")},
    )
    assert repeated.status_code == 409
    assert "rejected without AI reevaluation" in repeated.text
    with database.session_factory() as db:
        assert db.query(Contribution).filter(Contribution.call_id == call_id).count() == 1


def test_image_text_pair_requires_and_stores_text(client: ASGITestClient) -> None:
    caller = Account.create()
    sign_in(client, caller.key.hex())
    call_id = create_call(client, "Image-text pairs")
    database = client.app.state.database
    with database.session_factory() as db:
        data_call = db.get(DataCall, call_id)
        assert data_call is not None
        data_call.data_type = "image_text"
        data_call.status = CallStatus.OPEN
        db.commit()

    missing = client.post(
        f"/calls/{call_id}/contributions",
        files={"contribution_file": ("sign.png", _png_bytes(), "image/png")},
    )
    assert missing.status_code == 422
    accepted = client.post(
        f"/calls/{call_id}/contributions",
        data={"companion_text": "Vietnamese stop sign"},
        files={"contribution_file": ("sign.png", _png_bytes(), "image/png")},
        follow_redirects=False,
    )
    assert accepted.status_code == 303
    with database.session_factory() as db:
        contribution = db.query(Contribution).filter(Contribution.call_id == call_id).one()
        assert contribution.companion_text == "Vietnamese stop sign"


def test_wallet_challenge_is_one_use(client: ASGITestClient) -> None:
    account = Account.create()
    signup = client.post(
        "/signup",
        data={
            "email": "challenge@example.test",
            "password": "correct-horse-password",
            "display_name": "Challenge user",
        },
    )
    assert signup.status_code == 303
    challenge = client.post("/api/auth/challenge", json={"address": account.address}).json()
    signature = Account.sign_message(
        encode_defunct(text=challenge["message"]), account.key
    ).signature.hex()
    payload = {"message": challenge["message"], "signature": signature}
    assert client.post("/api/auth/verify", json=payload).status_code == 200
    assert client.post("/api/auth/verify", json=payload).status_code == 401


def test_email_account_profile_and_signin(client: ASGITestClient) -> None:
    created = client.post(
        "/signup",
        data={
            "email": "Owner@Example.com",
            "password": "correct-horse-password",
            "display_name": "Original name",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    updated = client.post(
        "/settings",
        data={
            "email": "owner@example.com",
            "display_name": "Updated name",
            "bio": "Dataset collector",
            "new_password": "",
        },
        files={"profile_picture": ("avatar.png", _png_bytes(), "image/png")},
        follow_redirects=False,
    )
    assert updated.status_code == 303
    settings_page = client.get("/settings")
    assert "Updated name" in settings_page.text
    assert "Dataset collector" in settings_page.text
    assert "/picture" in settings_page.text

    client.post("/api/auth/logout")
    signed_in = client.post(
        "/signin",
        data={"email": "OWNER@example.com", "password": "correct-horse-password"},
        follow_redirects=False,
    )
    assert signed_in.status_code == 303


def test_existing_wallet_account_can_recover_and_add_email(client: ASGITestClient) -> None:
    account = Account.create()
    database = client.app.state.database
    with database.session_factory() as db:
        db.add(User(wallet_address=account.address))
        db.commit()

    challenge = client.post("/api/auth/challenge", json={"address": account.address})
    assert challenge.status_code == 200
    message = challenge.json()["message"]
    signature = Account.sign_message(encode_defunct(text=message), account.key).signature.hex()
    verified = client.post("/api/auth/verify", json={"message": message, "signature": signature})
    assert verified.status_code == 200
    assert client.get("/settings").status_code == 200

    updated = client.post(
        "/settings",
        data={
            "email": "legacy@example.test",
            "display_name": "Legacy owner",
            "bio": "",
            "new_password": "new-legacy-password",
        },
        follow_redirects=False,
    )
    assert updated.status_code == 303


def test_create_contribute_review_flow(client: ASGITestClient) -> None:
    caller = Account.create()
    contributor = Account.create()
    sign_in(client, caller.key.hex())
    call_id = create_call(client)
    draft_page = client.get(f"/calls/{call_id}")
    assert draft_page.status_code == 200
    assert "Set escrow and token addresses" in draft_page.text
    open_call(client, call_id)

    client.post("/api/auth/logout")
    sign_in(client, contributor.key.hex())
    response = client.post(
        f"/calls/{call_id}/contributions",
        data={"companion_text": "A healthy maple street tree with green leaves"},
        files={
            "contribution_file": (
                "tree.png",
                _png_bytes(),
                "image/png",
            )
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    contribution_id = int(response.headers["location"].rsplit("/", 1)[-1])

    detail = client.get(f"/contributions/{contribution_id}")
    assert detail.status_code == 200
    assert "manual judgment is required" in detail.text
    forbidden = client.post(
        f"/contributions/{contribution_id}/decision",
        data={"decision": "accept", "tier": "standard"},
    )
    assert forbidden.status_code == 403

    duplicate = client.post(
        f"/calls/{call_id}/contributions",
        data={"companion_text": "Duplicate tree image"},
        files={
            "contribution_file": (
                "again.png",
                _png_bytes(),
                "image/png",
            )
        },
    )
    assert duplicate.status_code == 409

    client.post("/api/auth/logout")
    sign_in(client, caller.key.hex())
    queue = client.get(f"/calls/{call_id}/review")
    assert queue.status_code == 200
    assert "tree.png" in queue.text
    accepted = client.post(
        f"/contributions/{contribution_id}/decision",
        data={"decision": "accept", "tier": "high"},
        follow_redirects=False,
    )
    assert accepted.status_code == 303

    database = client.app.state.database
    with database.session_factory() as db:
        contribution = db.scalar(select(Contribution).where(Contribution.id == contribution_id))
        assert contribution is not None
        assert contribution.status == ContributionStatus.AWAITING_PAYOUT
        assert contribution.reward_amount == 2_000_000
        assert contribution.ai_recommendation == "unsure"


def test_upload_validation_and_transaction_hash(client: ASGITestClient) -> None:
    account = Account.create()
    sign_in(client, account.key.hex())
    call_id = create_call(client, "Image samples")
    open_call(client, call_id)

    invalid = client.post(
        f"/calls/{call_id}/contributions",
        data={"companion_text": "Invalid image bytes"},
        files={"contribution_file": ("bad.png", b"\xff\xfe", "image/png")},
    )
    assert invalid.status_code == 422

    database = client.app.state.database
    with database.session_factory() as db:
        data_call = db.get(DataCall, call_id)
        assert data_call is not None
        data_call.status = CallStatus.DRAFT
        db.commit()
    invalid_tx = client.post(f"/calls/{call_id}/funding-tx", json={"tx_hash": "not-a-hash"})
    assert invalid_tx.status_code == 422


def test_authorized_user_can_poll_evaluation_progress(client: ASGITestClient) -> None:
    account = Account.create()
    sign_in(client, account.key.hex())
    call_id = create_call(client, "Progress check")

    database = client.app.state.database
    with database.session_factory() as db:
        data_call = db.get(DataCall, call_id)
        assert data_call is not None
        contribution = Contribution(
            call_id=call_id,
            contributor_id=data_call.caller_id,
            stored_filename="progress.txt",
            original_filename="progress.txt",
            sha256="a" * 64,
            media_type="text/csv",
            size_bytes=10,
            status=ContributionStatus.EVALUATING,
            evaluation_progress=65,
            evaluation_stage="Evaluating each criterion",
        )
        db.add(contribution)
        db.commit()
        contribution_id = contribution.id

    response = client.get(f"/api/contributions/{contribution_id}/evaluation")
    assert response.status_code == 200
    assert response.json() == {
        "status": "evaluating",
        "progress": 65,
        "stage": "Evaluating each criterion",
        "recommendation": None,
    }
