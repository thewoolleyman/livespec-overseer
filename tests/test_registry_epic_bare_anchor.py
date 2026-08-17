"""epic_from_plan_anchor must resolve the current bare-id epic.md shape.

Regression for overseer-7vczhl: `_LEDGER_ANCHOR` was written for the legacy
handoff.md prose convention ("**Ledger anchor:** epic `overseer-4w2m`") and never
learned the plan-thread migration tooling's epic.md shape (a markdown heading, a
blank line, then the bare id alone on its own line, no backticks). Every migrated
plan thread's epic.md was therefore silently unresolvable.
"""

from __future__ import annotations

import sys
from pathlib import Path

_OVERSEER_DIR = Path(__file__).resolve().parent.parent / "overseer"
sys.path.insert(0, str(_OVERSEER_DIR))

from _registry_epic import _anchor_from_path, epic_from_plan_anchor  # noqa: E402 — path pin above

__all__: list[str] = []

_EPIC_ID = "overseer-4w2m"


def test_epic_from_plan_anchor_resolves_the_current_bare_epic_md_shape(*, tmp_path: Path) -> None:
    """POSITIVE: the exact generator-emitted shape resolves."""
    plan = tmp_path / "plan" / "some-topic"
    plan.mkdir(parents=True)
    (plan / "epic.md").write_text(
        f"# Ledger epic anchor\n\n{_EPIC_ID}\n\n"
        "This migrated research record preserves the legacy handoff's immutable "
        "epic anchor. Read live status from the ledger, not from this file.\n",
        encoding="utf-8",
    )
    assert epic_from_plan_anchor(repo=tmp_path, topic="some-topic") == _EPIC_ID


def test_epic_from_plan_anchor_still_resolves_the_legacy_handoff_shape(*, tmp_path: Path) -> None:
    """CONTROL: the fix must not regress the pre-existing backtick-quoted shape."""
    plan = tmp_path / "plan" / "some-topic"
    plan.mkdir(parents=True)
    (plan / "handoff.md").write_text(
        f"**Ledger anchor:** epic **`{_EPIC_ID}`** (this repo's beads tenant)\n",
        encoding="utf-8",
    )
    assert epic_from_plan_anchor(repo=tmp_path, topic="some-topic") == _EPIC_ID


def test_anchor_from_path_returns_none_for_a_genuinely_anchorless_file(*, tmp_path: Path) -> None:
    """CONTROL: prose that never declares an anchor must not manufacture one.

    Exercises `_anchor_from_path` directly (the regex-matching unit under test)
    rather than the public `epic_from_plan_anchor`, which would otherwise fall
    through to `_ledger_epic_from_plan_tag`'s real `bd` subprocess call here.
    """
    path = tmp_path / "epic.md"
    path.write_text(
        "# Ledger epic anchor\n\nThis thread has not been anchored yet.\n",
        encoding="utf-8",
    )
    assert _anchor_from_path(path=path) is None
