"""The isolated-run target: one binding, one serialized write, and byte-identity on failure.

SPECIFICATION/contracts.md requires a conforming ProvisioningTarget adapter to bind each
reference immutably to one consumer-run identity, resolve it from the PERSISTED ISSUANCE
RECORD rather than by parsing it, write exactly the raw credential bytes with no added
encoding, framing or trailing newline, and leave an existing destination BYTE-IDENTICAL
whenever it returns failure. It fixes commit status at `in-progress`, `committed` or
`uncommitted`, makes `committed_at` non-null exactly for `committed` and equal to the final
lease-fence sample, and states that failure to take the per-reference lock means
`in-progress`, NEVER `uncommitted`.

The byte-identity assertions below read the destination back after each refusal rather than
merely checking the returned status, because the status is what the adapter CLAIMS and the
bytes are what the consumer will actually authenticate with. The two have to be checked
separately or the claim is unfalsifiable.

`in-progress` versus `uncommitted` is the sharpest distinction here and it is exercised with
a genuinely held lock rather than a stub: a timed-out or parent-orphaned target child may
still own that lock and still be writing, so reporting `uncommitted` would assert the
destination is unchanged at the one moment nobody can know that.
"""

from __future__ import annotations

import importlib
import os
import pathlib

__all__: list[str] = []

_NOW = "2026-09-12T10:00:00Z"
_LATER = "2026-09-13T10:00:00Z"


def _modules():
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_target.py"
    assert module_path.is_file(), "overseer/_lpm_target.py must exist"
    return (
        importlib.import_module("_lpm_target"),
        importlib.import_module("_lpm_locks"),
    )


def _uid() -> int:
    return os.geteuid()


def _lock(target, tmp_path, *, budget: float = 0.0):
    return target.TargetLock(
        path=tmp_path / "locks" / "target.lock",
        timeout_seconds=budget,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )


def _issuance(target, **changes):
    fields = {
        "reference": "tgt-0001",
        "consumer_run_id": "run-a",
        "adapter": "isolated-run",
        "destination": "/nowhere/credential",
        "issued_at": _NOW,
        "expires_at": _LATER,
    }
    fields.update(changes)
    return target.TargetIssuance(**fields)


def _refusal(target, **changes) -> str:
    source = target.issuance_object(issuance=_issuance(target))
    source.update(changes)
    return target.issuance_from_object(parsed=source).failure().message


def test_an_issued_reference_is_bound_to_one_run_and_expires_in_twenty_four_hours():
    target, _ = _modules()

    issued = target.new_issuance(
        reference="tgt-0001",
        consumer_run_id="run-a",
        adapter="isolated-run",
        destination="/run/a/credential",
        now=_NOW,
    ).unwrap()

    assert target.ISSUANCE_SECONDS == 86400
    assert issued.issued_at == _NOW
    assert issued.expires_at == _LATER
    assert issued.consumer_run_id == "run-a"


def test_issuing_refuses_an_unregistered_adapter_an_empty_reference_and_an_unusable_clock():
    target, _ = _modules()

    unregistered = target.new_issuance(
        reference="tgt-0001",
        consumer_run_id="run-a",
        adapter="host-wide",
        destination="/run/a/credential",
        now=_NOW,
    )
    assert unregistered.failure().error_type == "invalid-request"
    assert "isolated-run" in target.REGISTERED_TARGET_ADAPTERS

    for empty in ({"reference": ""}, {"consumer_run_id": ""}):
        fields = {
            "reference": "tgt-0001",
            "consumer_run_id": "run-a",
            "adapter": "isolated-run",
            "destination": "/run/a/credential",
            "now": _NOW,
        }
        fields.update(empty)
        assert target.new_issuance(**fields).failure().error_type == "invalid-request"

    unusable = target.new_issuance(
        reference="tgt-0001",
        consumer_run_id="run-a",
        adapter="isolated-run",
        destination="/run/a/credential",
        now="yesterday",
    )
    assert unusable.failure().error_type == "internal-bug"


def test_the_issuance_record_round_trips_and_rejects_every_malformed_shape():
    target, _ = _modules()

    issuance = _issuance(target)
    stored = target.issuance_object(issuance=issuance)
    assert sorted(stored) == sorted(target.ISSUANCE_MEMBERS)
    assert target.issuance_from_object(parsed=stored).unwrap() == issuance

    assert "JSON object" in target.issuance_from_object(parsed=["nope"]).failure().message
    assert "carries exactly" in _refusal(target, extra="no")
    assert "integer 1" in _refusal(target, version=2)
    assert "integer 1" in _refusal(target, version=True)
    assert "non-empty string" in _refusal(target, reference="")
    assert "non-empty string" in _refusal(target, destination=7)
    assert "RFC 3339" in _refusal(target, issued_at="yesterday")
    assert "RFC 3339" in _refusal(target, expires_at=7)


def test_resolution_is_a_lookup_and_refuses_a_foreign_run_or_a_forged_reference():
    target, _ = _modules()
    issuance = _issuance(target)

    resolved = target.resolve_issuance(
        issuance=issuance, target_ref="tgt-0001", consumer_run_id="run-a", now=_NOW, bound=False
    )
    assert resolved.unwrap() == "/nowhere/credential"

    forged = target.resolve_issuance(
        issuance=issuance,
        target_ref="/etc/shadow",
        consumer_run_id="run-a",
        now=_NOW,
        bound=False,
    )
    assert "does not name this issuance" in forged.failure().message

    foreign = target.resolve_issuance(
        issuance=issuance, target_ref="tgt-0001", consumer_run_id="run-b", now=_NOW, bound=False
    )
    assert "different consumer run" in foreign.failure().message

    retired = target.resolve_issuance(
        issuance=_issuance(target, adapter="host-wide"),
        target_ref="tgt-0001",
        consumer_run_id="run-a",
        now=_NOW,
        bound=False,
    )
    assert "registered target adapter" in retired.failure().message


def test_issuance_expiry_refuses_a_fresh_provision_but_never_a_bound_replay():
    target, _ = _modules()
    issuance = _issuance(target)
    after_expiry = "2026-09-13T10:00:01Z"

    fresh = target.resolve_issuance(
        issuance=issuance,
        target_ref="tgt-0001",
        consumer_run_id="run-a",
        now=after_expiry,
        bound=False,
    )
    assert fresh.failure().error_type == "invalid-request"
    assert "expired unassigned" in fresh.failure().message

    replay = target.resolve_issuance(
        issuance=issuance,
        target_ref="tgt-0001",
        consumer_run_id="run-a",
        now=after_expiry,
        bound=True,
    )
    assert replay.unwrap() == "/nowhere/credential"


def test_a_commit_writes_exactly_the_raw_bytes_owner_only_and_stamps_the_fence_sample(tmp_path):
    target, _ = _modules()
    destination = tmp_path / "run-a" / "credential"

    outcome = target.commit_credential(
        destination=str(destination),
        value=b"sk-ant-oat0-live",
        owner_uid=_uid(),
        fence_now=_NOW,
        lease_expires_at=_LATER,
        lock=_lock(target, tmp_path),
    )

    assert outcome.status == target.COMMITTED
    assert outcome.committed_at == _NOW
    # No added encoding, framing or trailing newline.
    assert destination.read_bytes() == b"sk-ant-oat0-live"
    assert destination.stat().st_mode & 0o777 == 0o600
    assert destination.parent.stat().st_mode & 0o777 == 0o700


def test_an_expired_lease_fence_aborts_before_the_write_and_leaves_the_target_identical(tmp_path):
    target, _ = _modules()
    destination = tmp_path / "run-a" / "credential"
    destination.parent.mkdir(mode=0o700)
    destination.write_bytes(b"prior-credential")
    destination.chmod(0o600)

    for sample in (_LATER, "2026-09-13T10:00:01Z"):
        outcome = target.commit_credential(
            destination=str(destination),
            value=b"replacement",
            owner_uid=_uid(),
            fence_now=sample,
            lease_expires_at=_LATER,
            lock=_lock(target, tmp_path),
        )
        assert outcome.status == target.UNCOMMITTED
        assert outcome.committed_at is None
        assert destination.read_bytes() == b"prior-credential"


def test_a_refused_destination_is_uncommitted_and_its_prior_bytes_survive(tmp_path):
    target, _ = _modules()
    destination = tmp_path / "run-a" / "credential"
    destination.parent.mkdir(mode=0o700)
    destination.write_bytes(b"prior-credential")
    # More broadly accessible than 0600: the writer refuses rather than rewriting through
    # the very permissions that made the existing file unsafe.
    destination.chmod(0o644)

    outcome = target.commit_credential(
        destination=str(destination),
        value=b"replacement",
        owner_uid=_uid(),
        fence_now=_NOW,
        lease_expires_at=_LATER,
        lock=_lock(target, tmp_path),
    )

    assert outcome.status == target.UNCOMMITTED
    assert outcome.committed_at is None
    assert destination.read_bytes() == b"prior-credential"


def test_a_held_per_reference_lock_is_in_progress_and_never_uncommitted(tmp_path):
    target, locks = _modules()
    destination = tmp_path / "run-a" / "credential"
    lock = _lock(target, tmp_path)
    held = locks.take_lock(
        path=lock.path,
        owner_uid=_uid(),
        timeout_seconds=0.0,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    ).unwrap()

    try:
        outcome = target.commit_credential(
            destination=str(destination),
            value=b"replacement",
            owner_uid=_uid(),
            fence_now=_NOW,
            lease_expires_at=_LATER,
            lock=lock,
        )
    finally:
        locks.release_lock(held=held)

    assert outcome.status == target.IN_PROGRESS
    assert outcome.committed_at is None
    assert not destination.exists()
    assert target.COMMIT_STATUSES == (
        target.IN_PROGRESS,
        target.COMMITTED,
        target.UNCOMMITTED,
    )


def test_the_bytes_writer_refuses_an_unsafe_parent_without_touching_anything(tmp_path):
    _ = _modules()
    localstate = importlib.import_module("_lpm_localstate")
    assert hasattr(localstate, "write_local_bytes"), "the raw-bytes writer must exist"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(mode=0o700)
    (tmp_path / "linked").symlink_to(elsewhere)

    written = localstate.write_local_bytes(
        path=tmp_path / "linked" / "credential", payload=b"value", owner_uid=_uid()
    )

    assert written.failure().error_type == "store-unavailable"
    assert not (elsewhere / "credential").exists()


def test_the_isolated_run_adapter_is_the_one_registered_name():
    target, _ = _modules()

    assert target.ISOLATED_RUN_ADAPTER == "isolated-run"
    assert target.REGISTERED_TARGET_ADAPTERS == (target.ISOLATED_RUN_ADAPTER,)
    assert target.ISSUANCE_VERSION == 1
