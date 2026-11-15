from __future__ import annotations

from datetime import UTC, datetime, timedelta

from eth_account import Account

from app.models import CallStatus, DataCall
from tests.conftest import ASGITestClient
from tests.test_app import create_call, sign_in


def edited_call_data() -> dict[str, str]:
    return {
        "title": "Edited city tree call",
        "description": "An updated description for the draft call.",
        "data_type": "image",
        "acceptance_criteria": "One clear image of a healthy street tree",
        "review_mode": "manual",
        "standard_reward": "3",
        "high_reward": "4",
        "max_acceptances": "2",
        "deadline": (datetime.now(UTC) + timedelta(days=4)).strftime("%Y-%m-%dT%H:%M"),
    }


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
        assert data_call.data_type == "image"
        assert data_call.standard_reward == 3_000_000
        assert data_call.max_acceptances == 2

    client.post("/api/auth/logout")
    sign_in(client, other_user.key.hex())
    assert client.get(f"/calls/{call_id}/edit").status_code == 403
    assert client.post(f"/calls/{call_id}/delete").status_code == 403

    client.post("/api/auth/logout")
    sign_in(client, caller.key.hex())
    removed = client.post(f"/calls/{call_id}/delete", follow_redirects=False)
    assert removed.status_code == 303
    assert client.get(f"/calls/{call_id}").status_code == 404


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
