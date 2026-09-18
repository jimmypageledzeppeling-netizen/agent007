"""Application configuration loaded from environment variables and the .env file.

A single ``Settings`` instance is the only place that reads the environment; every
other module receives configuration through it instead of calling ``os.getenv``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root: .../Agent007/Agent007/app/config.py -> up three levels.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed view over the environment. Invalid or missing values fail at startup."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    log_level: str = "INFO"
    log_dir: Path = Path("Log")
    data_dir: Path = Path("Agent007/data")
    sessions_dir: Path = Path("Agent007/sessions")
    media_cache_dir: Path = Path("Agent007/media")
    data_mode: str = "test"

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_db: str = "agent007"
    mysql_user: str = "agent007"
    mysql_password: SecretStr = SecretStr("")

    kafka_bootstrap_servers: str = "127.0.0.1:9092"
    kafka_client_id: str = "agent007"

    telegram_api_id: int = 0
    telegram_api_hash: SecretStr = SecretStr("")
    telegram_clear_delay_min_seconds: float = Field(default=0.2, ge=0.2, le=1.5)
    telegram_clear_delay_max_seconds: float = Field(default=1.5, ge=0.2, le=1.5)

    @model_validator(mode="after")
    def _validate_clear_delay_range(self) -> "Settings":
        if self.telegram_clear_delay_max_seconds < self.telegram_clear_delay_min_seconds:
            raise ValueError(
                "TELEGRAM_CLEAR_DELAY_MAX_SECONDS must be >= TELEGRAM_CLEAR_DELAY_MIN_SECONDS"
            )
        return self

    @staticmethod
    def _resolve(directory: Path) -> Path:
        """Anchor a relative directory to the repository root; keep absolute ones as-is."""
        return directory if directory.is_absolute() else PROJECT_ROOT / directory

    @computed_field
    @property
    def log_path(self) -> Path:
        """Absolute path of the log directory, resolved against the repository root."""
        return self._resolve(self.log_dir)

    @computed_field
    @property
    def data_path(self) -> Path:
        """Absolute path of the directory with the JSON data files read by the UI."""
        return self._resolve(self.data_dir)

    @computed_field
    @property
    def sessions_path(self) -> Path:
        """Absolute path of directory with Telegram session files."""
        return self._resolve(self.sessions_dir)

    @computed_field
    @property
    def media_cache_path(self) -> Path:
        """Absolute path of directory with cached Telegram media files."""
        return self._resolve(self.media_cache_dir)

    @property
    def use_live_data(self) -> bool:
        """Whether the application should use the (future) live data source."""
        return self.data_mode.strip().lower() == "live"

    def database_url(self, *, is_async: bool = True) -> str:
        """Build the SQLAlchemy URL.

        Args:
            is_async: ``True`` for the aiomysql driver used by the application,
                ``False`` for the PyMySQL driver used by Alembic migrations.
        """
        driver = "mysql+aiomysql" if is_async else "mysql+pymysql"
        password = self.mysql_password.get_secret_value()
        return (
            f"{driver}://{self.mysql_user}:{password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )

    @property
    def is_telegram_configured(self) -> bool:
        """Whether Telegram API credentials have been supplied."""
        return self.telegram_api_id > 0 and bool(self.telegram_api_hash.get_secret_value())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance (read from the environment once)."""
    return Settings()


def save_telegram_credentials(api_id: int, api_hash: str, *, env_path: Path | None = None) -> None:
    """Persist Telegram API credentials to .env and refresh cached settings."""
    clean_hash = api_hash.strip()
    if api_id <= 0:
        raise ValueError("TELEGRAM_API_ID must be a positive integer")
    if not clean_hash:
        raise ValueError("TELEGRAM_API_HASH must not be empty")

    target = env_path or (PROJECT_ROOT / ".env")
    lines = target.read_text(encoding="utf-8").splitlines() if target.exists() else []

    def _upsert(key: str, value: str) -> None:
        prefix = f"{key}="
        for index, line in enumerate(lines):
            if line.strip().startswith(prefix):
                lines[index] = f"{key}={value}"
                return
        lines.append(f"{key}={value}")

    _upsert("TELEGRAM_API_ID", str(api_id))
    _upsert("TELEGRAM_API_HASH", clean_hash)

    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    get_settings.cache_clear()
