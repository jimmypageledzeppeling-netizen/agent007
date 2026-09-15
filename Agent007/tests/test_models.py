"""Tests for app.models."""

from __future__ import annotations

import pytest

from app.models import Account, AccountStatus, Dialog, DialogKind, Message


def test_account_is_parsed_from_a_full_record() -> None:
    """Every field of accounts.json reaches the object."""
    account = Account.from_dict(
        {"id": "acc-1", "name": "Рабочий", "phone": "+7 999", "status": "online"}
    )
    assert (account.id, account.name, account.phone) == ("acc-1", "Рабочий", "+7 999")
    assert account.status is AccountStatus.ONLINE


def test_account_without_id_is_rejected() -> None:
    """A record with no identity cannot be selected in the UI, so it must not load."""
    with pytest.raises(ValueError, match="id"):
        Account.from_dict({"name": "Без идентификатора"})


def test_account_without_name_is_rejected() -> None:
    """An unnamed account would render as an empty row."""
    with pytest.raises(ValueError, match="name"):
        Account.from_dict({"id": "acc-1"})


def test_account_phone_is_optional() -> None:
    """A missing phone degrades to an empty string rather than failing."""
    assert Account.from_dict({"id": "acc-1", "name": "Имя"}).phone == ""


def test_unknown_account_status_does_not_fail() -> None:
    """An unexpected status code maps to UNKNOWN instead of raising."""
    account = Account.from_dict({"id": "acc-1", "name": "Имя", "status": "wat"})
    assert account.status is AccountStatus.UNKNOWN
    assert account.status.label == "Неизвестно"


def test_every_account_status_has_a_label() -> None:
    """The accounts column must never show a blank status."""
    assert all(status.label for status in AccountStatus)


def test_dialog_is_parsed_and_bound_to_its_account() -> None:
    """The account id comes from the enclosing section, not from the record."""
    dialog = Dialog.from_dict({"id": "d-1", "title": "Чат", "kind": "group", "unread": 4}, "acc-1")
    assert (dialog.id, dialog.title, dialog.account_id) == ("d-1", "Чат", "acc-1")
    assert dialog.kind is DialogKind.GROUP
    assert dialog.unread == 4


def test_dialog_without_title_is_rejected() -> None:
    """A titleless dialog is not displayable."""
    with pytest.raises(ValueError, match="title"):
        Dialog.from_dict({"id": "d-1"}, "acc-1")


def test_unknown_dialog_kind_falls_back_to_contact() -> None:
    """An unexpected kind still has to land in one of the three sections."""
    dialog = Dialog.from_dict({"id": "d-1", "title": "Чат", "kind": "bot"}, "acc-1")
    assert dialog.kind is DialogKind.CONTACT


@pytest.mark.parametrize("raw", [{"unread": -5}, {"unread": "много"}, {}])
def test_unread_counter_is_never_negative_or_broken(raw: dict) -> None:
    """Bad or missing counters become zero, so the column stays numeric."""
    record = {"id": "d-1", "title": "Чат", **raw}
    assert Dialog.from_dict(record, "acc-1").unread == 0


def test_every_dialog_kind_has_both_captions() -> None:
    """Sections need a plural caption, the message header a singular one."""
    assert all(kind.group_title and kind.label for kind in DialogKind)


def test_message_is_parsed_from_a_full_record() -> None:
    """Author, text and direction reach the transcript."""
    message = Message.from_dict(
        {"author": "Я", "sent_at": "2026-09-15T08:40:00", "text": "Привет", "outgoing": True}
    )
    assert (message.author, message.text, message.outgoing) == ("Я", "Привет", True)


def test_message_without_author_is_rejected() -> None:
    """The transcript prefixes every message with its author."""
    with pytest.raises(ValueError, match="author"):
        Message.from_dict({"text": "Привет"})


def test_message_defaults_to_incoming() -> None:
    """Only an explicit flag marks a message as sent by the operator."""
    assert Message.from_dict({"author": "Кто-то", "text": "Привет"}).outgoing is False


def test_message_time_is_formatted_for_display() -> None:
    """An ISO timestamp is shown in the local day-first format."""
    message = Message.from_dict({"author": "Я", "sent_at": "2026-09-15T08:40:00"})
    assert message.time_label == "15.09.2026 08:40"


def test_unparsable_message_time_is_shown_as_is() -> None:
    """A non-ISO value is still worth showing; it must not break rendering."""
    message = Message.from_dict({"author": "Я", "sent_at": "вчера"})
    assert message.time_label == "вчера"


def test_missing_message_time_has_a_placeholder() -> None:
    """An absent timestamp renders as a dash, not as an empty gap."""
    assert Message.from_dict({"author": "Я"}).time_label == "—"
