"""Messages column -- the rightmost section of the main window (about 50% wide).

Renders the selected dialog as a read-only transcript. Outgoing messages are
right-aligned and coloured so the direction is readable at a glance.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from pathlib import Path
from tkinter import ttk

from app.models import Dialog, Message
from Front import theme

TITLE = "Сообщения"

_PLACEHOLDER_TEXT = "Выберите диалог, чтобы прочитать переписку"
_EMPTY_DIALOG_TEXT = "В этом диалоге пока нет сообщений"
_NO_SELECTION_TITLE = "Диалог не выбран"

_TAG_META = "meta"
_TAG_META_OUTGOING = "meta-outgoing"
_TAG_INCOMING = "incoming"
_TAG_OUTGOING = "outgoing"
_TAG_PLACEHOLDER = "placeholder"
_SPINNER_FRAMES = ("◜", "◠", "◝", "◞", "◡", "◟")


def _plural_messages(count: int) -> str:
    """Return ``count`` with the correctly declined Russian noun."""
    if count % 100 in range(11, 20):
        noun = "сообщений"
    elif count % 10 == 1:
        noun = "сообщение"
    elif count % 10 in (2, 3, 4):
        noun = "сообщения"
    else:
        noun = "сообщений"
    return f"{count} {noun}"


class MessagesPanel(ttk.Labelframe):
    """Shows the header and the message history of one dialog.

    The panel is a pure sink: it is told what to display and never asks the
    repository or the other panels for anything.
    """

    def __init__(self, master: tk.Misc) -> None:
        """Build the header and the read-only text area."""
        super().__init__(master, text=TITLE, padding=theme.PANEL_PADDING)
        self._on_refresh_chat: Callable[[], None] | None = None
        self._on_preload_media: Callable[[], None] | None = None
        self._image_refs: list[tk.PhotoImage] = []
        self._spinner_job: str | None = None
        self._spinner_index = 0
        self._loading = False

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._title = ttk.Label(self, text=_NO_SELECTION_TITLE, font=theme.FONT_TITLE)
        self._title.grid(row=0, column=0, columnspan=2, sticky="w")

        actions = ttk.Frame(self)
        actions.grid(row=0, column=2, sticky="e")
        self._spinner = ttk.Label(actions, text="", width=2, foreground=theme.COLOR_MUTED)
        self._spinner.grid(row=0, column=0, padx=(0, theme.GAP))
        self._refresh_button = ttk.Button(actions, text="Обновить чат", command=self._request_refresh)
        self._refresh_button.grid(row=0, column=1, padx=(0, theme.GAP))
        self._preload_button = ttk.Button(
            actions,
            text="Загрузить медиа",
            command=self._request_preload,
        )
        self._preload_button.grid(row=0, column=2)

        self._subtitle = ttk.Label(
            self, text="", font=theme.FONT_META, foreground=theme.COLOR_MUTED
        )
        self._subtitle.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, theme.GAP))

        self._text = tk.Text(
            self,
            wrap="word",
            font=theme.FONT_BASE,
            borderwidth=1,
            relief="solid",
            padx=8,
            pady=8,
            state="disabled",
            cursor="arrow",
        )
        self._text.grid(row=2, column=0, sticky="nsew")
        self._configure_tags()

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._text.yview)
        scrollbar.grid(row=2, column=1, sticky="ns")
        self._text.configure(yscrollcommand=scrollbar.set)

        self.show_placeholder()

    def show_placeholder(self, text: str = _PLACEHOLDER_TEXT) -> None:
        """Reset the header and show a hint instead of a transcript."""
        self._title.configure(text=_NO_SELECTION_TITLE)
        self._subtitle.configure(text="")
        self._image_refs = []
        self._replace_body(((text, _TAG_PLACEHOLDER),))

    def show_dialog(self, dialog: Dialog, messages: Sequence[Message]) -> None:
        """Display ``dialog`` in the header and ``messages`` as the transcript."""
        self._title.configure(text=dialog.title)
        self._subtitle.configure(
            text=f"{dialog.kind.label} · {_plural_messages(len(messages))}"
        )

        if not messages:
            self._replace_body(((_EMPTY_DIALOG_TEXT, _TAG_PLACEHOLDER),))
            return

        self._replace_message_body(messages)

    def configure_actions(
        self,
        *,
        on_refresh_chat: Callable[[], None] | None = None,
        on_preload_media: Callable[[], None] | None = None,
    ) -> None:
        """Set callbacks for message-panel action buttons."""
        self._on_refresh_chat = on_refresh_chat
        self._on_preload_media = on_preload_media

    def _request_refresh(self) -> None:
        if self._on_refresh_chat is not None:
            self._on_refresh_chat()

    def _request_preload(self) -> None:
        if self._on_preload_media is not None:
            self._on_preload_media()

    def set_loading(self, loading: bool) -> None:
        """Show or hide spinner and lock actions while background work runs."""
        if loading:
            if self._loading:
                return
            self._loading = True
            self._refresh_button.configure(state="disabled")
            self._preload_button.configure(state="disabled")
            self._spinner_index = 0
            self._tick_spinner()
            return

        self._loading = False
        self._refresh_button.configure(state="normal")
        self._preload_button.configure(state="normal")
        if self._spinner_job is not None:
            self.after_cancel(self._spinner_job)
            self._spinner_job = None
        self._spinner.configure(text="")

    @property
    def transcript(self) -> str:
        """Current body text, without Tk's trailing newline."""
        return self._text.get("1.0", "end-1c")

    @property
    def text(self) -> tk.Text:
        """The underlying text widget, exposed for layout tuning and the tests."""
        return self._text

    def _replace_body(self, chunks: Sequence[tuple[str, str]]) -> None:
        """Rewrite the text area with ``(text, tag)`` pairs, keeping it read-only."""
        self._image_refs = []
        self._text.configure(state="normal")
        try:
            self._text.delete("1.0", "end")
            for text, tag in chunks:
                self._text.insert("end", text, tag)
        finally:
            # Must not stay editable even if inserting raises: the transcript is
            # a view, not an input field.
            self._text.configure(state="disabled")
        self._text.see("end")

    def _media_chunks(self, message: Message, body_tag: str) -> list[tuple[str, str]]:
        media_path = (message.media_path or "").strip()
        if not media_path:
            return []

        if message.media_kind == "photo":
            image = self._load_photo(media_path)
            if image is not None:
                self._image_refs.append(image)
                self._text.insert("end", "\n", body_tag)
                self._text.image_create("end", image=image)
                self._text.insert("end", "\n", body_tag)
                return []

            return [("\n", body_tag), (f"[Фото] {media_path}\n", _TAG_PLACEHOLDER)]

        label = "Видео" if message.media_kind == "video" else "Файл"
        return [(f"[{label}] {media_path}\n", _TAG_PLACEHOLDER)]

    @staticmethod
    def _load_photo(path: str) -> tk.PhotoImage | None:
        file_path = Path(path)
        if not file_path.exists():
            return None
        try:
            return tk.PhotoImage(file=str(file_path))
        except tk.TclError:
            return None

    def _replace_message_body(self, messages: Sequence[Message]) -> None:
        self._image_refs = []
        self._text.configure(state="normal")
        try:
            self._text.delete("1.0", "end")
            for message in messages:
                outgoing = message.outgoing
                body_tag = _TAG_OUTGOING if outgoing else _TAG_INCOMING
                self._text.insert(
                    "end",
                    f"{message.author} · {message.time_label}\n",
                    _TAG_META_OUTGOING if outgoing else _TAG_META,
                )
                self._text.insert("end", f"{message.text}\n", body_tag)
                for text, tag in self._media_chunks(message, body_tag):
                    self._text.insert("end", text, tag)
                self._text.insert("end", "\n", body_tag)
        finally:
            self._text.configure(state="disabled")
        self._text.see("end")

    def _configure_tags(self) -> None:
        """Set up the fonts, colours and alignment used by the transcript."""
        self._text.tag_configure(
            _TAG_META, font=theme.FONT_META, foreground=theme.COLOR_MUTED, spacing1=6
        )
        self._text.tag_configure(
            _TAG_META_OUTGOING,
            font=theme.FONT_META,
            foreground=theme.COLOR_MUTED,
            spacing1=6,
            justify="right",
        )
        self._text.tag_configure(_TAG_INCOMING, font=theme.FONT_BASE)
        self._text.tag_configure(
            _TAG_OUTGOING,
            font=theme.FONT_BASE,
            foreground=theme.COLOR_OUTGOING,
            justify="right",
        )
        self._text.tag_configure(
            _TAG_PLACEHOLDER,
            font=theme.FONT_BASE,
            foreground=theme.COLOR_MUTED,
            justify="center",
            spacing1=24,
        )

    def _tick_spinner(self) -> None:
        if not self._loading:
            self._spinner.configure(text="")
            self._spinner_job = None
            return

        self._spinner.configure(text=_SPINNER_FRAMES[self._spinner_index % len(_SPINNER_FRAMES)])
        self._spinner_index += 1
        self._spinner_job = self.after(120, self._tick_spinner)
