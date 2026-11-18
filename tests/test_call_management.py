from __future__ import annotations

from datetime import UTC, datetime, timedelta

from eth_account import Account

from app.models import CallLink, CallStatus, Comment, Contribution, DataCall
from tests.conftest import ASGITestClient
from tests.test_app import create_call, sign_in


def edited_call_data() -> dict[str, str]:
    return {
        "title": "Edited city tree call",
        "description": "An updated description for the draft call.",
        "data_type": "image_text",
        "acceptance_criteria": "One clear image of a healthy street tree",
        "review_mode": "manual",
        "standard_reward": "3",
        "high_reward": "4",
        "max_acceptances": "2",
        "deadline": (datetime.now(UTC) + timedelta(days=4)).strftime("%Y-%m-%dT%H:%M"),
    }


def test_new_contributions_receive_unique_persistent_payout_keys(
    client: ASGITestClient,
) -> None:
    database = client.app.state.database
    with database.session_factory() as db:
        first = Contribution(
            call_id=999,
            contributor_id=999,
            stored_filename="first.png",
            original_filename="first.png",
            sha256="a" * 64,
            media_type="image/png",
            size_bytes=1,
        )
        second = Contribution(
            call_id=999,
            contributor_id=999,
            stored_filename="second.png",
            original_filename="second.png",
            sha256="b" * 64,
            media_type="image/png",
            size_bytes=1,
        )
        db.add_all([first, second])
        db.flush()

        assert first.payout_key.startswith("0x")
        assert len(first.payout_key) == 66
        assert first.payout_key != second.payout_key


def test_caller_can_edit_and_remove_unfunded_draft(client: ASGITestClient) -> None:
    caller = Account.create()
    other_user = Account.create()
    sign_in(client, caller.key.hex())
    new_call_page = client.get("/calls/new")
    assert new_call_page.status_code == 200
    assert "Create draft" in new_call_page.text
    call_id = create_call(client)

    detail_page = client.get(f"/calls/{call_id}")
    assert "Edit draft" in detail_page.text
    assert "Remove draft" in detail_page.text

    edit_page = client.get(f"/calls/{call_id}/edit")
    assert edit_page.status_code == 200
    assert "Useful city trees" in edit_page.text

    edited = client.post(
        f"/calls/{call_id}/edit",
        data=edited_call_data(),
        follow_redirects=False,
    )
    assert edited.status_code == 303

    database = client.app.state.database
    with database.session_factory() as db:
        data_call = db.get(DataCall, call_id)
        assert data_call is not None
        assert data_call.title == "Edited city tree call"
        assert data_call.data_type == "image_text"
        assert data_call.standard_reward == 3_000_000
        assert data_call.max_acceptances == 2
        assert data_call.escrow_call_id is not None
        assert data_call.escrow_call_id != data_call.id

    client.post("/api/auth/logout")
    sign_in(client, other_user.key.hex())
    assert client.get(f"/calls/{call_id}/edit").status_code == 403
    assert client.post(f"/calls/{call_id}/delete").status_code == 403

    client.post("/api/auth/logout")
    sign_in(client, caller.key.hex())
    removed = client.post(f"/calls/{call_id}/delete", follow_redirects=False)
    assert removed.status_code == 303
    assert client.get(f"/calls/{call_id}").status_code == 404


def test_maximum_accepted_can_exceed_one_hundred(client: ASGITestClient) -> None:
    caller = Account.create()
    sign_in(client, caller.key.hex())
    response = client.post(
        "/calls",
        data={**edited_call_data(), "max_acceptances": "1000"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    call_id = int(response.headers["location"].rsplit("/", 1)[-1])

    with client.app.state.database.session_factory() as db:
        data_call = db.get(DataCall, call_id)
        assert data_call is not None
        assert data_call.max_acceptances == 1000

    form = client.get(f"/calls/{call_id}/edit")
    assert 'name="max_acceptances" min="1" max="100000"' in form.text


def test_funding_submission_freezes_edit_and_remove(client: ASGITestClient) -> None:
    caller = Account.create()
    sign_in(client, caller.key.hex())
    call_id = create_call(client)

    database = client.app.state.database
    with database.session_factory() as db:
        data_call = db.get(DataCall, call_id)
        assert data_call is not None
        data_call.status = CallStatus.FUNDING
        data_call.funding_tx_hash = "0x" + "1" * 64
        db.commit()

    assert client.get(f"/calls/{call_id}/edit").status_code == 409
    assert (
        client.post(
            f"/calls/{call_id}/edit",
            data=edited_call_data(),
            follow_redirects=False,
        ).status_code
        == 409
    )
    assert client.post(f"/calls/{call_id}/delete").status_code == 409


def test_call_links_comments_and_one_level_replies(client: ASGITestClient) -> None:
    caller = Account.create()
    visitor = Account.create()
    sign_in(client, caller.key.hex())
    response = client.post(
        "/calls",
        data={
            **edited_call_data(),
            "links_text": (
                "Portfolio | https://example.com/portfolio\nGitHub | https://github.com/example"
            ),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    call_id = int(response.headers["location"].rsplit("/", 1)[-1])

    page = client.get(f"/calls/{call_id}")
    assert "https://example.com/portfolio" in page.text
    assert "https://github.com/example" in page.text

    client.post("/api/auth/logout")
    sign_in(client, visitor.key.hex())
    posted = client.post(
        f"/calls/{call_id}/comments",
        data={"body": "Could you clarify the location requirement?"},
        follow_redirects=False,
    )
    assert posted.status_code == 303

    database = client.app.state.database
    with database.session_factory() as db:
        data_call = db.get(DataCall, call_id)
        assert data_call is not None
        assert db.query(CallLink).filter(CallLink.call_id == call_id).count() == 2
        parent = db.query(Comment).filter(Comment.call_id == call_id).one()
        parent_id = parent.id

    replied = client.post(
        f"/calls/{call_id}/comments",
        data={"body": "A reply", "parent_id": str(parent_id)},
        follow_redirects=False,
    )
    assert replied.status_code == 303
    page = client.get(f"/calls/{call_id}")
    assert "Could you clarify the location requirement?" in page.text
    assert "A reply" in page.text

    with database.session_factory() as db:
        reply = db.query(Comment).filter(Comment.parent_id == parent_id).one()
        reply_id = reply.id
    nested = client.post(
        f"/calls/{call_id}/comments",
        data={"body": "Nested reply", "parent_id": str(reply_id)},
    )
    assert nested.status_code == 422
