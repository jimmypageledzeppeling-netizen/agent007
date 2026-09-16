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

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol, TypeVar

from telethon import errors, utils
from telethon.sync import TelegramClient
from telethon.tl.types import Channel, Chat, User

from app.config import Settings, get_settings
from app.logging_config import get_logger
from app.models import Account, AccountStatus, Dialog, DialogKind, Message

_LOGGER = get_logger(__name__)

ACCOUNTS_FILENAME = "accounts.json"
DIALOGS_FILENAME = "dialogs.json"
MESSAGES_FILENAME = "messages.json"
LIVE_ACCOUNTS_FILENAME = "live_accounts.json"

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

    def add_account(
        self,
        phone: str,
        request_code: Callable[[str], str | None],
        request_password: Callable[[str], str | None],
    ) -> Account:
        """Add a Telegram account to the data source and return it."""
        raise NotImplementedError

    def remove_account(self, account_id: str) -> bool:
        """Remove an account from the data source."""
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

    def add_account(
        self,
        phone: str,
        request_code: Callable[[str], str | None],
        request_password: Callable[[str], str | None],
    ) -> Account:
        """Reject account creation outside live mode."""
        raise RuntimeError("Добавление аккаунта доступно только в DATA_MODE=live")

    def remove_account(self, account_id: str) -> bool:
        """Reject account removal outside live mode."""
        raise RuntimeError("Удаление аккаунта доступно только в DATA_MODE=live")

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


class LiveRepository:
    """Telegram-backed repository with local JSON account storage and session files."""

    def __init__(self, *, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._data_dir = self._settings.data_path
        self._sessions_dir = self._settings.sessions_path
        self._accounts_path = self._data_dir / LIVE_ACCOUNTS_FILENAME
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

    def accounts(self) -> list[Account]:
        """Return connected accounts persisted in accounts.json."""
        raw = self._document().get("accounts", [])
        return JsonFileRepository._parse(raw, Account.from_dict, "account")

    def dialogs(self, account_id: str) -> list[Dialog]:
        """Read dialogs from Telegram for one connected account."""
        record = self._find_record(account_id)
        if record is None:
            return []

        try:
            return self._in_worker(lambda: self._load_dialogs(account_id, record))
        except (errors.RPCError, OSError):
            _LOGGER.exception("Could not load dialogs for account %s", account_id)
            return []

    def messages(self, dialog_id: str) -> list[Message]:
        """Read messages from Telegram for one dialog id produced by dialogs()."""
        account_id, peer_id = self._split_dialog_id(dialog_id)
        if account_id is None:
            return []

        record = self._find_record(account_id)
        if record is None:
            return []

        try:
            return self._in_worker(lambda: self._load_messages(record, peer_id))
        except (errors.RPCError, OSError, ValueError):
            _LOGGER.exception("Could not load messages for dialog %s", dialog_id)
            return []

    def add_account(
        self,
        phone: str,
        request_code: Callable[[str], str | None],
        request_password: Callable[[str], str | None],
    ) -> Account:
        """Authenticate in Telegram and persist account metadata."""
        clean_phone = phone.strip()
        if not clean_phone:
            raise ValueError("Номер телефона не указан")

        temp_record = {"id": f"phone-{clean_phone}", "phone": clean_phone}
        sent_hash = self._in_worker(lambda: self._send_code_request(clean_phone, temp_record))
        code = (request_code(clean_phone) or "").strip()
        if not code:
            raise ValueError("Код подтверждения не введён")

        try:
            account = self._in_worker(
                lambda: self._sign_in_with_code(clean_phone, temp_record, code, sent_hash)
            )
        except errors.SessionPasswordNeededError:
            password = (request_password(clean_phone) or "").strip()
            if not password:
                raise ValueError("Пароль 2FA не введён")
            account = self._in_worker(
                lambda: self._sign_in_with_password(clean_phone, temp_record, password)
            )

        self._rename_session(temp_record["id"], account.id)
        self._upsert_account(account)
        return account

    def _load_dialogs(self, account_id: str, record: Mapping[str, Any]) -> list[Dialog]:
        with self._client(record) as client:
            if not client.is_user_authorized():
                return []

            dialogs: list[Dialog] = []
            for item in client.iter_dialogs(limit=200):
                kind = self._dialog_kind(item.entity)
                dialogs.append(
                    Dialog(
                        id=f"{account_id}:{item.id}",
                        account_id=account_id,
                        title=item.name or str(item.id),
                        kind=kind,
                        unread=max(0, int(item.unread_count or 0)),
                    )
                )
            return dialogs

    def _load_messages(self, record: Mapping[str, Any], peer_id: int) -> list[Message]:
        with self._client(record) as client:
            if not client.is_user_authorized():
                return []

            items = list(reversed(client.get_messages(peer_id, limit=100)))
            result: list[Message] = []
            for item in items:
                author = "Я" if item.out else self._author_name(item)
                result.append(
                    Message(
                        author=author,
                        sent_at=item.date.isoformat() if item.date else "",
                        text=item.message or "",
                        outgoing=bool(item.out),
                    )
                )
            return result

    def _send_code_request(
        self,
        clean_phone: str,
        temp_record: Mapping[str, Any],
    ) -> str:
        with self._client(temp_record) as client:
            sent = client.send_code_request(clean_phone)
            return sent.phone_code_hash

    def _sign_in_with_code(
        self,
        clean_phone: str,
        temp_record: Mapping[str, Any],
        code: str,
        sent_hash: str,
    ) -> Account:
        with self._client(temp_record) as client:
            client.sign_in(phone=clean_phone, code=code, phone_code_hash=sent_hash)
            return self._build_account(clean_phone, client)

    def _sign_in_with_password(
        self,
        clean_phone: str,
        temp_record: Mapping[str, Any],
        password: str,
    ) -> Account:
        with self._client(temp_record) as client:
            client.sign_in(password=password)
            return self._build_account(clean_phone, client)

    @staticmethod
    def _build_account(clean_phone: str, client: TelegramClient) -> Account:
        me = client.get_me()
        if me is None:
            raise ValueError("Не удалось получить профиль Telegram")

        account_id = f"tg-{me.id}"
        display = utils.get_display_name(me).strip() or clean_phone
        return Account(
            id=account_id,
            name=f"{display} · {clean_phone}",
            phone=clean_phone,
            status=AccountStatus.ONLINE,
        )

    @staticmethod
    def _in_worker(work: Callable[[], _T]) -> _T:
        def _execute() -> _T:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return work()
            finally:
                asyncio.set_event_loop(None)
                loop.close()

        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(_execute).result()

    def remove_account(self, account_id: str) -> bool:
        """Remove account from JSON storage and delete local Telegram session files."""
        document = self._document()
        accounts = document.get("accounts", [])
        if not isinstance(accounts, list):
            return False

        kept = [item for item in accounts if str(item.get("id", "")) != account_id]
        if len(kept) == len(accounts):
            return False

        document["accounts"] = kept
        self._write_document(document)
        self._delete_session(account_id)
        return True

    def _document(self) -> dict[str, Any]:
        if not self._accounts_path.exists():
            return {"accounts": []}
        return JsonFileRepository._read(self._accounts_path)

    def _write_document(self, document: dict[str, Any]) -> None:
        self._accounts_path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _find_record(self, account_id: str) -> Mapping[str, Any] | None:
        accounts = self._document().get("accounts", [])
        if not isinstance(accounts, list):
            return None
        for record in accounts:
            if isinstance(record, Mapping) and str(record.get("id", "")) == account_id:
                return record
        return None

    def _client(self, record: Mapping[str, Any]) -> TelegramClient:
        if not self._settings.is_telegram_configured:
            self._settings = get_settings()
        if not self._settings.is_telegram_configured:
            raise ValueError("TELEGRAM_API_ID / TELEGRAM_API_HASH не настроены")

        session_name = str(record.get("session", record.get("id", ""))).strip()
        if not session_name:
            raise ValueError("У аккаунта не указан session id")
        session_path = self._sessions_dir / session_name
        return TelegramClient(
            str(session_path),
            self._settings.telegram_api_id,
            self._settings.telegram_api_hash.get_secret_value(),
        )

    @staticmethod
    def _dialog_kind(entity: object) -> Any:
        if isinstance(entity, User):
            return DialogKind.CONTACT
        if isinstance(entity, Channel):
            return DialogKind.CHANNEL if entity.broadcast else DialogKind.GROUP
        if isinstance(entity, Chat):
            return DialogKind.GROUP
        return DialogKind.CONTACT

    @staticmethod
    def _split_dialog_id(dialog_id: str) -> tuple[str | None, int]:
        account_id, separator, raw_peer = dialog_id.partition(":")
        if not separator:
            return None, 0
        try:
            return account_id, int(raw_peer)
        except ValueError:
            return None, 0

    @staticmethod
    def _author_name(item: Any) -> str:
        sender = getattr(item, "sender", None)
        if sender is not None:
            name = utils.get_display_name(sender).strip()
            if name:
                return name
        return "Собеседник"

    def _rename_session(self, old_name: str, new_name: str) -> None:
        old_base = self._sessions_dir / old_name
        new_base = self._sessions_dir / new_name
        for suffix in (".session", ".session-journal"):
            src = old_base.with_suffix(suffix)
            if src.exists():
                src.replace(new_base.with_suffix(suffix))

    def _delete_session(self, session_name: str) -> None:
        base = self._sessions_dir / session_name
        for suffix in (".session", ".session-journal"):
            path = base.with_suffix(suffix)
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                _LOGGER.exception("Could not delete session file %s", path)

    def _upsert_account(self, account: Account) -> None:
        document = self._document()
        records = document.get("accounts", [])
        if not isinstance(records, list):
            records = []

        raw = {
            "id": account.id,
            "session": account.id,
            "name": account.name,
            "phone": account.phone,
            "status": account.status.value,
        }
        updated = False
        for index, item in enumerate(records):
            if isinstance(item, Mapping) and str(item.get("id", "")) == account.id:
                records[index] = raw
                updated = True
                break
        if not updated:
            records.append(raw)

        document["accounts"] = records
        self._write_document(document)


def create_repository(*, settings: Settings | None = None) -> DataRepository:
    """Create the repository chosen by configuration.

    Supported modes:
    - ``test``: JSON fixtures from ``data``.
    - ``live``: placeholder empty repository until live integration lands.
    """
    resolved = settings or get_settings()
    if resolved.use_live_data:
        _LOGGER.info("Using live data mode (Telegram repository)")
        return LiveRepository(settings=resolved)

    _LOGGER.info("Using test data mode (JSON fixtures from %s)", resolved.data_path)
    return JsonFileRepository(settings=resolved)
