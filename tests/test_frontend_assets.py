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
