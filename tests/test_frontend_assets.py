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
    assert wallet_js.index(approval_wait) < wallet_js.index(nonce_read)
    assert wallet_js.index(nonce_read) < wallet_js.rindex(funding_call)
    assert "nonce," in wallet_js


def test_wallet_transaction_account_must_match_signed_in_user() -> None:
    wallet_js = Path("app/static/js/wallet.js").read_text(encoding="utf-8")
    base_page = Path("app/templates/base.html").read_text(encoding="utf-8")

    assert "data-user-wallet" in base_page
    assert "activeAccount !== getAddress(signedInWallet)" in wallet_js
    assert "DataBounty is signed in as" in wallet_js
