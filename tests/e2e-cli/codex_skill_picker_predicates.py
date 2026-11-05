"""Pure rendered-screen predicates shared by the Codex picker exercise."""

from __future__ import annotations


def mentions_list_has_new_marker(*, plain: str, before: str, markers: tuple[str, ...]) -> bool:
    """Whether a mentions-list screen changed after the filter keystrokes."""
    return plain != before and markers[0] in plain
