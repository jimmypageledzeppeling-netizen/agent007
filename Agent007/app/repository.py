"""Data access behind the UI.

Step 2 has no database yet, so the three columns are fed from the JSON files in
``Agent007/data``. :class:`DataRepository` is the seam that keeps that
temporary: step 3 swaps :class:`JsonFileRepository` for a MySQL-backed
implementation without the panels noticing.

A missing or malformed file is logged as an error and degrades to an empty list
instead of raising -- the window must still open, the same way
:mod:`app.health` reports a dead dependency rather than propagating it.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol, TypeVar

from app.config import Settings, get_settings
from app.logging_config import get_logger
from app.models import Account, Dialog, Message

_LOGGER = get_logger(__name__)

ACCOUNTS_FILENAME = "accounts.json"
DIALOGS_FILENAME = "dialogs.json"
MESSAGES_FILENAME = "messages.json"

_T = TypeVar("_T")


class DataRepository(Protocol):
    """Read-only source of the objects the UI displays."""

    def accounts(self) -> list[Account]:
        """Return every managed Telegram account."""
        raise NotImplementedError

    def dialogs(self, account_id: str) -> list[Dialog]:
        """Return the contacts, groups and channels of one account."""
        raise NotImplementedError

    def messages(self, dialog_id: str) -> list[Message]:
        """Return the messages of one dialog, oldest first."""
        raise NotImplementedError


class JsonFileRepository:
    """:class:`DataRepository` backed by the JSON files in the ``data`` directory.

    Each file is read from disk at most once and then served from memory; call
    :meth:`reload` to pick up changes made while the application is running.
    """

    def __init__(self, data_dir: Path | None = None, *, settings: Settings | None = None) -> None:
        """Store the directory to read from, defaulting to ``Settings.data_path``."""
        if data_dir is None:
            data_dir = (settings or get_settings()).data_path
        self._data_dir = Path(data_dir)
        self._cache: dict[str, dict[str, Any]] = {}

    @property
    def data_dir(self) -> Path:
        """Directory the JSON files are read from."""
        return self._data_dir

    def reload(self) -> None:
        """Drop the in-memory copies so the next call re-reads the files."""
        self._cache.clear()

    def accounts(self) -> list[Account]:
        """Return every managed Telegram account, in file order."""
        raw = self._document(ACCOUNTS_FILENAME).get("accounts", [])
        return self._parse(raw, Account.from_dict, "account")

    def dialogs(self, account_id: str) -> list[Dialog]:
        """Return the dialogs of ``account_id``; empty for an unknown account."""
        raw = self._section(DIALOGS_FILENAME, "dialogs").get(account_id, [])
        return self._parse(raw, lambda item: Dialog.from_dict(item, account_id), "dialog")

    def messages(self, dialog_id: str) -> list[Message]:
        """Return the messages of ``dialog_id``; empty for a dialog without history."""
        raw = self._section(MESSAGES_FILENAME, "messages").get(dialog_id, [])
        return self._parse(raw, Message.from_dict, "message")

    def _document(self, filename: str) -> dict[str, Any]:
        """Return a parsed file, reading it from disk on first use only."""
        if filename not in self._cache:
            self._cache[filename] = self._read(self._data_dir / filename)
        return self._cache[filename]

    def _section(self, filename: str, key: str) -> Mapping[str, Any]:
        """Return the ``key`` object of a file, or an empty mapping if it is malformed."""
        section = self._document(filename).get(key, {})
        if not isinstance(section, Mapping):
            _LOGGER.error(
                "Section '%s' of %s must be a JSON object, got %s",
                key,
                filename,
                type(section).__name__,
            )
            return {}
        return section

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        """Parse a JSON object, logging and absorbing any I/O or syntax error."""
        try:
            with path.open(encoding="utf-8") as handle:
                document = json.load(handle)
        except FileNotFoundError:
            _LOGGER.error("Data file %s is missing; the UI will show an empty list", path)
            return {}
        except (OSError, json.JSONDecodeError):
            # Logged with a traceback: a broken data file is a real defect, but not
            # one that should keep the main window from opening.
            _LOGGER.exception("Data file %s could not be read", path)
            return {}

        if not isinstance(document, dict):
            _LOGGER.error(
                "Data file %s must contain a JSON object, got %s",
                path,
                type(document).__name__,
            )
            return {}
        return document

    @staticmethod
    def _parse(
        raw: Any,
        factory: Callable[[Mapping[str, Any]], _T],
        label: str,
    ) -> list[_T]:
        """Convert records into objects, skipping and logging the invalid ones."""
        if not isinstance(raw, list):
            _LOGGER.error(
                "Expected a list of %s records, got %s", label, type(raw).__name__
            )
            return []

        parsed: list[_T] = []
        for index, item in enumerate(raw):
            if not isinstance(item, Mapping):
                _LOGGER.error("Skipping %s record #%d: not a JSON object", label, index)
                continue
            try:
                parsed.append(factory(item))
            except ValueError as error:
                _LOGGER.error("Skipping %s record #%d: %s", label, index, error)
        return parsed
