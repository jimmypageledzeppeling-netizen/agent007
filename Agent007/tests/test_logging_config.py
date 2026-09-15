"""Tests for app.logging_config, including the Promt.md error-file requirement."""

from __future__ import annotations

import logging

from app.config import Settings
from app.logging_config import APP_LOG_FILENAME, ERROR_LOG_FILENAME, setup_logging


def test_creates_log_directory(settings: Settings) -> None:
    """The Log directory is created on demand."""
    log_dir = setup_logging(settings, force=True)
    assert log_dir.is_dir()


def test_errors_go_to_a_dedicated_file(settings: Settings) -> None:
    """Promt.md: error logging is written to a separate file under ./Log."""
    log_dir = setup_logging(settings, force=True)
    logging.getLogger("test").error("boom")
    logging.shutdown()

    error_log = (log_dir / ERROR_LOG_FILENAME).read_text(encoding="utf-8")
    assert "boom" in error_log
    assert "ERROR" in error_log


def test_info_is_excluded_from_the_error_file(settings: Settings) -> None:
    """The error file must stay free of non-error noise."""
    log_dir = setup_logging(settings, force=True)
    logging.getLogger("test").info("just a note")
    logging.shutdown()

    assert "just a note" not in (log_dir / ERROR_LOG_FILENAME).read_text(encoding="utf-8")
    assert "just a note" in (log_dir / APP_LOG_FILENAME).read_text(encoding="utf-8")


def test_setup_is_idempotent(settings: Settings) -> None:
    """Calling setup twice must not duplicate handlers (and duplicate log lines)."""
    setup_logging(settings, force=True)
    handler_count = len(logging.getLogger().handlers)
    setup_logging(settings)
    assert len(logging.getLogger().handlers) == handler_count


def test_log_level_comes_from_settings(settings: Settings) -> None:
    """LOG_LEVEL drives the root logger level."""
    setup_logging(settings, force=True)
    assert logging.getLogger().level == logging.DEBUG
