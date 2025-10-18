"""Application configuration using pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    artifacts_dir: Path = Path("artifacts")
    uploads_dir: Path = Path("uploads")
    logs_dir: Path = Path("logs")
    default_fdr_threshold: float = 0.1
    enable_analytics: bool = False
    openai_api_key: Optional[str] = None
    api_key: Optional[str] = None


@lru_cache(1)
def get_settings() -> Settings:
    settings = Settings()
    settings.artifacts_dir.mkdir(exist_ok=True)
    settings.uploads_dir.mkdir(exist_ok=True)
    settings.logs_dir.mkdir(exist_ok=True)
    return settings
