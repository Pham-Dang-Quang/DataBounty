from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "DataBounty"
    secret_key: str = "local-hackathon-secret-change-me"
    database_url: str = "sqlite:///./data/databounty.db"
    upload_dir: Path = Path("./data/uploads")
    max_upload_bytes: int = 5 * 1024 * 1024
    session_https_only: bool = False

    avalanche_rpc_url: str = "https://api.avax-test.network/ext/bc/C/rpc"
    chain_id: int = 43113
    escrow_contract_address: str = ""
    token_contract_address: str = ""
    token_symbol: str = "DBT"
    token_decimals: int = 6
    fuji_explorer_url: str = "https://subnets-test.avax.network/c-chain"
    required_confirmations: int = 1

    enable_hf_models: bool = False
    text_model: str = "Horizon-Labs/multilingual-zeroshot-small"
    image_model: str = "openai/clip-vit-base-patch32"

    def ensure_directories(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite:///./"):
            Path(self.database_url.removeprefix("sqlite:///./")).parent.mkdir(
                parents=True, exist_ok=True
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
