"""Tests for the three panels of the main window.

Every test drives the widgets the way a click would -- through the selection of
the underlying Treeview -- so the callbacks the main window relies on are
covered, not just the rendering.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app.models import Account, AccountStatus, Dialog, DialogKind, Message
from Front.accounts.accounts_panel import AccountsPanel
from Front.chats.dialogs_panel import DialogsPanel
from Front.messages.messages_panel import MessagesPanel
from tests.conftest import FakeRepository


# --- accounts panel ----------------------------------------------------------


def test_accounts_panel_lists_every_account(tk_root: tk.Tk, fake_repository: FakeRepository) -> None:
    """One row per account, in file order."""
    panel = AccountsPanel(tk_root)
    panel.set_accounts(fake_repository.accounts())
    assert list(panel.tree.get_children()) == ["a-1", "a-2"]


def test_accounts_panel_shows_name_and_status(tk_root: tk.Tk) -> None:
    """The row carries the name; the narrow status column carries the label."""
    panel = AccountsPanel(tk_root)
    panel.set_accounts(
        [Account(id="a-1", name="Рабочий", phone="+7 999", status=AccountStatus.LIMITED)]
    )
    assert panel.tree.item("a-1", "text") == "Рабочий"
    # Tk returns column values as a tuple of strings.
    assert panel.tree.item("a-1", "values") == ("Ограничен",)


def test_accounts_panel_shows_a_placeholder_when_empty(tk_root: tk.Tk) -> None:
    """An empty accounts file must not leave a blank column."""
    panel = AccountsPanel(tk_root)
    panel.set_accounts([])
    rows = panel.tree.get_children()
    assert len(rows) == 1
    assert panel.tree.item(rows[0], "text") == "Нет аккаунтов"


def test_accounts_panel_placeholder_is_not_reported_as_an_account(tk_root: tk.Tk) -> None:
    """Clicking the placeholder must not fire the callback with a bogus account."""
    seen: list[Account] = []
    panel = AccountsPanel(tk_root, on_select=seen.append)
    panel.set_accounts([])
    panel.tree.selection_set(panel.tree.get_children()[0])
    tk_root.update()
    assert seen == []
    assert panel.selected is None


def test_accounts_panel_reports_the_selected_account(
    tk_root: tk.Tk, fake_repository: FakeRepository
) -> None:
    """Selecting a row hands the account to the main window."""
    seen: list[Account] = []
    panel = AccountsPanel(tk_root, on_select=seen.append)
    panel.set_accounts(fake_repository.accounts())
    panel.select("a-2")
    tk_root.update()
    assert [account.id for account in seen] == ["a-2"]
    assert panel.selected is not None and panel.selected.id == "a-2"


def test_accounts_panel_select_first_picks_the_top_row(
    tk_root: tk.Tk, fake_repository: FakeRepository
) -> None:
    """The window opens with the first account already chosen."""
    seen: list[Account] = []
    panel = AccountsPanel(tk_root, on_select=seen.append)
    panel.set_accounts(fake_repository.accounts())
    panel.select_first()
    tk_root.update()
    assert [account.id for account in seen] == ["a-1"]


def test_accounts_panel_select_first_is_safe_when_empty(tk_root: tk.Tk) -> None:
    """No accounts means no selection and no exception."""
    panel = AccountsPanel(tk_root)
    panel.set_accounts([])
    panel.select_first()
    assert panel.selected is None


def test_accounts_panel_replaces_previous_contents(
    tk_root: tk.Tk, fake_repository: FakeRepository
) -> None:
    """A reload must not append rows to the ones already there."""
    panel = AccountsPanel(tk_root)
    panel.set_accounts(fake_repository.accounts())
    panel.set_accounts(fake_repository.accounts()[:1])
    assert list(panel.tree.get_children()) == ["a-1"]


def test_accounts_panel_context_menu_opens_add_account_modal(tk_root: tk.Tk) -> None:
    """Right-click action opens a modal dialog with phone input controls."""
    panel = AccountsPanel(tk_root)
    panel._open_add_account_dialog()  # pylint: disable=protected-access
    tk_root.update()

    dialogs = [child for child in panel.winfo_children() if isinstance(child, tk.Toplevel)]
    assert len(dialogs) == 1
    dialog = dialogs[0]
    assert dialog.title() == "Добавить аккаунт"

    entries = [
        widget
        for widget in dialog.winfo_children()[0].winfo_children()
        if isinstance(widget, ttk.Entry)
    ]
    assert len(entries) == 1

    buttons = [
        widget
        for widget in dialog.winfo_children()[0].winfo_children()[2].winfo_children()
        if isinstance(widget, ttk.Button)
    ]
    labels = [button.cget("text") for button in buttons]
    assert labels == ["ОК", "ОТМЕНА"]


def test_accounts_panel_modal_cancel_closes_dialog(tk_root: tk.Tk) -> None:
    """Cancel button closes the add-account modal."""
    panel = AccountsPanel(tk_root)
    panel._open_add_account_dialog()  # pylint: disable=protected-access
    tk_root.update()

    dialog = next(child for child in panel.winfo_children() if isinstance(child, tk.Toplevel))
    cancel_button = next(
        widget
        for widget in dialog.winfo_children()[0].winfo_children()[2].winfo_children()
        if isinstance(widget, ttk.Button) and widget.cget("text") == "ОТМЕНА"
    )
    cancel_button.invoke()
    tk_root.update()

    assert not dialog.winfo_exists()


# --- dialogs panel -----------------------------------------------------------


def test_dialogs_panel_starts_with_a_hint(tk_root: tk.Tk) -> None:
    """Before an account is chosen the column explains what to do."""
    panel = DialogsPanel(tk_root)
    rows = panel.tree.get_children()
    assert panel.tree.item(rows[0], "text") == "Выберите аккаунт слева"


def test_dialogs_panel_groups_by_kind_in_a_fixed_order(
    tk_root: tk.Tk, fake_repository: FakeRepository
) -> None:
    """Sections are always contacts, then groups, then channels."""
    panel = DialogsPanel(tk_root)
    panel.set_dialogs(fake_repository.dialogs("a-1"))
    captions = [panel.tree.item(iid, "text") for iid in panel.tree.get_children()]
    assert captions == ["Контакты (1)", "Группы (1)", "Каналы (1)"]


def test_dialogs_panel_puts_each_dialog_under_its_section(
    tk_root: tk.Tk, fake_repository: FakeRepository
) -> None:
    """A dialog is a child of the section matching its kind."""
    panel = DialogsPanel(tk_root)
    panel.set_dialogs(fake_repository.dialogs("a-1"))
    sections = panel.tree.get_children()
    assert [panel.tree.get_children(section) for section in sections] == [
        ("d-1",),
        ("d-2",),
        ("d-3",),
    ]


def test_dialogs_panel_omits_sections_without_dialogs(tk_root: tk.Tk) -> None:
    """An account with only channels shows one section, not three."""
    panel = DialogsPanel(tk_root)
    panel.set_dialogs(
        [Dialog(id="d-1", account_id="a-1", title="Канал", kind=DialogKind.CHANNEL, unread=0)]
    )
    captions = [panel.tree.item(iid, "text") for iid in panel.tree.get_children()]
    assert captions == ["Каналы (1)"]


def test_dialogs_panel_shows_the_unread_counter(
    tk_root: tk.Tk, fake_repository: FakeRepository
) -> None:
    """Unread messages are counted in the column; a read dialog stays blank."""
    panel = DialogsPanel(tk_root)
    panel.set_dialogs(fake_repository.dialogs("a-1"))
    assert panel.tree.item("d-1", "values") == ("3",)
    assert panel.tree.item("d-2", "values") == ("",)


def test_dialogs_panel_reports_an_account_without_dialogs(tk_root: tk.Tk) -> None:
    """The reserve account has no dialogs at all; say so instead of showing nothing."""
    panel = DialogsPanel(tk_root)
    panel.set_dialogs([])
    rows = panel.tree.get_children()
    assert panel.tree.item(rows[0], "text") == "У аккаунта нет диалогов"


def test_dialogs_panel_reports_the_selected_dialog(
    tk_root: tk.Tk, fake_repository: FakeRepository
) -> None:
    """Selecting a dialog hands it to the main window."""
    seen: list[Dialog] = []
    panel = DialogsPanel(tk_root, on_select=seen.append)
    panel.set_dialogs(fake_repository.dialogs("a-1"))
    panel.select("d-3")
    tk_root.update()
    assert [dialog.id for dialog in seen] == ["d-3"]


def test_dialogs_panel_ignores_clicks_on_a_section(
    tk_root: tk.Tk, fake_repository: FakeRepository
) -> None:
    """A section header is a grouping row, not a dialog."""
    seen: list[Dialog] = []
    panel = DialogsPanel(tk_root, on_select=seen.append)
    panel.set_dialogs(fake_repository.dialogs("a-1"))
    panel.tree.selection_set(panel.tree.get_children()[0])
    tk_root.update()
    assert seen == []
    assert panel.selected is None


def test_dialogs_panel_forgets_dialogs_when_reset(
    tk_root: tk.Tk, fake_repository: FakeRepository
) -> None:
    """Switching to an account without dialogs clears the previous selection."""
    panel = DialogsPanel(tk_root)
    panel.set_dialogs(fake_repository.dialogs("a-1"))
    panel.set_dialogs([])
    assert panel.selected is None


# --- messages panel ----------------------------------------------------------


def test_messages_panel_starts_with_a_hint(tk_root: tk.Tk) -> None:
    """Before a dialog is chosen the transcript explains what to do."""
    panel = MessagesPanel(tk_root)
    assert "Выберите диалог" in panel.transcript


def test_messages_panel_renders_the_transcript(
    tk_root: tk.Tk, fake_repository: FakeRepository
) -> None:
    """Author, formatted time and text appear for every message, oldest first."""
    panel = MessagesPanel(tk_root)
    dialog = fake_repository.dialogs("a-1")[0]
    panel.show_dialog(dialog, fake_repository.messages("d-1"))

    transcript = panel.transcript
    assert "Контакт · 15.09.2026 10:00" in transcript
    assert "Привет" in transcript
    assert transcript.index("Привет") < transcript.index("И тебе")


def test_messages_panel_reports_an_empty_dialog(tk_root: tk.Tk) -> None:
    """A dialog without history says so rather than showing the previous one."""
    panel = MessagesPanel(tk_root)
    dialog = Dialog(id="d-9", account_id="a-1", title="Пусто", kind=DialogKind.GROUP, unread=0)
    panel.show_dialog(dialog, [])
    assert panel.transcript == "В этом диалоге пока нет сообщений"


def test_messages_panel_replaces_the_previous_dialog(
    tk_root: tk.Tk, fake_repository: FakeRepository
) -> None:
    """Opening another dialog must not append to the transcript already shown."""
    panel = MessagesPanel(tk_root)
    dialog = fake_repository.dialogs("a-1")[0]
    panel.show_dialog(dialog, fake_repository.messages("d-1"))
    panel.show_dialog(
        dialog, [Message(author="Кто-то", sent_at="", text="Новое", outgoing=False)]
    )

    assert "Привет" not in panel.transcript
    assert "Новое" in panel.transcript


def test_messages_panel_marks_outgoing_messages(
    tk_root: tk.Tk, fake_repository: FakeRepository
) -> None:
    """Both directions are rendered and the outgoing style is actually applied."""
    panel = MessagesPanel(tk_root)
    dialog = fake_repository.dialogs("a-1")[0]
    panel.show_dialog(dialog, fake_repository.messages("d-1"))

    assert "Я · 15.09.2026 10:05" in panel.transcript
    assert panel.text.tag_ranges("outgoing")
    assert panel.text.tag_ranges("incoming")


def test_messages_panel_transcript_is_read_only(
    tk_root: tk.Tk, fake_repository: FakeRepository
) -> None:
    """The transcript is a view, not an input field: edits must be refused."""
    panel = MessagesPanel(tk_root)
    dialog = fake_repository.dialogs("a-1")[0]
    panel.show_dialog(dialog, fake_repository.messages("d-1"))

    before = panel.transcript
    assert str(panel.text["state"]) == "disabled"

    # A disabled Text silently discards edits instead of raising.
    panel.text.insert("end", "напечатанное вручную")
    panel.text.delete("1.0", "2.0")
    assert panel.transcript == before
