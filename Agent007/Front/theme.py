"""Visual constants shared by the panels.

Kept in one place so the three sections stay consistent and a later restyling
touches a single file instead of every panel.
"""

from __future__ import annotations

# Padding inside a panel and between two neighbouring panels, in pixels.
PANEL_PADDING = 6
GAP = 3

FONT_BASE = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 11, "bold")
FONT_AUTHOR = ("Segoe UI", 9, "bold")
FONT_META = ("Segoe UI", 8)

COLOR_MUTED = "#6b6b6b"
COLOR_OUTGOING = "#1a5fb4"
COLOR_UNREAD = "#0b6b3a"

# Height of one row in the account and dialog lists.
ROW_HEIGHT = 22
