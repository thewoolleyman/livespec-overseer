"""The credential record carries a reference, never a value — and its edges are exact.

SPECIFICATION/contracts.md fixes the provisionable record at exactly twelve members and
requires that a record with a missing or extra member, wrong field type or value, identity
conflict, lifecycle inconsistency or invalid generation/reference relation be INELIGIBLE
with a secret-free diagnostic WITHOUT preventing another valid record from satisfying the
request. These tests exercise one defect per invariant, because a validator that stops at
the first shape it recognizes passes a suite that only ever shows it well-formed records.

The freshness tests sit at the EQUALITY instant on purpose. The contract's own scenario
pins one record whose current time equals `last_validated` plus the configured maximum age
and another whose current time equals `expires_at`, and requires that neither be selected
at that instant. A `>` comparison would pass every other test in this file.
"""

from __future__ import annotations

import importlib
import pathlib

__all__: list[str] = []

_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
_REF = "op://llm-provider-manager-token-values/3f2504e0-4f89-41d3-9a0c-0305e82c3301-gen/credential"


def _record_module():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_record.py"
    assert module_path.is_file(), "overseer/_lpm_record.py must exist"
    return importlib.import_module("_lpm_record")


def _valid_object() -> dict[str, object]:
    return {
        "version": 1,
        "record_id": _RECORD_ID,
        "provider": "anthropic",
        "account_id": "acct-1",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": "2026-09-12T10:00:00Z",
        "expires_at": None,
        "last_validated": "2026-09-12T10:00:00Z",
        "value_generation": _GENERATION,
        "value_ref": _REF,
        "previous_value_ref": None,
    }


def _defect(**changes: object) -> str:
    source = _valid_object()
    source.update(changes)
    return _record_module().credential_record_from_object(parsed=source).failure().reason


def _accepted(**changes: object):
    source = _valid_object()
    source.update(changes)
    return _record_module().credential_record_from_object(parsed=source).unwrap()


def test_a_well_formed_record_round_trips_through_its_exact_member_mapping():
    record = _accepted()

    assert _record_module().record_object(record=record) == _valid_object()
    assert record.value_ref == _REF, "the record carries the REFERENCE, never the value"


def test_the_lifecycle_status_set_and_the_active_subset_are_the_ratified_ones():
    module = _record_module()

    assert module.CREDENTIAL_STATUSES == (
        "acquiring",
        "valid",
        "suspect",
        "revalidating",
        "dead",
        "reacquiring",
    )
    assert module.ACTIVE_STATUSES == ("acquiring", "reacquiring", "revalidating")
    assert module.IDENTITY_FIELDS == ("record_id", "provider", "account_id", "kind", "purpose")


def test_membership_is_exact_in_both_directions():
    module = _record_module()
    missing = _valid_object()
    del missing["purpose"]
    extra = _valid_object()
    extra["captured_token"] = "sk-ant-oat0-secret"

    assert module.credential_record_from_object(parsed=[]).failure().reason == (
        "credential record must be a JSON object"
    )
    assert module.credential_record_from_object(parsed=missing).failure().reason == (
        "credential record is missing purpose"
    )
    # An extra member is refused rather than ignored: silently dropping it is how a
    # captured value would ride into a stored record unnoticed.
    assert module.credential_record_from_object(parsed=extra).failure().reason == (
        "credential record has extra member captured_token"
    )
    assert _defect(version=2) == "credential record version must be the integer 1"
    assert _defect(version=True) == "credential record version must be the integer 1"


def test_every_field_type_and_value_is_checked_before_the_record_is_built():
    assert _defect(record_id="3F2504E0-4F89-41D3-9A0C-0305E82C3301") == (
        "record_id must be a lowercase RFC 4122 UUIDv4"
    )
    assert _defect(record_id=7) == "record_id must be a lowercase RFC 4122 UUIDv4"
    assert _defect(provider="") == "provider must be a non-empty string"
    assert _defect(kind=3) == "kind must be a non-empty string"
    assert _defect(status="rotating") == "status must be one ratified lifecycle status"
    assert _defect(acquired_at="2026-09-12 10:00:00") == (
        "acquired_at must be a UTC RFC 3339-second timestamp"
    )
    assert _defect(acquired_at=None) == "acquired_at must be a UTC RFC 3339-second timestamp"
    assert _defect(expires_at="soon") == (
        "expires_at must be null or a UTC RFC 3339-second timestamp"
    )
    assert _defect(value_generation="not-a-uuid") == (
        "value_generation must be null or a lowercase UUIDv4"
    )
    assert _defect(value_ref="") == "value_ref must be null or a non-empty reference"


def test_the_generation_reference_and_lifecycle_relations_are_enforced_together():
    assert _defect(value_generation=None) == (
        "value_generation and value_ref must both be null or both set"
    )
    assert _defect(status="suspect", value_generation=None, value_ref=None) == (
        "a suspect record must carry a value reference"
    )
    assert _defect(last_validated=None) == "a valid record must carry a non-null last_validated"
    assert (
        _defect(
            status="dead",
            last_validated=None,
            previous_value_ref="op://old",
            value_generation=None,
            value_ref=None,
        )
        == "previous_value_ref cannot outlive its value_ref"
    )
    # `acquiring` MAY carry neither, which is the one state where both nulls are correct.
    assert (
        _accepted(
            status="acquiring", last_validated=None, value_generation=None, value_ref=None
        ).status
        == "acquiring"
    )


def test_identity_is_immutable_across_replacement_and_lifecycle_writes():
    module = _record_module()
    before = _accepted()

    assert not module.identity_conflict(before=before, after=_accepted(status="suspect"))
    assert module.identity_conflict(before=before, after=_accepted(purpose="interactive"))


def test_expiry_and_age_staleness_both_count_their_equality_instant():
    module = _record_module()
    expiring = _accepted(expires_at="2026-09-12T11:00:00Z")

    assert module.is_expired(record=expiring, now="2026-09-12T11:00:00Z")
    assert not module.is_expired(record=expiring, now="2026-09-12T10:59:59Z")
    assert not module.is_expired(record=_accepted(), now="2030-01-01T00:00:00Z")
    stale = module.is_age_stale(
        record=_accepted(last_validated="2026-09-12T10:00:00Z"),
        now="2026-09-12T10:05:00Z",
        maximum_validation_age_seconds=300,
    )
    fresh = module.is_age_stale(
        record=_accepted(last_validated="2026-09-12T10:00:00Z"),
        now="2026-09-12T10:04:59Z",
        maximum_validation_age_seconds=300,
    )
    assert stale, "current time equal to last_validated + max age is age-stale"
    assert not fresh


def test_a_record_with_no_usable_validation_time_is_age_stale_rather_than_fresh():
    module = _record_module()
    never = module.CredentialRecord(
        record_id=_RECORD_ID,
        provider="anthropic",
        account_id="acct-1",
        kind="claude-code-oauth",
        purpose="factory",
        status="acquiring",
        acquired_at="2026-09-12T10:00:00Z",
        expires_at=None,
        last_validated=None,
        value_generation=None,
        value_ref=None,
        previous_value_ref=None,
    )
    unreadable = module.CredentialRecord(
        record_id=_RECORD_ID,
        provider="anthropic",
        account_id="acct-1",
        kind="claude-code-oauth",
        purpose="factory",
        status="valid",
        acquired_at="2026-09-12T10:00:00Z",
        expires_at=None,
        last_validated="whenever",
        value_generation=_GENERATION,
        value_ref=_REF,
        previous_value_ref=None,
    )

    assert module.is_age_stale(
        record=never, now="2026-09-12T10:00:01Z", maximum_validation_age_seconds=300
    )
    assert module.is_age_stale(
        record=unreadable, now="2026-09-12T10:00:01Z", maximum_validation_age_seconds=300
    )


def test_only_a_valid_record_that_is_neither_stale_nor_expired_is_selectable():
    module = _record_module()
    now = "2026-09-12T10:01:00Z"

    assert module.is_selectable(record=_accepted(), now=now, maximum_validation_age_seconds=300)
    assert not module.is_selectable(
        record=_accepted(status="suspect"), now=now, maximum_validation_age_seconds=300
    )
    assert not module.is_selectable(
        record=_accepted(expires_at=now), now=now, maximum_validation_age_seconds=300
    )
    assert not module.is_selectable(record=_accepted(), now=now, maximum_validation_age_seconds=60)
