"""Read the plan ledger epic anchor for assignment-time mapping rows."""

from __future__ import annotations

import os
import re
from pathlib import Path

from _registry_core import warn

__all__: list[str] = ["epic_from_plan_anchor"]


_LEDGER_ANCHOR = re.compile(
    r"[Ll]edger anchor:?\*{0,2}[^\n`]*\n?[^\n`]*`([a-z0-9-]+(?:\.[0-9]+)?)`"
)


def epic_from_plan_anchor(*, repo: str | os.PathLike[str], topic: str) -> str | None:
    """Return the plan handoff's declared ledger anchor, or None when absent.

    This helper is for ASSIGNMENT surfaces. The daemon discovery pass must keep using
    directory-only discovery and must not call it.
    """
    path = Path(repo) / "plan" / topic / "handoff.md"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        warn(message=f"could not read plan ledger anchor {path}: {exc}")
        return None
    match = _LEDGER_ANCHOR.search(text)
    return match.group(1) if match is not None else None
