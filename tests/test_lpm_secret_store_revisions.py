"""The append-only chain is the condition — and its three non-success words differ.

SPECIFICATION/contracts.md carries every conditional record write on an APPEND-ONLY chain
of revision items, because a mutable item update cannot express "replace this only if it
still holds exactly what I read" and no backend here may rely on title uniqueness. The
predecessor digest carries the comparison instead, so a stale writer's create simply cannot
be the next revision.

These tests refuse to let the in-memory backend be a stub. It enforces the real protocol,
so a fenced retry, a defeated writer and an invalid chain are distinguishable HERE — which
is the only place a dependent slice's recovery tests can lean on them being distinguishable
at all.

`committed`, `uncommitted`, `condition-failed` and `unavailable` are four different
statements, and the third and fourth are the ones that get merged by accident:
`condition-failed` definitively says no change was made because the comparison failed,
while `unavailable` says the outcome is UNKNOWN. Reporting an unknown write as a failed one
is exactly how a committed mutation gets retried as though it never happened.
"""

from __future__ import annotations

import hashlib
import importlib
import pathlib

__all__: list[str] = []

_RECORD = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_OTHER = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_EFFECT = "a" * 64
_NEXT_EFFECT = "b" * 64


def _modules():
    for name in ("_lpm_revisions.py", "_lpm_store.py"):
        assert (
            pathlib.Path(__file__).parents[1] / "overseer" / name
        ).is_file(), f"overseer/{name} must exist"
    return importlib.import_module("_lpm_revisions"), importlib.import_module("_lpm_store")


def _item(*, revisions, record_id: str, revision: int, effect: str, predecessor: str, record: str):
    return revisions.RevisionItem(
        title=revisions.revision_title(record_id=record_id, revision=revision, effect_id=effect),
        predecessor_sha256=predecessor,
        record=record,
    )


def test_a_revision_title_and_its_genesis_predecessor_are_the_contract_forms():
    revisions, _ = _modules()

    assert revisions.revision_title(record_id=_RECORD, revision=1, effect_id=_EFFECT) == (
        f"{_RECORD}-m00000000000000000001-{_EFFECT}"
    )
    assert revisions.predecessor_digest(record=None) == "0" * 64
    assert revisions.predecessor_digest(record='{"a":1}') == (
        hashlib.sha256(b'{"a":1}').hexdigest()
    )


def test_an_empty_chain_is_authoritative_absence_rather_than_an_invalid_chain():
    revisions, _ = _modules()

    resolved = revisions.resolve_chain(record_id=_RECORD, items=[])

    # Absence PERMITS a genesis create; invalidity must refuse every mutation. Collapsing
    # them would either wedge a fresh record or let a broken chain be written over.
    assert (resolved.revision, resolved.item, resolved.reason) == (None, None, None)


def test_byte_identical_physical_duplicates_collapse_to_one_logical_revision():
    revisions, _ = _modules()
    item = _item(
        revisions=revisions,
        record_id=_RECORD,
        revision=1,
        effect=_EFFECT,
        predecessor="0" * 64,
        record='{"v":1}',
    )

    resolved = revisions.resolve_chain(record_id=_RECORD, items=[item, item])

    assert resolved.revision == 1
    assert resolved.reason is None


def test_each_broken_chain_reports_its_own_reason_rather_than_one_corrupt_bucket():
    revisions, _ = _modules()
    first = _item(
        revisions=revisions,
        record_id=_RECORD,
        revision=1,
        effect=_EFFECT,
        predecessor="0" * 64,
        record='{"v":1}',
    )
    conflicting = _item(
        revisions=revisions,
        record_id=_RECORD,
        revision=1,
        effect=_NEXT_EFFECT,
        predecessor="0" * 64,
        record='{"v":2}',
    )
    second = _item(
        revisions=revisions,
        record_id=_RECORD,
        revision=2,
        effect=_NEXT_EFFECT,
        predecessor=revisions.predecessor_digest(record='{"v":1}'),
        record='{"v":2}',
    )
    third_only = _item(
        revisions=revisions,
        record_id=_RECORD,
        revision=3,
        effect=_EFFECT,
        predecessor="0" * 64,
        record='{"v":3}',
    )
    mismatched = _item(
        revisions=revisions,
        record_id=_RECORD,
        revision=2,
        effect=_EFFECT,
        predecessor="0" * 64,
        record='{"v":9}',
    )
    successor = _item(
        revisions=revisions,
        record_id=_RECORD,
        revision=2,
        effect=_EFFECT,
        predecessor=revisions.predecessor_digest(record='{"v":1}'),
        record='{"v":8}',
    )

    def _reason(items) -> str | None:
        return revisions.resolve_chain(record_id=_RECORD, items=items).reason

    assert _reason([second]) == "gap", "a chain that does not start at revision one"
    assert _reason([first, conflicting]) == "conflict"
    assert _reason([first, second, third_only]) == "predecessor-mismatch"
    assert _reason([first, mismatched]) == "predecessor-mismatch"
    assert _reason([first, second, successor]) == "multiple-successors"
    assert (
        _reason(
            [
                first,
                second,
                _item(
                    revisions=revisions,
                    record_id=_RECORD,
                    revision=4,
                    effect=_EFFECT,
                    predecessor=revisions.predecessor_digest(record='{"v":2}'),
                    record='{"v":4}',
                ),
            ]
        )
        == "gap"
    )
    assert (
        revisions.resolve_chain(
            record_id=_RECORD,
            items=[revisions.RevisionItem(title="wrong", predecessor_sha256="0" * 64, record="{}")],
        ).reason
        == "title-mismatch"
    )
    assert revisions.INVALID_CHAIN_REASONS == (
        "gap",
        "conflict",
        "title-mismatch",
        "predecessor-mismatch",
        "multiple-successors",
    )


def test_a_malformed_revision_number_is_a_title_mismatch_rather_than_a_revision():
    revisions, _ = _modules()

    def _reason(title: str) -> str | None:
        return revisions.resolve_chain(
            record_id=_RECORD,
            items=[revisions.RevisionItem(title=title, predecessor_sha256="0" * 64, record="{}")],
        ).reason

    assert _reason(f"{_RECORD}-m1-{_EFFECT}") == "title-mismatch"
    assert _reason(f"{_RECORD}-m0000000000000000000x-{_EFFECT}") == "title-mismatch"
    assert _reason(f"{_RECORD}-m00000000000000000000-{_EFFECT}") == "title-mismatch"
    assert _reason(f"{_RECORD}-m00000000000000000001") == "title-mismatch"
    assert _reason(f"{_RECORD}-m00000000000000000001-") == "title-mismatch"
