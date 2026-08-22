"""Report wait-premise records the store could not use, and why.

SPECIFICATION contracts.md "The wait-premise record" makes reads FAIL-SOFT and
INDIVIDUALLY SCOPED: an unreadable, malformed, or unknown-or-newer record MUST
be skipped AND SURFACED rather than returned as valid or allowed to fail the
read of its siblings. ``wait_premises`` implements the skipping; this module
implements the surfacing, so a recorded wait that nobody can test is visible
rather than indistinguishable from no wait at all.

Kept beside ``wait_premises`` rather than inside it so the writing side stays
within this repo's per-file LLOC ceiling. The dependency runs ONE way.
"""

from __future__ import annotations

import os
from pathlib import Path

import jsonio
import wait_premises

__all__: list[str] = [
    "read_wait_premise_skips",
    "schema_version_reason",
    "skip_reason",
]


def read_wait_premise_skips(*, repo: str | os.PathLike[str], topic: str) -> list[dict[str, object]]:
    """Records this store refused, each with the reason it was not usable.

    Surfacing is separate from reading precisely so one unusable record cannot
    fail the read of its siblings.
    """
    directory = wait_premises.wait_premise_dir(repo=repo, topic=topic)
    try:
        paths = sorted(directory.glob("*.json"))
    except OSError:
        return []
    return [
        {"path": str(path), "reason": skip_reason(path=path)}
        for path in paths
        if wait_premises.read_wait_premise(path=path) is None
    ]


def skip_reason(*, path: Path) -> str:
    try:
        parsed_result = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    except OSError:
        return "unreadable"
    if jsonio.is_parse_failure(result=parsed_result):
        return "malformed"
    parsed = parsed_result.unwrap()
    if parsed is None:
        return "malformed"
    return schema_version_reason(value=parsed)


def schema_version_reason(*, value: dict[str, object]) -> str:
    """Name which version condition disqualified a record.

    ``invalid-fields`` is the residue: the version is the one this store writes,
    so whatever disqualified the record was some other field.
    """
    if "schema_version" not in value:
        return "schema-version-absent"
    version = value["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        return "schema-version-invalid"
    if version != wait_premises.SCHEMA_VERSION:
        return "schema-version-unknown"
    return "invalid-fields"
