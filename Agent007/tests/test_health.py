"""Tests for app.health.

The unit tests point the checks at a closed port and assert they degrade into a
failed :class:`CheckResult` rather than raising. The integration tests need
``docker compose up -d`` and are skipped unless ``-m integration`` is requested.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.health import CheckResult, check_kafka, check_mysql, check_telegram_config, run_all_checks


@pytest.fixture(name="unreachable")
def unreachable_fixture(settings: Settings) -> Settings:
    """Settings aimed at ports nothing is listening on."""
    return settings.model_copy(
        update={"mysql_port": 1, "kafka_bootstrap_servers": "127.0.0.1:1"}
    )


def test_check_result_renders_status() -> None:
    """Results print a human-readable status line."""
    assert str(CheckResult("MySQL", True, "up")) == "[OK] MySQL: up"
    assert str(CheckResult("MySQL", False, "down")) == "[FAIL] MySQL: down"


async def test_mysql_failure_is_reported_not_raised(unreachable: Settings) -> None:
    """An unreachable database yields ok=False instead of an exception."""
    result = await check_mysql(unreachable)
    assert result.ok is False
    assert result.name == "MySQL"


async def test_kafka_failure_is_reported_not_raised(unreachable: Settings) -> None:
    """An unreachable broker yields ok=False instead of an exception."""
    result = await check_kafka(unreachable)
    assert result.ok is False
    assert result.name == "Kafka"


def test_telegram_check_fails_without_credentials(settings: Settings) -> None:
    """Missing credentials are surfaced with an actionable message."""
    result = check_telegram_config(settings)
    assert result.ok is False
    assert "TELEGRAM_API_ID" in result.detail


def test_telegram_check_passes_with_credentials() -> None:
    """Configured credentials pass without touching the network."""
    # Built via the constructor rather than model_copy: the latter skips validation,
    # so a plain str would never be coerced into SecretStr.
    configured = Settings(_env_file=None, telegram_api_id=42, telegram_api_hash="hash")
    assert check_telegram_config(configured).ok is True


async def test_run_all_checks_covers_every_dependency(unreachable: Settings) -> None:
    """One broken dependency must not hide the others."""
    results = await run_all_checks(unreachable)
    assert [r.name for r in results] == ["MySQL", "Kafka", "Telegram"]


@pytest.mark.integration
async def test_infrastructure_is_reachable() -> None:
    """Live check against docker-compose services. Run with: pytest -m integration"""
    from app.config import get_settings  # pylint: disable=import-outside-toplevel

    results = await run_all_checks(get_settings())
    failures = [str(r) for r in results if not r.ok and r.name != "Telegram"]
    assert not failures, f"infrastructure not reachable: {failures}"
