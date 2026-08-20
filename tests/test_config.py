from pathlib import Path

from fpl_engine.config import Environment, Settings, get_settings


def test_default_settings_use_dev_environment() -> None:
    settings = get_settings()

    assert settings.environment == Environment.DEV
    assert settings.log_level == "INFO"


def test_settings_respect_env_prefix(monkeypatch: object) -> None:  # type: ignore[valid-type]
    import os

    os.environ["FPL_ENVIRONMENT"] = "prod"
    os.environ["FPL_LOG_LEVEL"] = "DEBUG"
    try:
        settings = Settings()
        assert settings.environment == Environment.PROD
        assert settings.log_level == "DEBUG"
    finally:
        del os.environ["FPL_ENVIRONMENT"]
        del os.environ["FPL_LOG_LEVEL"]


def test_derived_data_paths_are_nested_under_data_dir() -> None:
    settings = Settings(data_dir=Path("data"))

    assert settings.raw_dir == Path("data/raw")
    assert settings.staging_dir == Path("data/staging")
    assert settings.processed_dir == Path("data/processed")
