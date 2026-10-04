"""The target-commit record is validated exactly, because a phase boundary depends on it.

SPECIFICATION/contracts.md requires `assignment-commit` to "record the adapter-supplied target
commit time", and provision `start` transitions to `postcommit` only AFTER a committed target —
so the instant crosses a phase boundary, and after a crash the only place a recovered
`postcommit` can find it is this record. That makes it the authoritative postcondition of
`target-write` as well: the destination's bytes cannot say whether THIS operation's write
committed, because a byte-identical value could have been left by the previous generation.

SO A MALFORMED ONE MUST REFUSE, NOT BE GUESSED AT. Every refusal here is
`store-unavailable`, which is the rail the contract reserves for state that cannot be read or
trusted, and the record is left exactly as found — a corrupt commit record is EVIDENCE about a
credential that may already be live at a destination, and replacing it with a plausible one
would convert "I cannot tell what landed" into a confident wrong answer.

MEMBERSHIP IS EXACT IN BOTH DIRECTIONS. A missing member makes the replay impossible; an extra
one is how a diagnostic or a leaked value would reach a durable record. Both are refused by the
same comparison rather than by two rules that could drift apart.

THE ROUND TRIP IS ASSERTED SEPARATELY FROM THE DEFECTS. `target_commit_object` builds its
mapping from the declared member list, so the encode/decode pair is what proves the declared
list and the dataclass have not diverged — a defect table alone would still pass if the encoder
silently dropped a field.
"""

from __future__ import annotations

import importlib
import pathlib

import pytest

from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_TARGET_REF = "ref-commit-record"
_RUN_ID = "run-commit-record"
_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_COMMITTED_AT = "2026-10-02T11:00:05Z"


def _module(name: str):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


def _valid() -> dict[str, object]:
    return {
        "version": 1,
        "target_ref": _TARGET_REF,
        "consumer_run_id": _RUN_ID,
        "record_id": _RECORD_ID,
        "value_generation": _GENERATION,
        "committed_at": _COMMITTED_AT,
    }


def _changed(**changes: object) -> dict[str, object]:
    source = _valid()
    for member, value in changes.items():
        source[member] = value
    return source


def _without(*, member: str) -> dict[str, object]:
    source = _valid()
    del source[member]
    return source


def test_the_declared_six_members_round_trip_through_the_encoder() -> None:
    module = _module("_lpm_target_commit")

    parsed = module.target_commit_from_object(parsed=_valid())

    assert isinstance(parsed, Success), parsed
    assert module.target_commit_object(commit=parsed.unwrap()) == _valid()
    assert module.TARGET_COMMIT_MEMBERS == (
        "version",
        "target_ref",
        "consumer_run_id",
        "record_id",
        "value_generation",
        "committed_at",
    )
    assert module.TARGET_COMMIT_VERSION == 1


@pytest.mark.parametrize(
    ("parsed", "fragment"),
    [
        ("not an object", "must be a JSON object"),
        (_without(member="committed_at"), "must contain exactly"),
        (_changed(diagnostic="leaked"), "must contain exactly"),
        (_changed(version=2), "version must be the integer 1"),
        (_changed(version=True), "version must be the integer 1"),
        (_changed(target_ref=""), "target_ref must be a non-empty string"),
        (_changed(consumer_run_id=7), "consumer_run_id must be a non-empty string"),
        (_changed(record_id="not-a-uuid"), "record_id must be a lowercase RFC 4122 UUIDv4"),
        (
            _changed(value_generation=None),
            "value_generation must be a lowercase RFC 4122 UUIDv4",
        ),
        (
            _changed(committed_at="2026-10-02 11:00:05"),
            "committed_at must be a UTC RFC 3339-second timestamp",
        ),
    ],
)
def test_an_unusable_target_commit_record_is_refused(parsed: object, fragment: str) -> None:
    refused = _module("_lpm_target_commit").target_commit_from_object(parsed=parsed)

    assert isinstance(refused, Failure), parsed
    assert refused.failure().error_type == "store-unavailable"
    assert fragment in refused.failure().message
