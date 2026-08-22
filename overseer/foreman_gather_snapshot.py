"""Status snapshot source for the foreman evidence document."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

import jsonio
import signals
from _foreman_source_result import source_value
from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _supervisor_snapshot import SCHEMA_VERSION
from foreman_gather_evidence import enrich_rows_with_evidence
from foreman_gather_sources import command_skipped, run_json_command

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "migrated_supervisor_handoff_state",
    "read_snapshot",
    "read_snapshot_fallback",
    "row_with_supervisor_handoff",
    "snapshot_payload",
    "supervisor_handoff_state",
    "validated_snapshot",
]


def validated_snapshot(*, document: dict[str, object], source_name: str) -> list[dict[str, object]]:
    schema = document.get("schema_version")
    rows = jsonio.as_list(value=document.get("rows"))
    generation = document.get("tick_generation")
    if schema != SCHEMA_VERSION or rows is None:
        msg = f"{source_name} snapshot has malformed primitive fields"
        raise ValueError(msg)
    if isinstance(generation, bool) or not isinstance(generation, int):
        msg = f"{source_name} snapshot has malformed tick_generation"
        raise TypeError(msg)
    narrowed: list[dict[str, object]] = []
    for row in rows:
        obj = jsonio.as_object(value=row)
        if obj is None:
            msg = f"{source_name} snapshot row is not an object"
            raise ValueError(msg)
        narrowed.append(obj)
    return narrowed


def snapshot_payload(
    *,
    repo: Path,
    document: dict[str, object],
    mode: str,
    path: Path | None,
    pane_captures: object = None,
) -> tuple[dict[str, object], dict[str, object]]:
    rows = validated_snapshot(document=document, source_name="status")
    repo_text = str(repo)
    used = enrich_rows_with_evidence(
        repo=repo,
        rows=[
            row_with_supervisor_handoff(repo=repo, row=row)
            for row in rows
            if row.get("repo") == repo_text
        ],
        pane_captures=pane_captures,
    )
    snapshot = {
        "daemon_instance_id": document.get("daemon_instance_id"),
        "tick_generation": document.get("tick_generation"),
        "written_at": document.get("written_at"),
        "rows": used,
    }
    source: dict[str, object] = {
        "status": "ok",
        "mode": mode,
        "rows_total": len(rows),
        "rows_used": len(used),
    }
    embedded_attention = jsonio.as_object(value=document.get("needs_attention"))
    if embedded_attention is not None:
        source["embedded_needs_attention"] = embedded_attention
    if path is not None:
        source["path"] = str(path)
        source["freshness"] = {
            "mtime": path.stat().st_mtime,
            "tick_generation": document.get("tick_generation"),
            "written_at": document.get("written_at"),
        }
    return snapshot, source


_HANDOFF_STATE_BY_MIGRATED_VERDICT: Final[Mapping[str, str]] = {
    "migrated": "present",
    "not-migrated": "missing",
    "unreadable": "unreadable",
}
"""Project the three-valued migrated verdict onto the row's handoff vocabulary.

A mapping rather than a branch chain so the projection is stated once and is
total: every verdict the predicate can return has a row value here, and a
verdict with no entry is a KeyError rather than a silent fallback onto
``missing`` -- which is the value that makes ``supervisor_pair_start`` a
warranted proposal and so is the worst possible thing to default to.
"""


def supervisor_handoff_state(*, repo: Path, topic: object) -> str:
    if not isinstance(topic, str) or topic == "":
        return "unknown"
    if signals.topic_reserved_for_supervisor(topic=topic):
        return "supervisor-topic"
    plan_dir = repo / "plan" / topic
    if not plan_dir.is_dir():
        return "not-plan"
    legacy_path = plan_dir / "supervisor-handoff.md"
    if legacy_path.is_file():
        return "present"
    return _HANDOFF_STATE_BY_MIGRATED_VERDICT[
        migrated_supervisor_handoff_state(repo=repo, topic=topic)
    ]


def migrated_supervisor_handoff_state(*, repo: Path, topic: str) -> str:
    """Report whether a topic's supervisor handoff lives in the ledger.

    Three-valued on purpose. A bare bool has no room for the difference between
    a verdict and a fault: ``False`` used to mean both "this handoff is not
    migrated" and "epic.md could not be read", and the first is the answer that
    says the handoff still needs migrating. Asserting that about a file the
    function never managed to inspect is the defect this widening removes.

    A MISSING epic.md is deliberately reported as ``not-migrated`` rather than
    as a fault: a topic that has no epic is an ordinary, legitimate state, and
    its handoff genuinely is not in the ledger. Only a file that exists and
    resists reading is ``unreadable``.
    """
    epic_path = repo / "plan" / topic / "epic.md"
    try:
        text = epic_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "not-migrated"
    except (OSError, ValueError):
        return "unreadable"
    lowered = text.lower()
    if "ledger" in lowered and ("comment" in lowered or "entry" in lowered):
        return "migrated"
    return "not-migrated"


def row_with_supervisor_handoff(*, repo: Path, row: dict[str, object]) -> dict[str, object]:
    enriched = dict(row)
    enriched["supervisor_handoff"] = supervisor_handoff_state(repo=repo, topic=row.get("topic"))
    return enriched


def read_snapshot(
    *,
    repo: Path,
    snapshot_path: Path,
    list_json_command: Sequence[str] | None,
    pane_captures: object = None,
) -> tuple[dict[str, object] | None, dict[str, object]]:
    try:
        text = snapshot_path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    if text:
        parsed_result = jsonio.parse_object(text=text)
        if jsonio.is_parse_failure(result=parsed_result):
            msg = "snapshot produced malformed JSON"
            raise ValueError(msg)
        parsed = parsed_result.unwrap()
        if parsed is None:
            msg = "snapshot produced non-object JSON"
            raise ValueError(msg)
        return snapshot_payload(
            repo=repo,
            document=parsed,
            mode="daemon-snapshot",
            path=snapshot_path,
            pane_captures=pane_captures,
        )
    return read_snapshot_fallback(
        repo=repo,
        snapshot_path=snapshot_path,
        command=list_json_command,
        pane_captures=pane_captures,
    )


def read_snapshot_fallback(
    *,
    repo: Path,
    snapshot_path: Path,
    command: Sequence[str] | None,
    pane_captures: object = None,
) -> tuple[dict[str, object] | None, dict[str, object]]:
    if command is None:
        return None, {
            "status": "skipped",
            "path": str(snapshot_path),
            "reason": "snapshot unavailable and no list --json fallback configured",
        }
    parsed = source_value(result=run_json_command(command=command, source_name="list_json"))
    if parsed is None:
        return None, command_skipped(command=command, reason="command not found")
    skip = parsed.get("__skip_reason__")
    if isinstance(skip, str):
        return None, command_skipped(command=command, reason=skip)
    return snapshot_payload(
        repo=repo,
        document=parsed,
        mode="list-json-observation-only",
        path=None,
        pane_captures=pane_captures,
    )
