"""Application configuration.

Centralizes all environment-dependent settings behind a single, typed
`Settings` object. Nothing else in the codebase should read `os.environ`
directly — this is the one place configuration is resolved, so later
phases (data ingestion, DB, API) all depend on the same contract.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Deployment environment. Controls things like data-write safety."""

    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class Settings(BaseSettings):
    """Typed, validated application settings.

    Values are resolved from (in priority order): environment variables,
    a `.env` file in the project root, then the defaults below.
    """

    model_config = SettingsConfigDict(
        env_prefix="FPL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.DEV
    log_level: str = "INFO"

    # Root of the data lake. See docs/architecture.md Section 4.
    data_dir: Path = Field(default=Path("data"))

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def staging_dir(self) -> Path:
        return self.data_dir / "staging"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"


def get_settings() -> Settings:
    """Return a fresh Settings instance.

    Not cached at module scope on purpose: tests need to construct
    Settings with different env vars without import-order side effects.
    Callers that want a stable instance for the lifetime of a process
    (e.g. the API app) should construct one at startup and pass it down.
    """
    return Settings()
