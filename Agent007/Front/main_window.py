"""Application main window: the three-column shell.

Its only responsibilities are laying the sections out and connecting their
callbacks. The panels stay unaware of each other, so a section can be replaced
or moved without touching the others.

Column widths come from the agreed proportions -- accounts 20%, dialogs 30%,
transcript 50% -- expressed as ``grid`` weights in a single uniform group,
which keeps the ratio when the window is resized.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app.logging_config import get_logger
from app.models import Account, Dialog
from app.repository import DataRepository, JsonFileRepository
from Front import theme
from Front.accounts.accounts_panel import AccountsPanel
from Front.chats.dialogs_panel import DialogsPanel
from Front.messages.messages_panel import MessagesPanel

_LOGGER = get_logger(__name__)

WINDOW_TITLE = "Agent007 — управление Telegram-аккаунтами"
MIN_WIDTH = 1024
MIN_HEIGHT = 640

# Accounts 20%, dialogs 30%, messages 50%.
COLUMN_WEIGHTS = (20, 30, 50)
UNIFORM_GROUP = "agent007-columns"


class MainWindow:
    """Hosts the accounts, dialogs and messages panels side by side.

    Args:
        master: Widget to build the layout in -- normally the ``tk.Tk`` root,
            but any container works, which is what makes the window testable.
        repository: Source of accounts, dialogs and messages. Defaults to the
            JSON-backed :class:`~app.repository.JsonFileRepository`.
    """

    def __init__(self, master: tk.Misc, repository: DataRepository | None = None) -> None:
        self.master = master
        self._repository = repository if repository is not None else JsonFileRepository()

        self.container = ttk.Frame(master, padding=theme.PANEL_PADDING)
        self.container.pack(fill="both", expand=True)
        self.container.rowconfigure(0, weight=1)

        self.accounts_panel = AccountsPanel(
            self.container, on_select=self._on_account_selected
        )
        self.dialogs_panel = DialogsPanel(
            self.container, on_select=self._on_dialog_selected
        )
        self.messages_panel = MessagesPanel(self.container)

        self._lay_out_columns()
        self.load_accounts()

    @property
    def panels(self) -> tuple[AccountsPanel, DialogsPanel, MessagesPanel]:
        """The three sections, left to right."""
        return (self.accounts_panel, self.dialogs_panel, self.messages_panel)

    def load_accounts(self) -> None:
        """Fill the accounts column and preselect the first account."""
        accounts = self._repository.accounts()
        self.accounts_panel.set_accounts(accounts)
        _LOGGER.info("Loaded %d account(s) into the accounts panel", len(accounts))
        self.accounts_panel.select_first()

    def _lay_out_columns(self) -> None:
        """Place the panels in one row and give each column its share of the width."""
        for index, (panel, weight) in enumerate(zip(self.panels, COLUMN_WEIGHTS)):
            self.container.columnconfigure(
                index, weight=weight, uniform=UNIFORM_GROUP, minsize=0
            )
            # Only the gaps between panels are padded, not the outer edges.
            padx = (0 if index == 0 else theme.GAP, 0 if index == 2 else theme.GAP)
            panel.grid(row=0, column=index, sticky="nsew", padx=padx)

    def _on_account_selected(self, account: Account) -> None:
        """Show the dialogs of the chosen account and reset the transcript."""
        _LOGGER.debug("Account selected: %s", account.id)
        self.dialogs_panel.set_dialogs(self._repository.dialogs(account.id))
        self.messages_panel.show_placeholder()

    def _on_dialog_selected(self, dialog: Dialog) -> None:
        """Show the transcript of the chosen dialog."""
        _LOGGER.debug("Dialog selected: %s", dialog.id)
        self.messages_panel.show_dialog(dialog, self._repository.messages(dialog.id))


def create_root() -> tk.Tk:
    """Create the top-level window, maximised where the platform allows it."""
    root = tk.Tk()
    root.title(WINDOW_TITLE)
    root.minsize(MIN_WIDTH, MIN_HEIGHT)
    try:
        # Windows and macOS: maximise but keep the title bar and taskbar usable.
        root.state("zoomed")
    except tk.TclError:
        # Some X11 window managers reject "zoomed"; fall back to the screen size.
        root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
    return root


def run(repository: DataRepository | None = None) -> None:
    """Open the main window and block on the Tk event loop until it is closed."""
    root = create_root()
    window = MainWindow(root, repository)
    _LOGGER.info("Main window opened with %d sections", len(window.panels))
    root.mainloop()
    _LOGGER.info("Main window closed")
