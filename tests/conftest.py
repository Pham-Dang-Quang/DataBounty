from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.main import create_app


class ASGITestClient:
    """Small synchronous wrapper that avoids Starlette's deprecated TestClient."""

    def __init__(self, settings: Settings) -> None:
        self.app = create_app(settings)
        self.app.state.database.create_tables()
        self.cookies = httpx.Cookies()

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
                cookies=self.cookies,
            ) as client:
                response = await client.request(method, path, **kwargs)
                self.cookies.update(response.cookies)
                return response

        return asyncio.run(send())


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        secret_key="test-secret",
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        upload_dir=tmp_path / "uploads",
        avalanche_rpc_url="http://127.0.0.1:1",
        escrow_contract_address="",
        token_contract_address="",
        enable_hf_models=False,
    )


@pytest.fixture
def client(settings: Settings) -> ASGITestClient:
    return ASGITestClient(settings)
