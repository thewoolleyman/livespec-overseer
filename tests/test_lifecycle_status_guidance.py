"""Root agent guidance must keep bd status writes lifecycle-conformant."""

from __future__ import annotations

from pathlib import Path

import pytest

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ROOT_GUIDANCE = _REPO_ROOT / "CLAUDE.md"
_LIFESPEC_STATUSES = (
    "backlog",
    "ready",
    "blocked",
    "active",
    "acceptance",
    "pending-approval",
    "closed",
)


def _assert_lifecycle_status_guidance(*, text: str) -> None:
    assert "Lifecycle statuses for `bd update --status`" in text
    assert "Beads-native names must never be passed to `bd update --status`" in text
    for status in _LIFESPEC_STATUSES:
        assert f"`{status}`" in text
    assert "`open` maps to `backlog`" in text
    assert "`in_progress` maps to `active`" in text
    assert "bd-guard is correct to block non-lifecycle" in text
    assert "do not bypass, relax, or re-mode it" in text


def test_root_guidance_names_lifecycle_statuses_and_bans_native_status_writes() -> None:
    """Agents reading CLAUDE.md must see the lifecycle vocabulary before writing."""
    _assert_lifecycle_status_guidance(text=_ROOT_GUIDANCE.read_text(encoding="utf-8"))


def test_lifecycle_status_guidance_detector_fails_when_a_status_is_missing() -> None:
    """POSITIVE CONTROL: a clean guidance scan must not be a broken assertion."""
    text = _ROOT_GUIDANCE.read_text(encoding="utf-8").replace("`acceptance`", "`removed`")
    with pytest.raises(AssertionError):
        _assert_lifecycle_status_guidance(text=text)
