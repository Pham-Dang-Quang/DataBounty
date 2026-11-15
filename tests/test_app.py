from __future__ import annotations

from datetime import UTC, datetime, timedelta

from eth_account import Account
from eth_account.messages import encode_defunct
from sqlalchemy import select

from app.models import CallStatus, Contribution, ContributionStatus, DataCall
from tests.conftest import ASGITestClient


def sign_in(client: ASGITestClient, private_key: str) -> str:
    account = Account.from_key(private_key)
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
            "data_type": "text",
            "acceptance_criteria": "A clear description of a healthy street tree",
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


def test_wallet_challenge_is_one_use(client: ASGITestClient) -> None:
    account = Account.create()
    challenge = client.post("/api/auth/challenge", json={"address": account.address}).json()
    signature = Account.sign_message(
        encode_defunct(text=challenge["message"]), account.key
    ).signature.hex()
    payload = {"message": challenge["message"], "signature": signature}
    assert client.post("/api/auth/verify", json=payload).status_code == 200
    assert client.post("/api/auth/verify", json=payload).status_code == 401


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
        files={
            "contribution_file": (
                "tree.txt",
                b"A healthy street tree with green leaves.",
                "text/plain",
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
        files={
            "contribution_file": (
                "again.txt",
                b"A healthy street tree with green leaves.",
                "text/plain",
            )
        },
    )
    assert duplicate.status_code == 409

    client.post("/api/auth/logout")
    sign_in(client, caller.key.hex())
    queue = client.get(f"/calls/{call_id}/review")
    assert queue.status_code == 200
    assert "tree.txt" in queue.text
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
    call_id = create_call(client, "Text samples")
    open_call(client, call_id)

    invalid = client.post(
        f"/calls/{call_id}/contributions",
        files={"contribution_file": ("bad.txt", b"\xff\xfe", "text/plain")},
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
            media_type="text/plain",
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
