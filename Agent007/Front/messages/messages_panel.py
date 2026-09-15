"""Messages column -- the rightmost section of the main window (about 50% wide).

Renders the selected dialog as a read-only transcript. Outgoing messages are
right-aligned and coloured so the direction is readable at a glance.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Sequence
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

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._title = ttk.Label(self, text=_NO_SELECTION_TITLE, font=theme.FONT_TITLE)
        self._title.grid(row=0, column=0, columnspan=2, sticky="w")

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

        chunks: list[tuple[str, str]] = []
        for message in messages:
            outgoing = message.outgoing
            chunks.append(
                (
                    f"{message.author} · {message.time_label}\n",
                    _TAG_META_OUTGOING if outgoing else _TAG_META,
                )
            )
            chunks.append(
                (f"{message.text}\n\n", _TAG_OUTGOING if outgoing else _TAG_INCOMING)
            )
        self._replace_body(chunks)

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
        self._text.configure(state="normal")
        try:
            self._text.delete("1.0", "end")
            for text, tag in chunks:
                self._text.insert("end", text, tag)
        finally:
            # Must not stay editable even if inserting raises: the transcript is
            # a view, not an input field.
            self._text.configure(state="disabled")
        self._text.see("1.0")

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
