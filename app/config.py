from __future__ import annotations

import os
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
    model_cache_dir: Path = Path("./models-cache")
    hf_home: Path | None = None
    hf_hub_cache: Path | None = None
    transformers_cache: Path | None = None
    torch_home: Path | None = None
    tmpdir: Path | None = None

    @property
    def hf_home_path(self) -> Path:
        return self.hf_home or self.model_cache_dir / "huggingface"

    @property
    def hf_hub_cache_path(self) -> Path:
        return self.hf_hub_cache or self.hf_home_path / "hub"

    @property
    def transformers_cache_path(self) -> Path:
        return self.transformers_cache or self.hf_hub_cache_path

    @property
    def torch_home_path(self) -> Path:
        return self.torch_home or self.model_cache_dir / "torch"

    @property
    def tmpdir_path(self) -> Path:
        return self.tmpdir or self.model_cache_dir / "tmp"

    def ensure_directories(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        if self.enable_hf_models:
            model_directories = {
                self.model_cache_dir,
                self.hf_home_path,
                self.hf_hub_cache_path,
                self.transformers_cache_path,
                self.torch_home_path,
                self.tmpdir_path,
            }
            for directory in model_directories:
                directory.mkdir(parents=True, exist_ok=True)
            environment = {
                "HF_HOME": self.hf_home_path,
                "HF_HUB_CACHE": self.hf_hub_cache_path,
                "TRANSFORMERS_CACHE": self.transformers_cache_path,
                "TORCH_HOME": self.torch_home_path,
                "TMPDIR": self.tmpdir_path,
                "TEMP": self.tmpdir_path,
                "TMP": self.tmpdir_path,
            }
            for name, directory in environment.items():
                os.environ[name] = str(directory.resolve())
        if self.database_url.startswith("sqlite:///./"):
            Path(self.database_url.removeprefix("sqlite:///./")).parent.mkdir(
                parents=True, exist_ok=True
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
