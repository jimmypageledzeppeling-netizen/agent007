"""Tests for app.config."""

from __future__ import annotations

from pathlib import Path

from app.config import PROJECT_ROOT, Settings, get_settings, save_telegram_credentials


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


def test_data_mode_defaults_to_test() -> None:
    """Without DATA_MODE, the repository should stay on JSON fixtures."""
    settings = Settings(_env_file=None)
    assert settings.data_mode == "test"
    assert settings.use_live_data is False


def test_data_mode_live_enables_live_repository() -> None:
    """DATA_MODE=live switches startup to the live repository stub."""
    assert Settings(_env_file=None, data_mode="live").use_live_data is True


def test_data_mode_is_case_and_whitespace_tolerant() -> None:
    """Human-edited .env values should still parse as expected."""
    assert Settings(_env_file=None, data_mode=" Live ").use_live_data is True


def test_save_telegram_credentials_writes_values(tmp_path: Path) -> None:
    """Credentials are persisted into .env for next launches."""
    env_path = tmp_path / ".env"
    env_path.write_text("DATA_MODE=live\n", encoding="utf-8")

    save_telegram_credentials(12345, "hash-value", env_path=env_path)
    content = env_path.read_text(encoding="utf-8")

    assert "TELEGRAM_API_ID=12345" in content
    assert "TELEGRAM_API_HASH=hash-value" in content


def test_save_telegram_credentials_updates_existing_keys(tmp_path: Path) -> None:
    """Existing TELEGRAM keys are updated instead of duplicated."""
    env_path = tmp_path / ".env"
    env_path.write_text("TELEGRAM_API_ID=1\nTELEGRAM_API_HASH=old\n", encoding="utf-8")

    save_telegram_credentials(99, "new-hash", env_path=env_path)
    lines = env_path.read_text(encoding="utf-8").splitlines()

    assert lines.count("TELEGRAM_API_ID=99") == 1
    assert lines.count("TELEGRAM_API_HASH=new-hash") == 1


def test_telegram_clear_delay_defaults_are_valid() -> None:
    """Bulk clear delay defaults stay within accepted anti-spam range."""
    settings = Settings(_env_file=None)
    assert settings.telegram_clear_delay_min_seconds == 0.2
    assert settings.telegram_clear_delay_max_seconds == 1.5


def test_telegram_clear_delay_range_is_rejected_when_inverted() -> None:
    """Max delay below min delay is a configuration error."""
    try:
        Settings(
            _env_file=None,
            telegram_clear_delay_min_seconds=1.0,
            telegram_clear_delay_max_seconds=0.5,
        )
    except ValueError as error:
        assert "TELEGRAM_CLEAR_DELAY_MAX_SECONDS" in str(error)
    else:
        raise AssertionError("Expected invalid delay range to raise ValueError")
