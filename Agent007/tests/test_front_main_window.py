"""Tests for Front.main_window: the column layout and the wiring between panels."""

from __future__ import annotations

import tkinter as tk

import pytest

from Front.accounts.accounts_panel import AccountsPanel
from Front.chats.dialogs_panel import DialogsPanel
from Front.main_window import COLUMN_WEIGHTS, UNIFORM_GROUP, MainWindow
from Front.messages.messages_panel import MessagesPanel
from tests.conftest import FakeRepository


@pytest.fixture(name="window")
def window_fixture(tk_root: tk.Tk, fake_repository: FakeRepository) -> MainWindow:
    """A main window fed from the in-memory repository."""
    window = MainWindow(tk_root, fake_repository)
    tk_root.update()
    return window


# --- layout ------------------------------------------------------------------


def test_window_has_the_three_sections(window: MainWindow) -> None:
    """Accounts, dialogs and transcript, left to right."""
    assert [type(panel) for panel in window.panels] == [
        AccountsPanel,
        DialogsPanel,
        MessagesPanel,
    ]


def test_sections_sit_in_one_row_of_three_columns(window: MainWindow) -> None:
    """Each panel occupies its own column of the single layout row."""
    positions = [(panel.grid_info()["row"], panel.grid_info()["column"]) for panel in window.panels]
    assert positions == [(0, 0), (0, 1), (0, 2)]


def test_sections_fill_the_available_space(window: MainWindow) -> None:
    """Panels stretch in both directions so the window has no dead margins."""
    assert all(panel.grid_info()["sticky"] == "nesw" for panel in window.panels)


def test_column_weights_encode_the_agreed_proportions(window: MainWindow) -> None:
    """20% / 30% / 50%, declared as grid weights."""
    weights = [
        window.container.grid_columnconfigure(index)["weight"]
        for index in range(len(COLUMN_WEIGHTS))
    ]
    assert weights == [20, 30, 50]


def test_columns_share_one_uniform_group(window: MainWindow) -> None:
    """Without a uniform group the weights would only split the leftover space."""
    groups = {
        str(window.container.grid_columnconfigure(index)["uniform"])
        for index in range(len(COLUMN_WEIGHTS))
    }
    assert groups == {UNIFORM_GROUP}


def test_rendered_widths_follow_the_proportions(
    tk_root: tk.Tk, fake_repository: FakeRepository
) -> None:
    """The panels really are laid out 20/30/50, not just configured that way."""
    window = MainWindow(tk_root, fake_repository)
    # Widths are only meaningful once the window is mapped: a withdrawn window
    # reports 1 pixel for every child.
    tk_root.deiconify()
    tk_root.geometry("1200x700")
    tk_root.update()

    widths = [panel.winfo_width() for panel in window.panels]
    total = sum(widths)
    shares = [width / total for width in widths]
    assert shares == pytest.approx([0.20, 0.30, 0.50], abs=0.02)


# --- wiring ------------------------------------------------------------------


def test_window_preselects_the_first_account(
    window: MainWindow, fake_repository: FakeRepository
) -> None:
    """The window opens on a populated view instead of three empty columns."""
    assert window.accounts_panel.selected is not None
    assert window.accounts_panel.selected.id == "a-1"
    assert fake_repository.dialog_calls == ["a-1"]


def test_selecting_an_account_fills_the_dialogs_column(window: MainWindow) -> None:
    """The dialogs of the preselected account are already listed."""
    tree = window.dialogs_panel.tree
    listed = [child for section in tree.get_children() for child in tree.get_children(section)]
    assert listed == ["d-1", "d-2", "d-3"]


def test_selecting_a_dialog_shows_its_transcript(
    window: MainWindow, fake_repository: FakeRepository
) -> None:
    """Choosing a dialog asks the repository for its messages and renders them."""
    window.dialogs_panel.select("d-1")
    window.master.update()

    assert fake_repository.message_calls == ["d-1"]
    assert "Привет" in window.messages_panel.transcript


def test_switching_account_resets_the_transcript(window: MainWindow) -> None:
    """A transcript from the previous account must not stay on screen."""
    window.dialogs_panel.select("d-1")
    window.master.update()
    assert "Привет" in window.messages_panel.transcript

    window.accounts_panel.select("a-2")
    window.master.update()
    assert "Выберите диалог" in window.messages_panel.transcript


def test_account_without_dialogs_shows_a_hint(window: MainWindow) -> None:
    """The second account has no dialogs; the column says so."""
    window.accounts_panel.select("a-2")
    window.master.update()

    tree = window.dialogs_panel.tree
    rows = tree.get_children()
    assert [tree.item(iid, "text") for iid in rows] == ["У аккаунта нет диалогов"]


def test_window_opens_with_an_empty_repository(tk_root: tk.Tk) -> None:
    """No accounts at all is a valid state, not a crash on startup."""
    window = MainWindow(tk_root, FakeRepository())
    tk_root.update()

    assert window.accounts_panel.selected is None
    assert "Выберите аккаунт слева" in [
        window.dialogs_panel.tree.item(iid, "text")
        for iid in window.dialogs_panel.tree.get_children()
    ]


def test_window_reloads_accounts_on_demand(
    window: MainWindow, fake_repository: FakeRepository
) -> None:
    """load_accounts() can be called again, e.g. after new data arrives."""
    window.load_accounts()
    window.master.update()
    assert list(window.accounts_panel.tree.get_children()) == ["a-1", "a-2"]
    assert fake_repository.dialog_calls == ["a-1", "a-1"]


def test_clearing_account_chats_calls_repository_and_refreshes_dialogs(
    window: MainWindow, fake_repository: FakeRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Clear action wipes dialogs via repository and refreshes the center/right panels."""
    monkeypatch.setattr("Front.main_window.messagebox.askyesno", lambda *args, **kwargs: True)

    account = window.accounts_panel.selected
    assert account is not None
    assert list(window.dialogs_panel.tree.get_children())

    window._on_clear_account_requested(account)  # pylint: disable=protected-access
    window.master.update()

    assert fake_repository.clear_calls == ["a-1"]
    rows = window.dialogs_panel.tree.get_children()
    assert [window.dialogs_panel.tree.item(iid, "text") for iid in rows] == [
        "У аккаунта нет диалогов"
    ]
