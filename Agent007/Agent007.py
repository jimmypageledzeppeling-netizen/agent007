# pylint: disable=invalid-name
# The filename is fixed by <StartupFile> in Agent007.pyproj and cannot be snake_case.
"""Agent007 entry point.

Step 1 wires up configuration and logging only. The Tkinter main window is
introduced in step 2 (see .claude/step2.md) and will be launched from here.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow running this file directly from Visual Studio or the command line.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import __version__  # noqa: E402  pylint: disable=wrong-import-position
from app.config import get_settings  # noqa: E402  pylint: disable=wrong-import-position
from app.logging_config import setup_logging  # noqa: E402  pylint: disable=wrong-import-position


def main() -> int:
    """Initialise the application and return a process exit code."""
    settings = get_settings()
    log_dir = setup_logging(settings)

    logger = logging.getLogger(__name__)
    logger.info("Agent007 %s starting in %s mode", __version__, settings.app_env)
    logger.info("Logs are written to %s", log_dir)

    print(f"Agent007 {__version__} ({settings.app_env}) - environment initialised.")
    print(f"Logs: {log_dir}")
    print("UI is not implemented yet; see .claude/step2.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
