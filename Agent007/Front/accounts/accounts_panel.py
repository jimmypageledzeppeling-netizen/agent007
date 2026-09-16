"""Accounts column -- the leftmost section of the main window (about 20% wide)."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from tkinter import ttk

from app.models import Account
from Front import theme

TITLE = "Аккаунты"

_COLUMN_STATUS = "status"
_PLACEHOLDER_IID = "__empty__"
_PLACEHOLDER_TEXT = "Нет аккаунтов"
_NO_SELECTION_TEXT = "Аккаунт не выбран"
_ADD_ACCOUNT_TITLE = "Добавить аккаунт"
_PHONE_LABEL = "Номер телефона"
_REMOVE_ACCOUNT_LABEL = "Удалить номер"
_TAG_PLACEHOLDER = "placeholder"


def _paste_from_clipboard(event: tk.Event) -> str:
    event.widget.event_generate("<<Paste>>")
    return "break"


def _copy_to_clipboard(event: tk.Event) -> str:
    event.widget.event_generate("<<Copy>>")
    return "break"


def _cut_to_clipboard(event: tk.Event) -> str:
    event.widget.event_generate("<<Cut>>")
    return "break"


def _select_all(event: tk.Event) -> str:
    event.widget.event_generate("<<SelectAll>>")
    return "break"


@dataclass(frozen=True, slots=True)
class AddAccountRequest:
    """Phone entry from the add-account dialog."""

    phone: str


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
        on_add_account: Callable[[AddAccountRequest], None] | None = None,
        on_remove_account: Callable[[Account], None] | None = None,
    ) -> None:
        """Build the list widget; call :meth:`set_accounts` to fill it."""
        super().__init__(master, text=TITLE, padding=theme.PANEL_PADDING)
        self._on_select = on_select
        self._on_add_account = on_add_account
        self._on_remove_account = on_remove_account
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
        self._tree.bind("<Button-3>", self._show_context_menu)

        self._menu = tk.Menu(self, tearoff=False)
        self._menu.add_command(label="Добавить аккаунт", command=self._open_add_account_dialog)
        self._menu.add_command(label=_REMOVE_ACCOUNT_LABEL, command=self._request_remove_selected)

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

    def _show_context_menu(self, event: tk.Event) -> str:
        """Open the accounts context menu on right click."""
        row = self._tree.identify_row(event.y)
        if row:
            self._tree.selection_set(row)
            self._tree.focus(row)

        selected = self.selected
        remove_state = "normal" if selected is not None else "disabled"
        self._menu.entryconfigure(_REMOVE_ACCOUNT_LABEL, state=remove_state)

        self._menu.tk_popup(event.x_root, event.y_root)
        self._menu.grab_release()
        return "break"

    def _open_add_account_dialog(self) -> None:
        """Open a modal dialog for entering a new account phone number."""
        dialog = tk.Toplevel(self)
        dialog.title(_ADD_ACCOUNT_TITLE)
        dialog.transient(self.winfo_toplevel())
        dialog.resizable(False, False)

        container = ttk.Frame(dialog, padding=theme.PANEL_PADDING)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(1, weight=1)

        ttk.Label(container, text=_PHONE_LABEL).grid(row=0, column=0, sticky="w")
        phone_var = tk.StringVar()
        phone_entry = ttk.Entry(container, textvariable=phone_var, width=28)
        phone_entry.grid(row=0, column=1, sticky="ew", padx=(theme.GAP, 0))

        menu = tk.Menu(dialog, tearoff=False)
        menu.add_command(label="Вырезать", command=lambda: phone_entry.event_generate("<<Cut>>"))
        menu.add_command(label="Копировать", command=lambda: phone_entry.event_generate("<<Copy>>"))
        menu.add_command(label="Вставить", command=lambda: phone_entry.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Выделить всё", command=lambda: phone_entry.event_generate("<<SelectAll>>"))

        buttons = ttk.Frame(container)
        buttons.grid(row=1, column=0, columnspan=2, sticky="e", pady=(theme.GAP, 0))

        def _close() -> None:
            dialog.destroy()

        def _submit() -> None:
            phone = phone_var.get().strip()
            _close()
            if self._on_add_account is not None:
                self._on_add_account(AddAccountRequest(phone=phone))

        ttk.Button(buttons, text="ОК", command=_submit).grid(row=0, column=0, padx=(0, theme.GAP))
        ttk.Button(buttons, text="ОТМЕНА", command=_close).grid(row=0, column=1)

        def _show_menu(event: tk.Event) -> str:
            menu.tk_popup(event.x_root, event.y_root)
            menu.grab_release()
            return "break"

        phone_entry.bind("<Control-v>", _paste_from_clipboard, add=True)
        phone_entry.bind("<Control-V>", _paste_from_clipboard, add=True)
        phone_entry.bind("<Control-c>", _copy_to_clipboard, add=True)
        phone_entry.bind("<Control-C>", _copy_to_clipboard, add=True)
        phone_entry.bind("<Control-x>", _cut_to_clipboard, add=True)
        phone_entry.bind("<Control-X>", _cut_to_clipboard, add=True)
        phone_entry.bind("<Control-a>", _select_all, add=True)
        phone_entry.bind("<Control-A>", _select_all, add=True)
        phone_entry.bind("<Shift-Insert>", _paste_from_clipboard, add=True)
        phone_entry.bind("<Control-Insert>", _copy_to_clipboard, add=True)
        phone_entry.bind("<Button-3>", _show_menu, add=True)

        dialog.protocol("WM_DELETE_WINDOW", _close)
        dialog.update_idletasks()
        dialog.grab_set()
        phone_entry.focus_set()

    def _request_remove_selected(self) -> None:
        """Request removal of the selected account through the callback."""
        account = self.selected
        if account is not None and self._on_remove_account is not None:
            self._on_remove_account(account)
