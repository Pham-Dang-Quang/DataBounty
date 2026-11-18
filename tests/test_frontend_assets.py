from pathlib import Path


def test_wallet_transactions_are_bound_to_fuji() -> None:
    wallet_js = Path("app/static/js/wallet.js").read_text(encoding="utf-8")

    assert 'import { avalancheFuji } from "https://esm.sh/viem@2/chains";' in wallet_js
    assert "chain: avalancheFuji" in wallet_js
    assert "client.switchChain({id: avalancheFuji.id})" in wallet_js


def test_demo_token_faucet_is_available_from_the_call_page() -> None:
    wallet_js = Path("app/static/js/wallet.js").read_text(encoding="utf-8")
    call_page = Path("app/templates/call_detail.html").read_text(encoding="utf-8")
    base_page = Path("app/templates/base.html").read_text(encoding="utf-8")

    assert "data-mint-demo-token" in call_page
    assert "wallet.js') }}?v=" in base_page
    assert 'functionName: "faucet"' in wallet_js
    assert "waitForTransactionReceipt" in wallet_js


def test_funding_waits_for_approval_and_uses_pending_nonce() -> None:
    wallet_js = Path("app/static/js/wallet.js").read_text(encoding="utf-8")

    approval_wait = "waitForTransactionReceipt({hash: approvalHash})"
    nonce_read = 'blockTag: "pending"'
    funding_call = 'functionName: "fundCall"'
    funding_wait = "waitForTransactionReceipt({hash})"
    funding_record = "postJson(button.dataset.endpoint, {tx_hash: hash})"
    assert wallet_js.index(approval_wait) < wallet_js.index(nonce_read)
    assert wallet_js.index(nonce_read) < wallet_js.rindex(funding_call)
    assert wallet_js.index(funding_wait, wallet_js.rindex(funding_call)) < wallet_js.index(
        funding_record, wallet_js.rindex(funding_call)
    )
    assert "nonce," in wallet_js
    assert 'name: "CallAlreadyExists"' in wallet_js


def test_payout_uses_persistent_key_and_hides_duplicate_action() -> None:
    wallet_js = Path("app/static/js/wallet.js").read_text(encoding="utf-8")
    detail_page = Path("app/templates/contribution_detail.html").read_text(encoding="utf-8")
    ui_js = Path("app/static/js/ui.js").read_text(encoding="utf-8")

    assert "button.dataset.contributionKey" in wallet_js
    assert "keccak256(toHex(button.dataset.contributionId))" not in wallet_js
    assert 'data-contribution-key="{{ contribution.payout_key }}"' in detail_page
    assert "{% if contribution.payout_tx_hash %}" in detail_page
    assert "data-payout-pending" in detail_page
    assert 'document.querySelector("[data-payout-pending]")' in ui_js


def test_wallet_transaction_account_must_match_signed_in_user() -> None:
    wallet_js = Path("app/static/js/wallet.js").read_text(encoding="utf-8")
    base_page = Path("app/templates/base.html").read_text(encoding="utf-8")

    assert "data-user-wallet" in base_page
    assert "activeAccount !== getAddress(signedInWallet)" in wallet_js
    assert "DataBounty is signed in as" in wallet_js


def test_evaluation_progress_polls_until_complete() -> None:
    evaluation_js = Path("app/static/js/evaluation.js").read_text(encoding="utf-8")
    detail_page = Path("app/templates/contribution_detail.html").read_text(encoding="utf-8")

    assert "data-evaluation-progress" in detail_page
    assert "<progress" in detail_page
    assert "fetch(evaluation.dataset.endpoint" in evaluation_js
    assert 'result.status !== "evaluating"' in evaluation_js


def test_theme_and_language_controls_are_available() -> None:
    base_page = Path("app/templates/base.html").read_text(encoding="utf-8")
    ui_js = Path("app/static/js/ui.js").read_text(encoding="utf-8")
    css = Path("app/static/css/app.css").read_text(encoding="utf-8")

    assert "data-theme-toggle" in base_page
    assert "data-language-toggle" in base_page
    assert 'localStorage.getItem("language")' in ui_js
    assert 'localStorage.setItem("theme", theme)' in ui_js
    assert '[data-theme="dark"]' in css


def test_account_names_use_shared_avatar_identity() -> None:
    macro = Path("app/templates/macros.html").read_text(encoding="utf-8")
    templates = [
        "base.html",
        "home.html",
        "call_detail.html",
        "review_queue.html",
        "contribution_detail.html",
    ]

    assert 'class="account-identity {{ extra_class }}"' in macro
    assert "/static/images/default-avatar.svg" in macro
    assert "/profiles/{{ account.id }}/picture" in macro
    for template in templates:
        content = Path("app/templates", template).read_text(encoding="utf-8")
        assert "account_identity" in content


def test_error_popup_is_dismissible_and_scrollable() -> None:
    base_page = Path("app/templates/base.html").read_text(encoding="utf-8")
    ui_js = Path("app/static/js/ui.js").read_text(encoding="utf-8")
    css = Path("app/static/css/app.css").read_text(encoding="utf-8")

    assert 'class="modal-close"' in base_page
    assert "data-error-popup-close" in base_page
    assert "messageElement.scrollTop = 0" in ui_js
    assert ".modal-message" in css
    assert "overflow-y: auto" in css
    assert "max-height: 70dvh" in css
    assert "server_error" in base_page
    assert not Path("app/templates/error.html").exists()


def test_call_deadline_has_live_localized_countdown() -> None:
    call_page = Path("app/templates/call_detail.html").read_text(encoding="utf-8")
    ui_js = Path("app/static/js/ui.js").read_text(encoding="utf-8")

    assert "data-deadline-countdown" in call_page
    assert "function updateDeadlineCountdowns()" in ui_js
    assert "window.setInterval(updateDeadlineCountdowns, 1000)" in ui_js
    assert "deadline_reached" in ui_js


def test_call_form_switches_csv_and_segmentation_requirements() -> None:
    call_form = Path("app/templates/call_form.html").read_text(encoding="utf-8")
    ui_js = Path("app/static/js/ui.js").read_text(encoding="utf-8")

    assert 'value="csv"' in call_form
    assert 'value="image_segmentation_text"' in call_form
    assert 'data-call-type-fields="csv"' in call_form
    assert 'data-call-type-fields="image_segmentation_text"' in call_form
    assert 'name="ai_evaluation_prompt"' in call_form
    assert "function updateCallTypeFields()" in ui_js


def test_contribution_form_warns_that_submission_is_irreversible() -> None:
    call_page = Path("app/templates/call_detail.html").read_text(encoding="utf-8")
    ui_js = Path("app/static/js/ui.js").read_text(encoding="utf-8")

    assert 'data-i18n="contribution_irreversible_warning"' in call_page
    assert "A submitted contribution cannot be withdrawn" in ui_js
    assert 'data-i18n="segmentation_mask_help"' in call_page
    assert "same aspect ratio" in ui_js
