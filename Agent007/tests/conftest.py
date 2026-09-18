"""Shared fixtures. Tests never read the developer's real .env."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from app.config import Settings
from app.models import Account, AccountStatus, Dialog, DialogKind, Message


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration tests unless they were explicitly requested with -m integration."""
    if "integration" in (config.getoption("-m") or ""):
        return
    skip = pytest.mark.skip(reason="needs docker compose up -d; run with -m integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(name="settings")
def settings_fixture(tmp_path: Path) -> Settings:
    """Settings pointed at a throwaway log directory, isolated from .env."""
    return Settings(
        _env_file=None,
        app_env="test",
        log_level="DEBUG",
        log_dir=tmp_path / "Log",
        mysql_password="test-password",
    )


class FakeRepository:
    """In-memory :class:`~app.repository.DataRepository` for the UI tests.

    Keeps the panel tests independent of the JSON fixtures: they assert on
    widget behaviour, not on the contents of ``data``.
    """

    def __init__(
        self,
        accounts: Sequence[Account] = (),
        dialogs: dict[str, list[Dialog]] | None = None,
        messages: dict[str, list[Message]] | None = None,
    ) -> None:
        """Store the canned answers this repository will hand out."""
        self._accounts = list(accounts)
        self._dialogs = dialogs or {}
        self._messages = messages or {}
        self.dialog_calls: list[str] = []
        self.message_calls: list[str] = []
        self.clear_calls: list[str] = []

    def accounts(self) -> list[Account]:
        """Return the canned accounts."""
        return list(self._accounts)

    def dialogs(self, account_id: str) -> list[Dialog]:
        """Return the canned dialogs of ``account_id`` and record the call."""
        self.dialog_calls.append(account_id)
        return list(self._dialogs.get(account_id, []))

    def messages(self, dialog_id: str) -> list[Message]:
        """Return the canned messages of ``dialog_id`` and record the call."""
        self.message_calls.append(dialog_id)
        return list(self._messages.get(dialog_id, []))

    def clear_account_chats(self, account_id: str) -> tuple[int, int]:
        """Record bulk-clear request and wipe canned dialogs/messages for account."""
        self.clear_calls.append(account_id)
        dialogs = self._dialogs.get(account_id, [])
        cleared = len(dialogs)
        for dialog in dialogs:
            self._messages.pop(dialog.id, None)
        self._dialogs[account_id] = []
        return (cleared, 0)


@pytest.fixture(name="tk_root")
def tk_root_fixture() -> Iterator[tk.Tk]:
    """A hidden Tk root, skipping the test when no display or Tk is available."""
    try:
        root = tk.Tk()
    except tk.TclError as error:  # pragma: no cover - depends on the environment
        pytest.skip(f"Tk is unavailable: {error}")
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()


@pytest.fixture(name="fake_repository")
def fake_repository_fixture() -> FakeRepository:
    """Two accounts, dialogs of all three kinds and a two-message transcript."""
    accounts = [
        Account(id="a-1", name="Первый", phone="+7 000 000-00-01", status=AccountStatus.ONLINE),
        Account(id="a-2", name="Второй", phone="+7 000 000-00-02", status=AccountStatus.OFFLINE),
    ]
    dialogs = {
        "a-1": [
            Dialog(id="d-1", account_id="a-1", title="Контакт", kind=DialogKind.CONTACT, unread=3),
            Dialog(id="d-2", account_id="a-1", title="Группа", kind=DialogKind.GROUP, unread=0),
            Dialog(id="d-3", account_id="a-1", title="Канал", kind=DialogKind.CHANNEL, unread=7),
        ],
        "a-2": [],
    }
    messages = {
        "d-1": [
            Message(author="Контакт", sent_at="2026-09-15T10:00:00", text="Привет", outgoing=False),
            Message(author="Я", sent_at="2026-09-15T10:05:00", text="И тебе", outgoing=True),
        ],
    }
    return FakeRepository(accounts, dialogs, messages)
