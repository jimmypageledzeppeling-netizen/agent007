"""Tests for app.config."""

from __future__ import annotations

from pathlib import Path

from app.config import PROJECT_ROOT, Settings, get_settings


def test_database_url_uses_async_driver_by_default(settings: Settings) -> None:
    """The application talks to MySQL through aiomysql."""
    assert settings.database_url().startswith("mysql+aiomysql://")


def test_database_url_sync_variant_is_for_alembic(settings: Settings) -> None:
    """Alembic needs the blocking PyMySQL driver."""
    assert settings.database_url(is_async=False).startswith("mysql+pymysql://")


def test_database_url_contains_credentials_and_charset(settings: Settings) -> None:
    """Password is unwrapped from SecretStr and utf8mb4 is requested."""
    url = settings.database_url()
    assert "test-password" in url
    assert url.endswith("?charset=utf8mb4")


def test_password_is_not_leaked_by_repr(settings: Settings) -> None:
    """SecretStr keeps the password out of logs and tracebacks."""
    assert "test-password" not in repr(settings)


def test_relative_log_dir_resolves_against_project_root() -> None:
    """A relative LOG_DIR is anchored to the repository root, not the CWD."""
    settings = Settings(_env_file=None, log_dir=Path("Log"))
    assert settings.log_path == PROJECT_ROOT / "Log"


def test_absolute_log_dir_is_kept(tmp_path: Path) -> None:
    """An absolute LOG_DIR is used as-is."""
    settings = Settings(_env_file=None, log_dir=tmp_path)
    assert settings.log_path == tmp_path


def test_telegram_is_unconfigured_by_default() -> None:
    """Defaults must not pretend credentials exist."""
    assert Settings(_env_file=None).is_telegram_configured is False


def test_telegram_configured_requires_both_values() -> None:
    """An api_id without a hash is not a usable configuration."""
    assert Settings(_env_file=None, telegram_api_id=123).is_telegram_configured is False
    settings = Settings(_env_file=None, telegram_api_id=123, telegram_api_hash="abc")
    assert settings.is_telegram_configured is True


def test_get_settings_is_cached() -> None:
    """Configuration is read from the environment exactly once."""
    assert get_settings() is get_settings()
