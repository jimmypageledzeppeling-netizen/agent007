"""Tests for app.repository, including the shipped JSON fixtures themselves."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from app.config import Settings
from app.models import DialogKind
from app.repository import (
    ACCOUNTS_FILENAME,
    DIALOGS_FILENAME,
    MESSAGES_FILENAME,
    JsonFileRepository,
)


@pytest.fixture(name="repository")
def repository_fixture() -> JsonFileRepository:
    """Repository over the real data directory, independent of the developer's .env."""
    return JsonFileRepository(settings=Settings(_env_file=None))


def _write(directory: Path, filename: str, document: object) -> None:
    """Write ``document`` as JSON into ``directory``, creating it if needed."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_text(
        json.dumps(document, ensure_ascii=False), encoding="utf-8"
    )


# --- the shipped fixtures ----------------------------------------------------


def test_shipped_accounts_are_loaded(repository: JsonFileRepository) -> None:
    """The accounts column has something to show out of the box."""
    accounts = repository.accounts()
    assert len(accounts) >= 2
    assert all(account.id and account.name for account in accounts)


def test_shipped_account_ids_are_unique(repository: JsonFileRepository) -> None:
    """Ids double as Treeview row ids, so duplicates would silently drop rows."""
    ids = [account.id for account in repository.accounts()]
    assert len(ids) == len(set(ids))


def test_shipped_dialogs_cover_all_three_kinds(repository: JsonFileRepository) -> None:
    """The test data must exercise the contacts, groups and channels sections."""
    kinds = {
        dialog.kind
        for account in repository.accounts()
        for dialog in repository.dialogs(account.id)
    }
    assert kinds == set(DialogKind)


def test_shipped_dialogs_are_bound_to_their_account(repository: JsonFileRepository) -> None:
    """Every dialog carries the id of the account it was read under."""
    for account in repository.accounts():
        assert all(
            dialog.account_id == account.id for dialog in repository.dialogs(account.id)
        )


def test_shipped_messages_reference_existing_dialogs(repository: JsonFileRepository) -> None:
    """messages.json must not contain dialog ids that dialogs.json does not define."""
    known = {
        dialog.id
        for account in repository.accounts()
        for dialog in repository.dialogs(account.id)
    }
    raw = json.loads((repository.data_dir / MESSAGES_FILENAME).read_text(encoding="utf-8"))
    assert set(raw["messages"]) <= known


def test_shipped_transcript_has_both_directions(repository: JsonFileRepository) -> None:
    """Incoming and outgoing rendering are both reachable with the shipped data."""
    directions = {
        message.outgoing
        for account in repository.accounts()
        for dialog in repository.dialogs(account.id)
        for message in repository.messages(dialog.id)
    }
    assert directions == {True, False}


# --- degraded inputs ---------------------------------------------------------


def test_missing_files_yield_empty_lists(tmp_path: Path) -> None:
    """A missing data file must not keep the main window from opening."""
    repository = JsonFileRepository(tmp_path)
    assert repository.accounts() == []
    assert repository.dialogs("acc-1") == []
    assert repository.messages("dlg-1") == []


def test_missing_file_is_logged_as_an_error(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Promt.md requires failures to reach the error log rather than be swallowed."""
    with caplog.at_level(logging.ERROR, logger="app.repository"):
        JsonFileRepository(tmp_path).accounts()
    assert any(ACCOUNTS_FILENAME in record.getMessage() for record in caplog.records)


def test_malformed_json_is_logged_and_survived(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A broken file is reported with a traceback and degrades to an empty list."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / ACCOUNTS_FILENAME).write_text("{not json", encoding="utf-8")
    with caplog.at_level(logging.ERROR, logger="app.repository"):
        assert JsonFileRepository(tmp_path).accounts() == []
    assert caplog.records


def test_top_level_array_is_rejected(tmp_path: Path) -> None:
    """The files are objects keyed by section; a bare array is a defect."""
    _write(tmp_path, ACCOUNTS_FILENAME, [{"id": "acc-1", "name": "Имя"}])
    assert JsonFileRepository(tmp_path).accounts() == []


def test_non_object_section_is_rejected(tmp_path: Path) -> None:
    """dialogs.json maps account ids to lists; anything else is ignored."""
    _write(tmp_path, DIALOGS_FILENAME, {"dialogs": ["acc-1"]})
    assert JsonFileRepository(tmp_path).dialogs("acc-1") == []


def test_non_list_record_collection_is_rejected(tmp_path: Path) -> None:
    """A section value that is not a list cannot be iterated into objects."""
    _write(tmp_path, ACCOUNTS_FILENAME, {"accounts": {"id": "acc-1"}})
    assert JsonFileRepository(tmp_path).accounts() == []


def test_invalid_records_are_skipped_not_fatal(tmp_path: Path) -> None:
    """One bad account must not hide the good ones."""
    _write(
        tmp_path,
        ACCOUNTS_FILENAME,
        {"accounts": [{"name": "Без id"}, "строка", {"id": "acc-2", "name": "Годный"}]},
    )
    accounts = JsonFileRepository(tmp_path).accounts()
    assert [account.id for account in accounts] == ["acc-2"]


def test_unknown_account_has_no_dialogs(tmp_path: Path) -> None:
    """Selecting an account absent from dialogs.json shows an empty list."""
    _write(tmp_path, DIALOGS_FILENAME, {"dialogs": {"acc-1": []}})
    assert JsonFileRepository(tmp_path).dialogs("acc-404") == []


def test_dialog_without_history_has_no_messages(tmp_path: Path) -> None:
    """A dialog missing from messages.json is empty, not an error."""
    _write(tmp_path, MESSAGES_FILENAME, {"messages": {}})
    assert JsonFileRepository(tmp_path).messages("dlg-1") == []


# --- caching -----------------------------------------------------------------


def test_files_are_read_once(tmp_path: Path) -> None:
    """The second call is served from memory, so deleting the file changes nothing."""
    _write(tmp_path, ACCOUNTS_FILENAME, {"accounts": [{"id": "acc-1", "name": "Имя"}]})
    repository = JsonFileRepository(tmp_path)
    assert len(repository.accounts()) == 1

    (tmp_path / ACCOUNTS_FILENAME).unlink()
    assert len(repository.accounts()) == 1


def test_reload_picks_up_changes(tmp_path: Path) -> None:
    """reload() drops the cache so an edited file is visible without a restart."""
    _write(tmp_path, ACCOUNTS_FILENAME, {"accounts": [{"id": "acc-1", "name": "Имя"}]})
    repository = JsonFileRepository(tmp_path)
    assert len(repository.accounts()) == 1

    _write(
        tmp_path,
        ACCOUNTS_FILENAME,
        {"accounts": [{"id": "acc-1", "name": "Имя"}, {"id": "acc-2", "name": "Ещё"}]},
    )
    repository.reload()
    assert len(repository.accounts()) == 2


def test_data_dir_defaults_to_the_settings_value() -> None:
    """Only app.config decides where the data lives."""
    settings = Settings(_env_file=None)
    assert JsonFileRepository(settings=settings).data_dir == settings.data_path
