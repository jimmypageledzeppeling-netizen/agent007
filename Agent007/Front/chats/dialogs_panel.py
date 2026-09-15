"""Dialogs column -- the middle section of the main window (about 30% wide).

Contacts, groups and channels of one account are shown in a single tree,
grouped by kind, so the operator sees all conversations of an account at once.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import ttk

from app.models import Dialog, DialogKind
from Front import theme

TITLE = "Контакты, группы и каналы"

# Order the sections appear in, independent of the order records arrive in.
KIND_ORDER = (DialogKind.CONTACT, DialogKind.GROUP, DialogKind.CHANNEL)

_COLUMN_UNREAD = "unread"
_GROUP_IID_PREFIX = "kind::"
_PLACEHOLDER_IID = "__empty__"
_PLACEHOLDER_TEXT = "Выберите аккаунт слева"
_EMPTY_ACCOUNT_TEXT = "У аккаунта нет диалогов"
_TAG_GROUP = "group"
_TAG_PLACEHOLDER = "placeholder"
_TAG_UNREAD = "unread"


class DialogsPanel(ttk.Labelframe):
    """Lists the dialogs of the selected account and reports the chosen one.

    Like :class:`~Front.accounts.accounts_panel.AccountsPanel`, the panel talks
    to the rest of the application only through its ``on_select`` callback.
    """

    def __init__(
        self,
        master: tk.Misc,
        *,
        on_select: Callable[[Dialog], None] | None = None,
    ) -> None:
        """Build the tree widget and show the initial placeholder."""
        super().__init__(master, text=TITLE, padding=theme.PANEL_PADDING)
        self._on_select = on_select
        self._dialogs: dict[str, Dialog] = {}
        # Id already reported to the callback, used to swallow repeated events.
        self._notified: str | None = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._tree = ttk.Treeview(
            self,
            columns=(_COLUMN_UNREAD,),
            show="tree headings",
            selectmode="browse",
        )
        self._tree.heading("#0", text="Диалог", anchor="w")
        self._tree.heading(_COLUMN_UNREAD, text="Новые", anchor="e")
        self._tree.column("#0", width=260, minwidth=120, stretch=True)
        self._tree.column(_COLUMN_UNREAD, width=60, minwidth=50, stretch=False, anchor="e")
        self._tree.tag_configure(_TAG_GROUP, font=theme.FONT_AUTHOR)
        self._tree.tag_configure(_TAG_PLACEHOLDER, foreground=theme.COLOR_MUTED)
        self._tree.tag_configure(_TAG_UNREAD, foreground=theme.COLOR_UNREAD)
        self._tree.grid(row=0, column=0, sticky="nsew")
        self._tree.bind("<<TreeviewSelect>>", self._handle_selection)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._tree.configure(yscrollcommand=scrollbar.set)

        self.show_placeholder()

    def show_placeholder(self, text: str = _PLACEHOLDER_TEXT) -> None:
        """Clear the tree and explain what the operator has to do first."""
        self._tree.delete(*self._tree.get_children())
        self._dialogs = {}
        self._notified = None
        self._tree.insert(
            "", "end", iid=_PLACEHOLDER_IID, text=text, tags=(_TAG_PLACEHOLDER,)
        )

    def set_dialogs(self, dialogs: Sequence[Dialog]) -> None:
        """Replace the tree contents, grouping the dialogs by their kind."""
        if not dialogs:
            self.show_placeholder(_EMPTY_ACCOUNT_TEXT)
            return

        self._tree.delete(*self._tree.get_children())
        self._dialogs = {dialog.id: dialog for dialog in dialogs}
        self._notified = None

        for kind in KIND_ORDER:
            of_kind = [dialog for dialog in dialogs if dialog.kind is kind]
            if not of_kind:
                # Do not clutter the tree with empty sections.
                continue
            parent = self._tree.insert(
                "",
                "end",
                iid=f"{_GROUP_IID_PREFIX}{kind.value}",
                text=f"{kind.group_title} ({len(of_kind)})",
                open=True,
                tags=(_TAG_GROUP,),
            )
            for dialog in of_kind:
                self._tree.insert(
                    parent,
                    "end",
                    iid=dialog.id,
                    text=dialog.title,
                    values=(dialog.unread or "",),
                    tags=(_TAG_UNREAD,) if dialog.unread else (),
                )

    def select(self, dialog_id: str) -> None:
        """Select a dialog by id; ids that are not listed are ignored."""
        if dialog_id in self._dialogs:
            self._tree.selection_set(dialog_id)
            self._tree.focus(dialog_id)

    @property
    def tree(self) -> ttk.Treeview:
        """The underlying tree widget, exposed for layout tuning and the tests."""
        return self._tree

    @property
    def selected(self) -> Dialog | None:
        """The currently selected dialog, or ``None`` for a section or placeholder row."""
        selection = self._tree.selection()
        return self._dialogs.get(selection[0]) if selection else None

    def _handle_selection(self, _event: tk.Event) -> None:
        """Notify the main window, ignoring clicks on section and placeholder rows."""
        dialog = self.selected
        if dialog is None or dialog.id == self._notified:
            # Section headers are not dialogs, and Tk can report one selection
            # change twice after the tree was rebuilt.
            return

        self._notified = dialog.id
        if self._on_select is not None:
            self._on_select(dialog)
