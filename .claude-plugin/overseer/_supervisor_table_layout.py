"""Deterministic terminal-width allocation for the overseer's live table."""

from __future__ import annotations

import os
from typing import IO

__all__: list[str] = ["fit_line", "render_lines", "terminal_columns"]

_DEFAULT_TTY_COLUMNS = 120
_FULL_HEADERS = ("Status", "Topic", "tmux", "Ctx%", "Repo")
_COMPACT_HEADERS = ("S", "T", "M", "C", "R")
_FULL_SEPARATOR = "  "
_COMPACT_SEPARATOR = " "
_FULL_MINIMUM = sum(map(len, _FULL_HEADERS)) + len(_FULL_SEPARATOR) * 4
_SPACED_COMPACT_MINIMUM = len(_COMPACT_HEADERS) + len(_COMPACT_SEPARATOR) * 4


def terminal_columns(*, out: IO[str]) -> int:
    """Read the current TTY width, with a bounded fallback for unavailable metadata."""
    try:
        columns = os.get_terminal_size(out.fileno()).columns
    except (AttributeError, OSError, TypeError, ValueError):
        columns = _DEFAULT_TTY_COLUMNS
    return max(1, columns)


def fit_line(*, text: str, columns: int | None) -> str:
    """Fit one plain-text line when ``columns`` bounds a TTY render."""
    return text if columns is None else _ellipsify(text=text, width=columns)


def render_lines(*, rows: list[tuple[str, ...]], columns: int | None) -> list[str]:
    """Render table rows within ``columns``; ``None`` preserves list-mode output."""
    if columns is not None and columns < len(_COMPACT_HEADERS):
        return _ultra_compact(rows=rows, columns=columns)

    if columns is None or columns >= _FULL_MINIMUM:
        headers = _FULL_HEADERS
        separator = _FULL_SEPARATOR
    elif columns >= _SPACED_COMPACT_MINIMUM:
        headers = _COMPACT_HEADERS
        separator = _COMPACT_SEPARATOR
    else:
        headers = _COMPACT_HEADERS
        separator = ""

    desired = [max(len(row[index]) for row in [headers, *rows]) for index in range(5)]
    widths = desired
    if columns is not None:
        available = columns - len(separator) * 4
        widths = _allocate_widths(
            desired=desired,
            minimum=[len(header) for header in headers],
            available=available,
        )
    return _format_rows(headers=headers, rows=rows, widths=widths, separator=separator)


def _allocate_widths(*, desired: list[int], minimum: list[int], available: int) -> list[int]:
    """Shrink the widest surplus first until the deterministic budget is met."""
    widths = desired.copy()
    while sum(widths) > available:
        index = max(
            range(len(widths)),
            key=lambda candidate: (widths[candidate] - minimum[candidate], -candidate),
        )
        widths[index] -= 1
    return widths


def _format_rows(
    *,
    headers: tuple[str, ...],
    rows: list[tuple[str, ...]],
    widths: list[int],
    separator: str,
) -> list[str]:
    """Format header, rule, and data with cell elision before padding."""

    def line_of(*, cells: tuple[str, ...]) -> str:
        return separator.join(
            _ellipsify(text=cell, width=widths[index]).ljust(widths[index])
            for index, cell in enumerate(cells)
        )

    return [
        line_of(cells=headers),
        separator.join("-" * width for width in widths),
        *(line_of(cells=row) for row in rows),
    ]


def _ultra_compact(*, rows: list[tuple[str, ...]], columns: int) -> list[str]:
    """Keep a bounded positional projection when even five one-cell columns cannot fit."""
    return [
        "".join(_COMPACT_HEADERS)[:columns],
        "-" * columns,
        *("".join(cell[:1] or " " for cell in row)[:columns] for row in rows),
    ]


def _ellipsify(*, text: str, width: int) -> str:
    """Fit ``text`` to a positive width and signal every truncation."""
    if len(text) <= width:
        return text
    if width == 1:
        return "…"
    return text[: width - 1] + "…"
