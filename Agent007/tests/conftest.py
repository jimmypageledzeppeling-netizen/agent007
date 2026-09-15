"""Shared fixtures. Tests never read the developer's real .env."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration tests unless they were explicitly requested with -m integration."""
    if "integration" in (config.getoption("-m") or ""):
        return
    skip = pytest.mark.skip(reason="needs docker compose up -d; run with -m integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(name="settings")
def settings_fixture(tmp_path: Path) -> Settings:
    """Settings pointed at a throwaway log directory, isolated from .env."""
    return Settings(
        _env_file=None,
        app_env="test",
        log_level="DEBUG",
        log_dir=tmp_path / "Log",
        mysql_password="test-password",
    )
