"""Accounts column -- the leftmost section of the main window (about 20% wide)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import ttk

from app.models import Account
from Front import theme

TITLE = "Аккаунты"

_COLUMN_STATUS = "status"
_PLACEHOLDER_IID = "__empty__"
_PLACEHOLDER_TEXT = "Нет аккаунтов"
_NO_SELECTION_TEXT = "Аккаунт не выбран"
_TAG_PLACEHOLDER = "placeholder"


class AccountsPanel(ttk.Labelframe):
    """Lists the managed Telegram accounts and reports which one is selected.

    The panel knows nothing about the other columns: on a selection it invokes
    the ``on_select`` callback that the main window supplied, which keeps the
    sections independently pluggable as step2.md requires.
    """

    def __init__(
        self,
        master: tk.Misc,
        *,
        on_select: Callable[[Account], None] | None = None,
    ) -> None:
        """Build the list widget; call :meth:`set_accounts` to fill it."""
        super().__init__(master, text=TITLE, padding=theme.PANEL_PADDING)
        self._on_select = on_select
        self._accounts: dict[str, Account] = {}
        # Id already reported to the callback, used to swallow repeated events.
        self._notified: str | None = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._tree = ttk.Treeview(
            self,
            columns=(_COLUMN_STATUS,),
            show="tree headings",
            selectmode="browse",
        )
        self._tree.heading("#0", text="Аккаунт", anchor="w")
        self._tree.heading(_COLUMN_STATUS, text="Статус", anchor="w")
        self._tree.column("#0", width=150, minwidth=80, stretch=True)
        self._tree.column(_COLUMN_STATUS, width=85, minwidth=60, stretch=False, anchor="w")
        self._tree.tag_configure(_TAG_PLACEHOLDER, foreground=theme.COLOR_MUTED)
        self._tree.grid(row=0, column=0, sticky="nsew")
        self._tree.bind("<<TreeviewSelect>>", self._handle_selection)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._tree.configure(yscrollcommand=scrollbar.set)

        # The phone number does not fit the narrow list, so it is shown for the
        # selected account only.
        self._details = ttk.Label(
            self,
            text=_NO_SELECTION_TEXT,
            font=theme.FONT_META,
            foreground=theme.COLOR_MUTED,
            wraplength=200,
            justify="left",
        )
        self._details.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(theme.GAP, 0))

    def set_accounts(self, accounts: Sequence[Account]) -> None:
        """Replace the list contents, or show a placeholder when there are none."""
        self._tree.delete(*self._tree.get_children())
        self._accounts = {account.id: account for account in accounts}
        self._notified = None
        self._details.configure(text=_NO_SELECTION_TEXT)

        if not accounts:
            self._tree.insert(
                "", "end", iid=_PLACEHOLDER_IID, text=_PLACEHOLDER_TEXT, tags=(_TAG_PLACEHOLDER,)
            )
            return

        for account in accounts:
            self._tree.insert(
                "",
                "end",
                iid=account.id,
                text=account.name,
                values=(account.status.label,),
            )

    def select(self, account_id: str) -> None:
        """Select an account by id; unknown ids are ignored."""
        if account_id in self._accounts:
            self._tree.selection_set(account_id)
            self._tree.focus(account_id)

    def select_first(self) -> None:
        """Select the first account so the window opens with a populated view."""
        first = next(iter(self._accounts), None)
        if first is not None:
            self.select(first)

    @property
    def tree(self) -> ttk.Treeview:
        """The underlying list widget, exposed for layout tuning and the tests."""
        return self._tree

    @property
    def selected(self) -> Account | None:
        """The currently selected account, or ``None`` if nothing is selected."""
        selection = self._tree.selection()
        return self._accounts.get(selection[0]) if selection else None

    def _handle_selection(self, _event: tk.Event) -> None:
        """Update the details line and notify the main window about the choice."""
        account = self.selected
        if account is None:
            # The placeholder row is selectable but is not a real account.
            self._details.configure(text=_NO_SELECTION_TEXT)
            return

        self._details.configure(text=f"{account.phone} · {account.status.label}")

        # Rebuilding the list makes Tk emit <<TreeviewSelect>> more than once for
        # a single change; reloading the other columns twice would be wasteful.
        if account.id == self._notified:
            return
        self._notified = account.id

        if self._on_select is not None:
            self._on_select(account)
