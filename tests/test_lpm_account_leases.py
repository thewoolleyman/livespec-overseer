"""The lease record: its exact shape, its strict liveness boundary, and its policy bounds.

SPECIFICATION/contracts.md makes a lease live only while its record exists AND the current time is
STRICTLY earlier than `lease_expires_at`, and bounds `lease_seconds` to 60 through 86400 with a
default of 21600 — a value outside that range being `invalid-request` before recovery, selection
or lease acquisition rather than something clamped into range.

The strictness of the liveness boundary is the half worth pinning: at the expiry instant the
lease is GONE, so the account becomes eligible again with no cooperation from a crashed
consumer. An inclusive reading here would wedge an account for as long as its holder stayed
dead.
"""

from __future__ import annotations

import importlib
import os
import pathlib

__all__: list[str] = []

_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"


def _modules():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_leases.py"
    assert module_path.is_file(), "overseer/_lpm_leases.py must exist"
    return (importlib.import_module("_lpm_leases"),)


def _uid() -> int:
    return os.geteuid()


def _lease(leases, **changes):
    fields = {
        "provider": "anthropic",
        "account_id": "one@example.test",
        "record_id": _RECORD_ID,
        "consumer_run_id": "run-a",
        "lease_started_at": "2026-09-12T10:00:00Z",
        "lease_expires_at": "2026-09-12T16:00:00Z",
    }
    fields.update(changes)
    return leases.AccountLease(**fields)


def _refusal(leases, **changes) -> str:
    source = leases.lease_object(lease=_lease(leases))
    source.update(changes)
    return leases.lease_from_object(parsed=source).failure().message


def test_lease_seconds_defaults_to_six_hours_and_is_refused_outside_its_bounds():
    (leases,) = _modules()

    assert leases.lease_seconds_field(value=None).unwrap() == leases.DEFAULT_LEASE_SECONDS
    assert leases.DEFAULT_LEASE_SECONDS == 21600
    assert leases.lease_seconds_field(value=leases.MINIMUM_LEASE_SECONDS).unwrap() == 60
    assert leases.lease_seconds_field(value=leases.MAXIMUM_LEASE_SECONDS).unwrap() == 86400
    assert leases.lease_seconds_field(value=59).failure().error_type == "invalid-request"
    assert leases.lease_seconds_field(value=86401).failure().message == (
        "lease_seconds must be from 60 through 86400"
    )
    assert leases.lease_seconds_field(value=True).failure().message == (
        "lease_seconds must be an integer"
    )
    assert leases.lease_seconds_field(value="21600").failure().message == (
        "lease_seconds must be an integer"
    )


def test_a_new_lease_expires_its_configured_span_after_the_captured_instant():
    (leases,) = _modules()

    built = leases.new_lease(
        provider="anthropic",
        account_id="one@example.test",
        record_id=_RECORD_ID,
        consumer_run_id="run-a",
        now="2026-09-12T10:00:00Z",
        lease_seconds=leases.DEFAULT_LEASE_SECONDS,
    ).unwrap()

    assert built == _lease(leases)
    refusal = leases.new_lease(
        provider="anthropic",
        account_id="one@example.test",
        record_id=_RECORD_ID,
        consumer_run_id="run-a",
        now="right now",
        lease_seconds=60,
    )
    assert refusal.failure().error_type == "internal-bug"


def test_a_lease_round_trips_through_its_exact_seven_members():
    (leases,) = _modules()

    emitted = leases.lease_object(lease=_lease(leases))

    assert sorted(emitted) == sorted(leases.LEASE_MEMBERS)
    assert emitted["version"] == leases.LEASE_VERSION
    assert leases.lease_from_object(parsed=emitted).unwrap() == _lease(leases)


def test_every_malformed_lease_shape_fails_closed_without_being_reset():
    (leases,) = _modules()

    assert leases.lease_from_object(parsed=[]).failure().message == "lease must be a JSON object"
    assert (
        leases.lease_from_object(parsed={})
        .failure()
        .message.startswith("lease carries exactly version, provider")
    )
    assert _refusal(leases, version=2) == "lease version must be the integer 1"
    assert _refusal(leases, version=True) == "lease version must be the integer 1"
    assert _refusal(leases, provider="") == "lease provider must be a non-empty string"
    assert _refusal(leases, account_id=7) == "lease account_id must be a non-empty string"
    assert _refusal(leases, record_id="NOPE") == "lease record_id must be a lowercase UUIDv4"
    assert _refusal(leases, record_id=None) == "lease record_id must be a lowercase UUIDv4"
    assert _refusal(leases, lease_started_at="2026-09-12 10:00:00") == (
        "lease lease_started_at is not a UTC RFC 3339-second timestamp"
    )
    assert _refusal(leases, lease_expires_at=0) == (
        "lease lease_expires_at is not a UTC RFC 3339-second timestamp"
    )


def test_a_lease_is_live_strictly_before_its_expiry_and_gone_at_that_instant():
    (leases,) = _modules()
    lease = _lease(leases)

    assert leases.lease_is_live(lease=lease, now="2026-09-12T15:59:59Z") is True
    assert leases.lease_is_live(lease=lease, now="2026-09-12T16:00:00Z") is False
    assert leases.lease_is_live(lease=lease, now="2026-09-12T16:00:01Z") is False


def test_an_absent_lease_file_means_no_run_holds_that_account(tmp_path):
    (leases,) = _modules()

    assert leases.read_lease(path=tmp_path / "lease.json", owner_uid=_uid()).unwrap() is None


def test_a_stored_lease_reads_back_through_the_same_validation(tmp_path):
    (leases,) = _modules()
    path = tmp_path / "state" / "lease.json"
    stored = leases.acquire_lease(
        path=path, lease=_lease(leases), owner_uid=_uid(), now="2026-09-12T10:00:00Z"
    )

    assert stored.unwrap() == _lease(leases)
    assert path.stat().st_mode & 0o777 == 0o600
    assert leases.read_lease(path=path, owner_uid=_uid()).unwrap() == _lease(leases)


def test_an_unsafe_or_malformed_lease_file_is_store_unavailable(tmp_path):
    (leases,) = _modules()
    directory = tmp_path / "lease.json"
    directory.mkdir()
    malformed = tmp_path / "other.json"
    malformed.write_text('{"version":1}', encoding="utf-8")
    malformed.chmod(0o600)

    unsafe = leases.read_lease(path=directory, owner_uid=_uid())
    partial = leases.read_lease(path=malformed, owner_uid=_uid())

    assert unsafe.failure().message == "lease.json is not a regular file"
    assert partial.failure().message.startswith("lease carries exactly version, provider")
    assert partial.failure().error_type == "store-unavailable"
    assert malformed.read_text(encoding="utf-8") == '{"version":1}', "neither reset nor mutated"
