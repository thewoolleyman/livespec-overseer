"""Mapping-row resume normalization helpers."""

from __future__ import annotations

import re

from _registry_core import warn

__all__: list[str] = [
    "normalize_resume_override",
    "normalize_rows",
]

_PLAN_HANDOFF_RESUME = re.compile(
    r"(?<![\w.-])(?:[^\s`\"']*/)?plan/[^\s`\"']*/(?:supervisor-)?handoff\.md\b"
)


def _mentions_retired_plan_handoff(*, resume: str) -> bool:
    """Return True when a resume override names the retired plan-file shape."""
    return _PLAN_HANDOFF_RESUME.search(resume.replace("\\", "/")) is not None


def _plan_epic_resume(*, repo: str, epic: str) -> str:
    """Build the canonical plan-track resume prompt without importing prompt helpers."""
    return f"resume plan epic {epic} in repository {repo}; read its ledger-held plan state"


def normalize_resume_override(*, row: dict[str, object]) -> bool:
    """Rewrite or clear retired plan-file resume overrides in-place.

    The detector is syntactic: a plan-tree ``handoff.md`` or
    ``supervisor-handoff.md`` resume is retired even if that path exists, and checking
    path existence here would violate the daemon's no-plan-file invariant.
    """
    resume = row.get("resume")
    if not isinstance(resume, str) or not _mentions_retired_plan_handoff(resume=resume):
        return False
    repo = row.get("repo")
    epic = row.get("epic")
    topic = row.get("topic")
    if isinstance(repo, str) and isinstance(epic, str):
        row["resume"] = _plan_epic_resume(repo=repo, epic=epic)
        warn(
            message=(
                "rewrote retired plan-file resume override to ledger epic resume "
                f"for {repo}::{topic}"
            )
        )
        return True
    del row["resume"]
    warn(
        message=(
            "cleared retired plan-file resume override with no recorded epic "
            f"for {repo}::{topic}"
        )
    )
    return True


def normalize_rows(*, rows: list[dict[str, object]]) -> bool:
    changed = False
    for row in rows:
        if normalize_resume_override(row=row):
            changed = True
    return changed
