# pylint: disable=invalid-name
# The package directory name is fixed by the <Folder> entry in Agent007.pyproj
# and by the project layout agreed with the author; it is not snake_case.
"""Tkinter presentation layer.

step2.md requires one module per window or panel and one class per element, so
every section of the main window lives in its own file and is grouped by
functional block:

* :mod:`Front.accounts` -- the accounts column;
* :mod:`Front.chats`    -- the contacts/groups/channels column;
* :mod:`Front.messages` -- the transcript of the selected dialog.

:mod:`Front.main_window` only lays the sections out and connects their
callbacks; the panels never import each other.
"""
