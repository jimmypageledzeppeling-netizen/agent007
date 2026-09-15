"""Verify that the development environment is ready (step 1 acceptance check).

Run from the repository root::

    .venv\\Scripts\\python.exe Agent007\\scripts\\check_env.py

Exits with code 0 when MySQL and Kafka are reachable, 1 otherwise. Missing
Telegram credentials are reported but do not fail the run, since they are only
needed once account management lands.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running the script directly, without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402  pylint: disable=wrong-import-position
from app.health import run_all_checks  # noqa: E402  pylint: disable=wrong-import-position
from app.logging_config import setup_logging  # noqa: E402  pylint: disable=wrong-import-position

# Names that are allowed to fail without failing the whole check.
_OPTIONAL = {"Telegram"}


async def main() -> int:
    """Run the checks and print a report."""
    settings = get_settings()
    log_dir = setup_logging(settings)

    print(f"Environment : {settings.app_env}")
    print(f"Log directory: {log_dir}")
    print(f"MySQL        : {settings.mysql_user}@{settings.mysql_host}:{settings.mysql_port}"
          f"/{settings.mysql_db}")
    print(f"Kafka        : {settings.kafka_bootstrap_servers}")
    print("-" * 60)

    results = await run_all_checks(settings)
    for result in results:
        print(result)

    required_failures = [r for r in results if not r.ok and r.name not in _OPTIONAL]
    print("-" * 60)
    if required_failures:
        print(f"FAILED: {', '.join(r.name for r in required_failures)}")
        return 1
    print("Environment is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
