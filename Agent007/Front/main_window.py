"""Application main window: the three-column shell.

Its only responsibilities are laying the sections out and connecting their
callbacks. The panels stay unaware of each other, so a section can be replaced
or moved without touching the others.

Column widths come from the agreed proportions -- accounts 20%, dialogs 30%,
transcript 50% -- expressed as ``grid`` weights in a single uniform group,
which keeps the ratio when the window is resized.
"""

from __future__ import annotations

import threading
import tkinter as tk
from queue import Empty, Queue
from collections.abc import Callable
from tkinter import (
    messagebox,
    ttk,
)

from app.config import get_settings, save_telegram_credentials
from app.logging_config import get_logger
from app.models import Account, Dialog
from app.repository import DataRepository, JsonFileRepository
from Front import theme
from Front.accounts.accounts_panel import AccountsPanel, AddAccountRequest
from Front.chats.dialogs_panel import DialogsPanel
from Front.messages.messages_panel import MessagesPanel

_LOGGER = get_logger(__name__)

WINDOW_TITLE = "Agent007 — управление Telegram-аккаунтами"
MIN_WIDTH = 1024
MIN_HEIGHT = 640
STATUS_PREFIX = "Telegram: "

# Accounts 20%, dialogs 30%, messages 50%.
COLUMN_WEIGHTS = (20, 30, 50)
UNIFORM_GROUP = "agent007-columns"

_COPY_KEYS = {"c", "с"}
_PASTE_KEYS = {"v", "м"}
_CUT_KEYS = {"x", "ч"}
_SELECT_ALL_KEYS = {"a", "ф"}
_KEYCODE_TO_LATIN = {
    65: "a",
    67: "c",
    86: "v",
    88: "x",
}


def _paste_from_clipboard(event: tk.Event) -> str:
    """Paste helper for Shift+Insert-compatible input fields."""
    event.widget.event_generate("<<Paste>>")
    return "break"


def _copy_to_clipboard(event: tk.Event) -> str:
    """Copy helper for context menu and explicit key bindings."""
    event.widget.event_generate("<<Copy>>")
    return "break"


def _cut_to_clipboard(event: tk.Event) -> str:
    """Cut helper for context menu and explicit key bindings."""
    event.widget.event_generate("<<Cut>>")
    return "break"


def _select_all_text(event: tk.Event) -> str:
    """Select-all helper for context menu and explicit key bindings."""
    event.widget.event_generate("<<SelectAll>>")
    return "break"


def _is_editable(widget: tk.Misc) -> bool:
    """Whether clipboard editing commands should be allowed for the widget."""
    state = "normal"
    try:
        state = str(widget.cget("state"))
    except (AttributeError, tk.TclError):
        pass
    return state not in {"disabled", "readonly"}


def _handle_clipboard_shortcut(event: tk.Event) -> str | None:
    """Handle copy/paste/cut/select-all regardless of active keyboard layout."""
    key = (event.keysym or "").lower()
    if len(key) != 1:
        key = ""

    if not key:
        key = (event.char or "").lower()

    if not key:
        key = _KEYCODE_TO_LATIN.get(getattr(event, "keycode", -1), "")

    widget = event.widget

    if key in _COPY_KEYS:
        widget.event_generate("<<Copy>>")
        return "break"

    if key in _PASTE_KEYS and _is_editable(widget):
        widget.event_generate("<<Paste>>")
        return "break"

    if key in _CUT_KEYS and _is_editable(widget):
        widget.event_generate("<<Cut>>")
        return "break"

    if key in _SELECT_ALL_KEYS:
        widget.event_generate("<<SelectAll>>")
        return "break"

    return None


def configure_editable_shortcuts(root: tk.Misc) -> None:
    """Enable layout-independent clipboard shortcuts for editable fields."""
    root.bind_class("Entry", "<Control-KeyPress>", _handle_clipboard_shortcut, add=True)
    root.bind_class("TEntry", "<Control-KeyPress>", _handle_clipboard_shortcut, add=True)
    root.bind_class("Text", "<Control-KeyPress>", _handle_clipboard_shortcut, add=True)


class MainWindow:
    """Hosts the accounts, dialogs and messages panels side by side.

    Args:
        master: Widget to build the layout in -- normally the ``tk.Tk`` root,
            but any container works, which is what makes the window testable.
        repository: Source of accounts, dialogs and messages. Defaults to the
            JSON-backed :class:`~app.repository.JsonFileRepository`.
    """

    def __init__(self, master: tk.Misc, repository: DataRepository | None = None) -> None:
        self.master = master
        self._repository = repository if repository is not None else JsonFileRepository()
        self._settings = get_settings()
        self._ui_thread_id = threading.get_ident()
        self._add_account_in_progress = False
        self._ui_calls: Queue[tuple[Callable[[], str | None], threading.Event, dict[str, str | None], dict[str, Exception | None]]] = Queue()
        self.master.after(25, self._drain_ui_calls)

        if self._settings.use_live_data:
            self._ensure_telegram_credentials()

        self.container = ttk.Frame(master, padding=theme.PANEL_PADDING)
        self.container.pack(fill="both", expand=True)
        self.container.rowconfigure(0, weight=1)
        self._status_var = tk.StringVar(value="Готово")

        self.accounts_panel = AccountsPanel(
            self.container,
            on_select=self._on_account_selected,
            on_add_account=self._on_add_account_requested,
            on_remove_account=self._on_remove_account_requested,
        )
        self.dialogs_panel = DialogsPanel(
            self.container, on_select=self._on_dialog_selected
        )
        self.messages_panel = MessagesPanel(self.container)

        self._lay_out_columns()
        self._status_bar = ttk.Label(
            self.master,
            textvariable=self._status_var,
            anchor="w",
            padding=(theme.PANEL_PADDING, 2),
            foreground=theme.COLOR_MUTED,
        )
        self._status_bar.pack(fill="x", side="bottom")
        self.load_accounts()

    @property
    def panels(self) -> tuple[AccountsPanel, DialogsPanel, MessagesPanel]:
        """The three sections, left to right."""
        return (self.accounts_panel, self.dialogs_panel, self.messages_panel)

    def load_accounts(self) -> None:
        """Fill the accounts column and preselect the first account."""
        accounts = self._repository.accounts()
        self.accounts_panel.set_accounts(accounts)
        _LOGGER.info("Loaded %d account(s) into the accounts panel", len(accounts))
        self.accounts_panel.select_first()

    def _lay_out_columns(self) -> None:
        """Place the panels in one row and give each column its share of the width."""
        for index, (panel, weight) in enumerate(zip(self.panels, COLUMN_WEIGHTS)):
            self.container.columnconfigure(
                index, weight=weight, uniform=UNIFORM_GROUP, minsize=0
            )
            # Only the gaps between panels are padded, not the outer edges.
            padx = (0 if index == 0 else theme.GAP, 0 if index == 2 else theme.GAP)
            panel.grid(row=0, column=index, sticky="nsew", padx=padx)

    def _on_account_selected(self, account: Account) -> None:
        """Show the dialogs of the chosen account and reset the transcript."""
        _LOGGER.debug("Account selected: %s", account.id)
        self.dialogs_panel.set_dialogs(self._repository.dialogs(account.id))
        self.messages_panel.show_placeholder()

    def _on_dialog_selected(self, dialog: Dialog) -> None:
        """Show the transcript of the chosen dialog."""
        _LOGGER.debug("Dialog selected: %s", dialog.id)
        self.messages_panel.show_dialog(dialog, self._repository.messages(dialog.id))

    def _on_add_account_requested(self, payload: AddAccountRequest) -> None:
        """Authenticate and add account in live mode, then refresh the list."""
        if self._add_account_in_progress:
            messagebox.showinfo("Подключение Telegram", "Подключение уже выполняется")
            return

        phone = payload.phone.strip()
        if not phone:
            messagebox.showerror("Добавить аккаунт", "Введите номер телефона")
            return

        self._add_account_in_progress = True
        self._set_status("Подготовка подключения...")

        def _worker() -> None:
            try:
                account = self._repository.add_account(
                    phone,
                    request_code=self._request_code,
                    request_password=self._request_password,
                    status_callback=self._on_telegram_status,
                )
            except RuntimeError as error:
                self._post_to_ui(lambda: self._set_status(str(error)))
                self._post_to_ui(lambda: messagebox.showinfo("Режим данных", str(error)))
            except ValueError as error:
                self._post_to_ui(lambda: self._set_status(str(error)))
                self._post_to_ui(
                    lambda: messagebox.showerror("Подключение Telegram", str(error))
                )
            except Exception:  # pragma: no cover - runtime dependency
                _LOGGER.exception("Could not add account")
                self._post_to_ui(lambda: self._set_status("Не удалось подключить аккаунт"))
                self._post_to_ui(
                    lambda: messagebox.showerror(
                        "Подключение Telegram", "Не удалось подключить аккаунт"
                    )
                )
            else:
                self._post_to_ui(lambda: self._on_account_added(account))
                self._post_to_ui(lambda: self._set_status(f"Подключён: {account.phone}"))
            finally:
                self._post_to_ui(self._set_add_account_idle)

        threading.Thread(target=_worker, daemon=True).start()

    def _set_add_account_idle(self) -> None:
        self._add_account_in_progress = False

    def _on_account_added(self, account: Account) -> None:
        self.load_accounts()
        self.accounts_panel.select(account.id)
        self.master.update_idletasks()

    def _on_remove_account_requested(self, account: Account) -> None:
        """Ask confirmation and remove account from live storage."""
        confirmed = messagebox.askyesno(
            "Удалить номер",
            f"Удалить номер {account.phone or account.name}?",
            parent=self.master,
        )
        if not confirmed:
            return

        try:
            removed = self._repository.remove_account(account.id)
        except RuntimeError as error:
            messagebox.showinfo("Режим данных", str(error))
            return
        except Exception:  # pragma: no cover - runtime dependency
            _LOGGER.exception("Could not remove account %s", account.id)
            messagebox.showerror("Удалить номер", "Не удалось удалить номер")
            return

        if removed:
            self.load_accounts()

    def _request_code(self, phone: str) -> str | None:
        """Prompt for Telegram SMS/app code in a modal dialog."""
        return self._call_on_ui_thread(lambda: self._ask_text("Код Telegram", f"Введите код для {phone}"))

    def _request_password(self, phone: str) -> str | None:
        """Prompt for Telegram 2FA password when required."""
        return self._call_on_ui_thread(
            lambda: self._ask_text("Пароль Telegram", f"Введите пароль для {phone}", masked=True)
        )

    def _on_telegram_status(self, message: str) -> None:
        def _show() -> None:
            self._set_status(message)
            _LOGGER.info("Telegram connect: %s", message)

        self._post_to_ui(_show)

    def _set_status(self, message: str) -> None:
        self._status_var.set(f"{STATUS_PREFIX}{message}")

    def _post_to_ui(self, callback: Callable[[], None]) -> None:
        try:
            self.master.after(0, callback)
        except tk.TclError:
            _LOGGER.debug("UI is already closed; skip callback")

    def _call_on_ui_thread(self, callback: Callable[[], str | None]) -> str | None:
        if threading.get_ident() == self._ui_thread_id:
            return callback()

        done = threading.Event()
        result: dict[str, str | None] = {"value": None}
        error: dict[str, Exception | None] = {"value": None}

        self._ui_calls.put((callback, done, result, error))
        done.wait()
        if error["value"] is not None:
            raise error["value"]
        return result["value"]

    def _drain_ui_calls(self) -> None:
        while True:
            try:
                callback, done, result, error = self._ui_calls.get_nowait()
            except Empty:
                break

            try:
                result["value"] = callback()
            except Exception as ex:  # pragma: no cover - defensive
                error["value"] = ex
            finally:
                done.set()

        try:
            self.master.after(25, self._drain_ui_calls)
        except tk.TclError:
            _LOGGER.debug("UI is already closed; stop UI-call pump")

    def _ensure_telegram_credentials(self) -> None:
        """Ask for Telegram API credentials once and persist them to .env."""
        if self._settings.is_telegram_configured:
            return

        while True:
            api_id_raw = self._ask_text("Telegram API", "Введите TELEGRAM_API_ID")
            if api_id_raw is None:
                return

            api_hash = self._ask_text("Telegram API", "Введите TELEGRAM_API_HASH")
            if api_hash is None:
                return

            try:
                api_id = int(api_id_raw.strip())
                save_telegram_credentials(api_id, api_hash)
            except (TypeError, ValueError):
                messagebox.showerror(
                    "Telegram API",
                    "Укажите корректные TELEGRAM_API_ID и TELEGRAM_API_HASH",
                    parent=self.master,
                )
                continue

            self._settings = get_settings()
            return

    def _ask_text(self, title: str, prompt: str, *, masked: bool = False) -> str | None:
        """Modal text input dialog with robust keyboard clipboard support."""
        dialog = tk.Toplevel(self.master)
        dialog.title(title)
        dialog.transient(self.master)
        dialog.resizable(False, False)

        container = ttk.Frame(dialog, padding=theme.PANEL_PADDING)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)

        ttk.Label(container, text=prompt).grid(row=0, column=0, sticky="w")
        value = tk.StringVar()
        entry = ttk.Entry(container, textvariable=value, width=36, show="*" if masked else "")
        entry.grid(row=1, column=0, sticky="ew", pady=(theme.GAP // 2, 0))

        menu = tk.Menu(dialog, tearoff=False)
        menu.add_command(label="Вырезать", command=lambda: entry.event_generate("<<Cut>>"))
        menu.add_command(label="Копировать", command=lambda: entry.event_generate("<<Copy>>"))
        menu.add_command(label="Вставить", command=lambda: entry.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Выделить всё", command=lambda: entry.event_generate("<<SelectAll>>"))

        result: dict[str, str | None] = {"value": None}

        def _ok() -> None:
            result["value"] = value.get()
            dialog.destroy()

        def _cancel() -> None:
            dialog.destroy()

        buttons = ttk.Frame(container)
        buttons.grid(row=2, column=0, sticky="e", pady=(theme.GAP, 0))
        ttk.Button(buttons, text="ОК", command=_ok).grid(row=0, column=0, padx=(0, theme.GAP))
        ttk.Button(buttons, text="ОТМЕНА", command=_cancel).grid(row=0, column=1)

        def _show_menu(event: tk.Event) -> str:
            menu.tk_popup(event.x_root, event.y_root)
            menu.grab_release()
            return "break"

        entry.bind("<Control-KeyPress>", _handle_clipboard_shortcut, add=True)
        entry.bind("<Control-v>", _paste_from_clipboard, add=True)
        entry.bind("<Control-V>", _paste_from_clipboard, add=True)
        entry.bind("<Control-c>", _copy_to_clipboard, add=True)
        entry.bind("<Control-C>", _copy_to_clipboard, add=True)
        entry.bind("<Control-x>", _cut_to_clipboard, add=True)
        entry.bind("<Control-X>", _cut_to_clipboard, add=True)
        entry.bind("<Control-a>", _select_all_text, add=True)
        entry.bind("<Control-A>", _select_all_text, add=True)
        entry.bind("<Shift-Insert>", _paste_from_clipboard, add=True)
        entry.bind("<Control-Insert>", _copy_to_clipboard, add=True)
        entry.bind("<Button-3>", _show_menu, add=True)
        entry.bind("<Return>", lambda _e: _ok(), add=True)
        entry.bind("<Escape>", lambda _e: _cancel(), add=True)

        dialog.protocol("WM_DELETE_WINDOW", _cancel)
        dialog.update_idletasks()
        dialog.grab_set()
        entry.focus_set()
        dialog.wait_window()
        return result["value"]


def create_root() -> tk.Tk:
    """Create the top-level window, maximised where the platform allows it."""
    root = tk.Tk()
    root.title(WINDOW_TITLE)
    root.minsize(MIN_WIDTH, MIN_HEIGHT)
    try:
        # Windows and macOS: maximise but keep the title bar and taskbar usable.
        root.state("zoomed")
    except tk.TclError:
        # Some X11 window managers reject "zoomed"; fall back to the screen size.
        root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
    configure_editable_shortcuts(root)
    return root


def run(repository: DataRepository | None = None) -> None:
    """Open the main window and block on the Tk event loop until it is closed."""
    root = create_root()
    window = MainWindow(root, repository)
    _LOGGER.info("Main window opened with %d sections", len(window.panels))
    root.mainloop()
    _LOGGER.info("Main window closed")
