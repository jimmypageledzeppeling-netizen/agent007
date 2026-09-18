"""Value objects the UI renders.

Deliberately free of persistence logic: the same types are produced today by the
JSON fixtures in :mod:`app.repository` and later by the MySQL layer, so the
panels never learn where their data came from.

Parsing is lenient about optional fields but strict about identity: a record
without an ``id`` cannot be selected in the UI, so it is rejected outright.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

_UNKNOWN_TIME = "—"


def _require(raw: Mapping[str, Any], key: str, context: str) -> str:
    """Return a non-empty string field, raising :class:`ValueError` if it is missing."""
    value = str(raw.get(key, "")).strip()
    if not value:
        raise ValueError(f"{context}: field '{key}' is missing or empty")
    return value


def _optional_int(raw: Mapping[str, Any], key: str) -> int:
    """Return a non-negative integer field, falling back to ``0`` on bad input."""
    try:
        return max(0, int(raw.get(key, 0)))
    except (TypeError, ValueError):
        return 0


class AccountStatus(str, Enum):
    """Connection state of a Telegram account as reported by the data source."""

    ONLINE = "online"
    OFFLINE = "offline"
    LIMITED = "limited"
    UNKNOWN = "unknown"

    @classmethod
    def parse(cls, value: Any) -> AccountStatus:
        """Return the matching member, or :attr:`UNKNOWN` for unrecognised input."""
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            return cls.UNKNOWN

    @property
    def label(self) -> str:
        """Human-readable status for display in the accounts column."""
        return _STATUS_LABELS[self]


_STATUS_LABELS = {
    AccountStatus.ONLINE: "В сети",
    AccountStatus.OFFLINE: "Не в сети",
    AccountStatus.LIMITED: "Ограничен",
    AccountStatus.UNKNOWN: "Неизвестно",
}


class DialogKind(str, Enum):
    """Type of a Telegram dialog: a private contact, a group or a channel."""

    CONTACT = "contact"
    GROUP = "group"
    CHANNEL = "channel"

    @classmethod
    def parse(cls, value: Any) -> DialogKind:
        """Return the matching member, or :attr:`CONTACT` for unrecognised input."""
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            return cls.CONTACT

    @property
    def group_title(self) -> str:
        """Caption of the section this kind is listed under in the dialogs column."""
        return _KIND_TITLES[self]

    @property
    def label(self) -> str:
        """Singular name of the kind, used in the message panel header."""
        return _KIND_LABELS[self]


_KIND_TITLES = {
    DialogKind.CONTACT: "Контакты",
    DialogKind.GROUP: "Группы",
    DialogKind.CHANNEL: "Каналы",
}

_KIND_LABELS = {
    DialogKind.CONTACT: "Контакт",
    DialogKind.GROUP: "Группа",
    DialogKind.CHANNEL: "Канал",
}


@dataclass(frozen=True, slots=True)
class Account:
    """A Telegram account managed by the application."""

    id: str
    name: str
    phone: str
    status: AccountStatus

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Account:
        """Build an account from one ``accounts.json`` record."""
        return cls(
            id=_require(raw, "id", "account"),
            name=_require(raw, "name", "account"),
            phone=str(raw.get("phone", "")).strip(),
            status=AccountStatus.parse(raw.get("status")),
        )


@dataclass(frozen=True, slots=True)
class Dialog:
    """A contact, group or channel belonging to one account."""

    id: str
    account_id: str
    title: str
    kind: DialogKind
    unread: int

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], account_id: str) -> Dialog:
        """Build a dialog from one ``dialogs.json`` record of ``account_id``."""
        return cls(
            id=_require(raw, "id", "dialog"),
            account_id=account_id,
            title=_require(raw, "title", "dialog"),
            kind=DialogKind.parse(raw.get("kind")),
            unread=_optional_int(raw, "unread"),
        )


@dataclass(frozen=True, slots=True)
class Message:
    """A single message inside a dialog."""

    author: str
    sent_at: str
    text: str
    outgoing: bool
    media_kind: str
    media_path: str
    media_caption: str
    media_mime: str

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Message:
        """Build a message from one ``messages.json`` record."""
        return cls(
            author=_require(raw, "author", "message"),
            sent_at=str(raw.get("sent_at", "")).strip(),
            text=str(raw.get("text", "")),
            outgoing=bool(raw.get("outgoing", False)),
            media_kind=str(raw.get("media_kind", "none") or "none").strip().lower(),
            media_path=str(raw.get("media_path", "")).strip(),
            media_caption=str(raw.get("media_caption", "")),
            media_mime=str(raw.get("media_mime", "")).strip(),
        )

    @property
    def time_label(self) -> str:
        """``sent_at`` formatted for the transcript, or the raw value if unparsable."""
        if not self.sent_at:
            return _UNKNOWN_TIME
        try:
            return datetime.fromisoformat(self.sent_at).strftime("%d.%m.%Y %H:%M")
        except ValueError:
            return self.sent_at
