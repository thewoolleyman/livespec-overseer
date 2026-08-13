"""Derive the guarded finalization route for a completed feature parent."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

__all__: list[str] = ["FeatureParentFinalization", "completed_feature_parent_route"]


@dataclass(frozen=True)
class FeatureParentFinalization:
    """The finalization decision returned by the eventual guard."""

    authorized: bool
    commands: tuple[str, ...]
    audit_note: str
    non_terminal_children: tuple[str, ...]


_TERMINAL_CHILD_STATUSES = frozenset({"closed", "done", "deleted"})
_FINALIZATION_COMMANDS = (
    "bd update {parent_id} --type epic --append-notes <audit-note>",
    "bd epic close-eligible --dry-run",
    "bd epic close-eligible",
    "bd show {parent_id} --json",
)


def _text_value(*, payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def _acceptance_criteria(*, parent: Mapping[str, object]) -> str:
    direct = _text_value(payload=parent, key="acceptance_criteria")
    if direct:
        return direct
    metadata = parent.get("metadata")
    if not isinstance(metadata, Mapping):
        return ""
    return _text_value(payload=cast("Mapping[str, object]", metadata), key="acceptance_criteria")


def _audit_note(
    *, parent_id: str, acceptance_criteria: str, children: Sequence[Mapping[str, object]]
) -> str:
    child_states = ", ".join(
        f"{_text_value(payload=child, key='id') or '<unnamed>'}="
        f"{_text_value(payload=child, key='status') or '<missing>'}"
        for child in children
    )
    return (
        f"Guarded parent finalization audit for {parent_id}: direct children [{child_states}]; "
        f"acceptance criteria: {acceptance_criteria}. Type correction to epic is authorized "
        "only to enter bd epic close-eligible; the final close remains eligibility-gated."
    )


def completed_feature_parent_route(
    *,
    parent: Mapping[str, object],
    children: Sequence[Mapping[str, object]],
) -> FeatureParentFinalization:
    """Authorize only the documented type-correction then guarded close route."""
    parent_id = _text_value(payload=parent, key="id")
    parent_type = _text_value(payload=parent, key="issue_type") or _text_value(
        payload=parent, key="type"
    )
    acceptance_criteria = _acceptance_criteria(parent=parent)
    non_terminal_children = tuple(
        child_id
        for child in children
        if (child_id := _text_value(payload=child, key="id"))
        and _text_value(payload=child, key="status") not in _TERMINAL_CHILD_STATUSES
    )
    authorized = bool(
        parent_id
        and parent_type == "feature"
        and acceptance_criteria
        and children
        and not non_terminal_children
    )
    return FeatureParentFinalization(
        authorized=authorized,
        commands=tuple(command.format(parent_id=parent_id) for command in _FINALIZATION_COMMANDS)
        if authorized
        else (),
        audit_note=_audit_note(
            parent_id=parent_id or "<missing-parent-id>",
            acceptance_criteria=acceptance_criteria or "<missing>",
            children=children,
        ),
        non_terminal_children=non_terminal_children,
    )
