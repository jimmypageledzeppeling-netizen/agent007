"""Connectivity checks for the infrastructure the application depends on.

Used by ``scripts/check_env.py`` to verify a freshly prepared environment and by
the integration tests. Every check returns a :class:`CheckResult` instead of
raising, so one broken dependency does not hide the state of the others.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings, get_settings
from app.logging_config import get_logger

_logger = get_logger(__name__)

_CONNECT_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single dependency check."""

    name: str
    ok: bool
    detail: str

    def __str__(self) -> str:
        status = "OK" if self.ok else "FAIL"
        return f"[{status}] {self.name}: {self.detail}"


async def check_mysql(settings: Settings | None = None) -> CheckResult:
    """Open a connection to MySQL and run ``SELECT VERSION()``."""
    settings = settings or get_settings()
    engine = create_async_engine(settings.database_url(), pool_pre_ping=True)
    try:
        async with asyncio.timeout(_CONNECT_TIMEOUT_SECONDS):
            async with engine.connect() as connection:
                version = (await connection.execute(text("SELECT VERSION()"))).scalar_one()
        return CheckResult("MySQL", True, f"connected, server version {version}")
    # A health check reports every failure mode rather than aborting the sweep.
    except Exception as exc:  # pylint: disable=broad-exception-caught
        _logger.error("MySQL check failed: %s", exc)
        return CheckResult("MySQL", False, f"{type(exc).__name__}: {exc}")
    finally:
        await engine.dispose()


async def check_kafka(settings: Settings | None = None) -> CheckResult:
    """Start a Kafka producer and read the cluster metadata."""
    settings = settings or get_settings()
    # Imported lazily so a missing broker does not slow down unrelated imports.
    from aiokafka import AIOKafkaProducer  # pylint: disable=import-outside-toplevel

    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        client_id=settings.kafka_client_id,
        request_timeout_ms=int(_CONNECT_TIMEOUT_SECONDS * 1000),
    )
    started = False
    try:
        async with asyncio.timeout(_CONNECT_TIMEOUT_SECONDS):
            await producer.start()
            started = True
            brokers = len(producer.client.cluster.brokers())
        return CheckResult("Kafka", True, f"connected, {brokers} broker(s) in cluster")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        _logger.error("Kafka check failed: %s", exc)
        return CheckResult("Kafka", False, f"{type(exc).__name__}: {exc}")
    finally:
        if started:
            await producer.stop()


def check_telegram_config(settings: Settings | None = None) -> CheckResult:
    """Verify Telegram credentials are present (no network call is made)."""
    settings = settings or get_settings()
    if settings.is_telegram_configured:
        return CheckResult("Telegram", True, f"api_id {settings.telegram_api_id} configured")
    return CheckResult(
        "Telegram",
        False,
        "TELEGRAM_API_ID / TELEGRAM_API_HASH are not set in .env",
    )


async def run_all_checks(settings: Settings | None = None) -> list[CheckResult]:
    """Run every dependency check concurrently and return the results."""
    settings = settings or get_settings()
    mysql, kafka = await asyncio.gather(check_mysql(settings), check_kafka(settings))
    return [mysql, kafka, check_telegram_config(settings)]
