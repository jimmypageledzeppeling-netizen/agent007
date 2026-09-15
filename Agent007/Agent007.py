# pylint: disable=invalid-name
# The filename is fixed by <StartupFile> in Agent007.pyproj and cannot be snake_case.
"""Agent007 entry point.

Wires up configuration and logging, then opens the Tkinter main window built in
step 2 (see .claude/step2.md).
"""

from __future__ import annotations

import logging
import os
import sys
import tkinter as tk
from pathlib import Path

# Allow running this file directly from Visual Studio or the command line.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import __version__  # noqa: E402  pylint: disable=wrong-import-position
from app.config import get_settings  # noqa: E402  pylint: disable=wrong-import-position
from app.logging_config import setup_logging  # noqa: E402  pylint: disable=wrong-import-position
from Front.main_window import run  # noqa: E402  pylint: disable=wrong-import-position


def _configure_tk_environment() -> None:
    """Point Tkinter to Tcl/Tk runtime files when Python was installed with a non-default layout."""
    if "TCL_LIBRARY" in os.environ and "TK_LIBRARY" in os.environ:
        return

    candidates = {
        Path(sys.base_prefix),
        Path(sys.base_exec_prefix),
        Path(sys.executable).resolve().parent.parent,
    }

    for base in candidates:
        tcl_dir = base / "tcl" / "tcl8.6"
        tk_dir = base / "tcl" / "tk8.6"

        if "TCL_LIBRARY" not in os.environ and (tcl_dir / "init.tcl").exists():
            os.environ["TCL_LIBRARY"] = str(tcl_dir)
        if "TK_LIBRARY" not in os.environ and (tk_dir / "tk.tcl").exists():
            os.environ["TK_LIBRARY"] = str(tk_dir)

        if "TCL_LIBRARY" in os.environ and "TK_LIBRARY" in os.environ:
            return


def main() -> int:
    """Initialise the application and return a process exit code."""
    settings = get_settings()
    log_dir = setup_logging(settings)

    logger = logging.getLogger(__name__)
    logger.info("Agent007 %s starting in %s mode", __version__, settings.app_env)
    logger.info("Logs are written to %s", log_dir)
    _configure_tk_environment()

    try:
        run()
    except tk.TclError:
        # No display, or Tk is missing from the interpreter: nothing to fall back on.
        logger.exception("Tkinter could not open the main window")
        return 1

    logger.info("Agent007 finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
