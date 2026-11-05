"""Pure rendered-screen predicates shared by the Codex picker exercise."""

from __future__ import annotations


def mentions_list_has_new_marker(*, plain: str, before: str, markers: tuple[str, ...]) -> bool:
    """Whether a rendered mentions marker did not appear before the keystrokes."""
    return any(marker in plain and marker not in before for marker in markers)
