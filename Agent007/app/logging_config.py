"""Centralised logging setup.

Promt.md requires error logging to go to a dedicated file under ``./Log``. Three
sinks are installed:

* ``Log/app.log``    -- everything at the configured level and above;
* ``Log/errors.log`` -- ERROR and CRITICAL only, the dedicated error file;
* stderr             -- same as ``app.log``, for running from a console.

Files rotate at 5 MB and keep five backups so a long-running session cannot fill
the disk.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from app.config import Settings, get_settings

_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 5
_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(threadName)s | %(message)s"

APP_LOG_FILENAME = "app.log"
ERROR_LOG_FILENAME = "errors.log"

_CONFIGURED = False


def _rotating_handler(path: Path, level: int, formatter: logging.Formatter):
    """Create a UTF-8 rotating file handler for ``path`` at ``level``."""
    handler = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


def setup_logging(settings: Settings | None = None, *, force: bool = False) -> Path:
    """Configure the root logger. Idempotent unless ``force`` is set.

    Args:
        settings: Configuration to use; defaults to :func:`get_settings`.
        force: Re-configure even if logging was already set up (used by tests).

    Returns:
        The directory the log files were written to.
    """
    global _CONFIGURED  # pylint: disable=global-statement

    settings = settings or get_settings()
    log_dir = settings.log_path
    log_dir.mkdir(parents=True, exist_ok=True)

    if _CONFIGURED and not force:
        return log_dir

    level = logging.getLevelNamesMapping().get(settings.log_level.upper(), logging.INFO)
    formatter = logging.Formatter(_FORMAT)

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
        existing.close()

    root.setLevel(level)
    root.addHandler(_rotating_handler(log_dir / APP_LOG_FILENAME, level, formatter))
    root.addHandler(_rotating_handler(log_dir / ERROR_LOG_FILENAME, logging.ERROR, formatter))

    console = logging.StreamHandler(stream=sys.stderr)
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Third-party libraries are chatty at DEBUG; keep them at WARNING.
    for noisy in ("telethon", "aiokafka", "asyncio", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True
    logging.getLogger(__name__).debug("Logging initialised in %s at level %s", log_dir, level)
    return log_dir


def get_logger(name: str) -> logging.Logger:
    """Return a module logger, configuring logging on first use."""
    setup_logging()
    return logging.getLogger(name)
