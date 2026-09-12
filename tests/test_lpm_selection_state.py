"""Selection state has one byte representation, and one initial value.

SPECIFICATION/contracts.md fixes `selection-state.json` at exactly three members, fixes
each entry's members, and requires both arrays to appear in their declared LEXICAL ORDER,
with an ABSENT file meaning the initial object. Order is not cosmetic here: this file is
the durable input to both selection strategies, and one byte representation per logical
state is what lets a delayed post-commit recovery recognize the state it is looking at.

The no-reset rule matters more here than anywhere else in this layer: resetting an
unreadable selection state would silently re-open every account this manager has already
committed to a run, while looking like a successful recovery.
"""

from __future__ import annotations

import importlib
import os
import pathlib

__all__: list[str] = []

_FIRST = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_SECOND = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


def _modules():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_selection_state.py"
    assert module_path.is_file(), "overseer/_lpm_selection_state.py must exist"
    return (importlib.import_module("_lpm_selection_state"),)


def _uid() -> int:
    return os.geteuid()


def _state_object(**changes: object) -> dict[str, object]:
    source: dict[str, object] = {
        "version": 1,
        "incumbents": [
            {
                "provider": "anthropic",
                "kind": "claude-code-oauth",
                "purpose": "factory",
                "record_id": _FIRST,
                "target_committed_at": "2026-09-12T10:00:00Z",
            }
        ],
        "last_assignments": [{"record_id": _FIRST, "assigned_at": "2026-09-12T10:00:00Z"}],
    }
    source.update(changes)
    return source


def _state_refusal(**changes: object) -> str:
    (selection,) = _modules()
    return selection.selection_state_from_object(parsed=_state_object(**changes)).failure().message


def test_an_absent_selection_state_file_means_the_initial_object(tmp_path):
    (selection,) = _modules()

    state = selection.read_selection_state(
        path=tmp_path / "selection-state.json", owner_uid=_uid()
    ).unwrap()

    assert state == selection.initial_selection_state()
    assert selection.selection_state_object(state=state) == {
        "version": 1,
        "incumbents": [],
        "last_assignments": [],
    }


def test_a_populated_state_round_trips_and_is_emitted_in_its_declared_order():
    (selection,) = _modules()
    unordered = selection.SelectionState(
        incumbents=(
            selection.Incumbent(
                provider="anthropic",
                kind="claude-code-oauth",
                purpose="interactive",
                record_id=_SECOND,
                target_committed_at="2026-09-12T11:00:00Z",
            ),
            selection.Incumbent(
                provider="anthropic",
                kind="claude-code-oauth",
                purpose="factory",
                record_id=_FIRST,
                target_committed_at="2026-09-12T10:00:00Z",
            ),
        ),
        last_assignments=(
            selection.LastAssignment(record_id=_SECOND, assigned_at="2026-09-12T11:00:00Z"),
            selection.LastAssignment(record_id=_FIRST, assigned_at="2026-09-12T10:00:00Z"),
        ),
    )

    emitted = selection.selection_state_object(state=unordered)

    assert [entry["purpose"] for entry in emitted["incumbents"]] == ["factory", "interactive"]
    assert [entry["record_id"] for entry in emitted["last_assignments"]] == [_FIRST, _SECOND]
    assert selection.selection_state_from_object(parsed=emitted).unwrap().incumbents[0].purpose == (
        "factory"
    )


def test_every_malformed_selection_state_shape_fails_closed():
    (selection,) = _modules()
    duplicate_key = _state_object()["incumbents"][0]

    assert selection.selection_state_from_object(parsed=[]).failure().message == (
        "selection state must be a JSON object"
    )
    assert _state_refusal(extra=1) == "selection state has exactly three members"
    assert _state_refusal(version=2) == "selection state version must be the integer 1"
    assert _state_refusal(incumbents={}) == "incumbents must be an array"
    assert _state_refusal(incumbents=[1]) == "incumbents entries must be objects"
    assert _state_refusal(incumbents=[{"provider": "anthropic"}]) == (
        "incumbents entries carry exactly provider, kind, purpose, record_id, "
        "target_committed_at"
    )
    assert _state_refusal(last_assignments=[{"record_id": _FIRST, "assigned_at": ""}]) == (
        "last_assignments assigned_at must be a non-empty string"
    )
    assert _state_refusal(last_assignments=[{"record_id": "nope", "assigned_at": "x"}]) == (
        "last_assignments record_id must be a lowercase UUIDv4"
    )
    assert _state_refusal(incumbents=[{**duplicate_key, "target_committed_at": "later"}]) == (
        "incumbent target_committed_at is not a UTC RFC 3339-second timestamp"
    )
    assert (
        _state_refusal(last_assignments=[{"record_id": _FIRST, "assigned_at": "later"}])
        == "assigned_at is not a UTC RFC 3339-second timestamp"
    )


def test_duplicate_or_out_of_order_entries_are_refused_rather_than_normalized():
    (selection,) = _modules()
    incumbent = _state_object()["incumbents"][0]
    later = {**incumbent, "purpose": "interactive"}
    assignment = {"record_id": _FIRST, "assigned_at": "2026-09-12T10:00:00Z"}

    assert _state_refusal(incumbents=[incumbent, incumbent]) == (
        "incumbents must be unique by provider, kind and purpose"
    )
    assert _state_refusal(incumbents=[later, incumbent]) == (
        "incumbents must appear in lexical key order"
    )
    assert _state_refusal(last_assignments=[assignment, assignment]) == (
        "last_assignments must be unique by record_id"
    )
    assert (
        _state_refusal(last_assignments=[{**assignment, "record_id": _SECOND}, assignment])
        == "last_assignments must appear in lexical record_id order"
    )
    assert (
        selection.read_selection_state(path=pathlib.Path(__file__), owner_uid=_uid() + 1)
        .failure()
        .error_type
        == "store-unavailable"
    )


def test_a_stored_selection_state_file_is_read_through_the_same_validation(tmp_path):
    (selection,) = _modules()
    path = tmp_path / "selection-state.json"
    path.write_text(
        '{"incumbents":[],"last_assignments":'
        '[{"assigned_at":"2026-09-12T10:00:00Z","record_id":"' + _FIRST + '"}],"version":1}',
        encoding="utf-8",
    )
    path.chmod(0o600)
    broken = tmp_path / "broken.json"
    broken.write_text('{"version":1}', encoding="utf-8")
    broken.chmod(0o600)

    stored = selection.read_selection_state(path=path, owner_uid=_uid()).unwrap()

    assert stored.last_assignments[0].record_id == _FIRST
    assert selection.read_selection_state(path=broken, owner_uid=_uid()).failure().message == (
        "selection state has exactly three members"
    )
