from pathlib import Path


def test_wallet_transactions_are_bound_to_fuji() -> None:
    wallet_js = Path("app/static/js/wallet.js").read_text(encoding="utf-8")

    assert 'import { avalancheFuji } from "https://esm.sh/viem@2/chains";' in wallet_js
    assert "chain: avalancheFuji" in wallet_js
    assert "client.switchChain({id: avalancheFuji.id})" in wallet_js
