"""The non-blocking lease interlock: no waiting, no half-assignment, no foreign releases.

SPECIFICATION/contracts.md requires a NON-BLOCKING per-account lease bound to `consumer_run_id`,
creation only over an absent or already-expired record, contention that RETRIES selection rather
than blocking or sharing an assignment, an idempotent release, and a deletion conditioned on the
file still naming the CLOSING run and record.

The two properties these tests exist for are the ones a plausible implementation loses. A
blocking acquire would hold a second run inside selection while the first writes a credential
to its target, and both would then believe they own the account — so contention must be an
IMMEDIATE typed retryable refusal that leaves the stored lease untouched. And a cleanup that
unlinked whatever file it found would delete the lease a LATER run took after this one's
expired, handing the same account out twice; naming both the run and the record in the
condition makes "release my lease" unable to mean "release whatever is here now".
"""

from __future__ import annotations

import importlib
import os
import pathlib

__all__: list[str] = []

_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_OTHER_RECORD = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


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


def _held(leases, tmp_path, **changes):
    path = tmp_path / "state" / "lease.json"
    taken = leases.acquire_lease(
        path=path, lease=_lease(leases, **changes), owner_uid=_uid(), now="2026-09-12T10:00:00Z"
    )
    assert taken.unwrap().consumer_run_id == _lease(leases, **changes).consumer_run_id
    return path


def test_a_second_run_meeting_a_live_lease_is_refused_immediately_and_retryably(tmp_path):
    (leases,) = _modules()
    path = _held(leases, tmp_path)

    contended = leases.acquire_lease(
        path=path,
        lease=_lease(leases, consumer_run_id="run-b", record_id=_OTHER_RECORD),
        owner_uid=_uid(),
        now="2026-09-12T11:00:00Z",
    )

    assert contended.failure().error_type == "retryable-exhaustion"
    assert contended.failure().message == (
        "the selected account is leased to another run until 2026-09-12T16:00:00Z"
    )
    assert leases.read_lease(path=path, owner_uid=_uid()).unwrap() == _lease(leases)


def test_an_expired_lease_is_treated_as_absent_so_a_crashed_consumer_frees_its_account(tmp_path):
    (leases,) = _modules()
    path = _held(leases, tmp_path)

    replacement = leases.acquire_lease(
        path=path,
        lease=_lease(
            leases,
            consumer_run_id="run-b",
            record_id=_OTHER_RECORD,
            lease_started_at="2026-09-12T16:00:00Z",
            lease_expires_at="2026-09-12T22:00:00Z",
        ),
        owner_uid=_uid(),
        now="2026-09-12T16:00:00Z",
    )

    assert replacement.unwrap().consumer_run_id == "run-b"
    assert leases.read_lease(path=path, owner_uid=_uid()).unwrap().record_id == _OTHER_RECORD


def test_an_identical_retry_reclaims_its_own_live_lease_without_moving_its_timestamps(tmp_path):
    (leases,) = _modules()
    path = _held(leases, tmp_path)

    reclaimed = leases.acquire_lease(
        path=path,
        lease=_lease(
            leases, lease_started_at="2026-09-12T12:00:00Z", lease_expires_at="2026-09-12T18:00:00Z"
        ),
        owner_uid=_uid(),
        now="2026-09-12T12:00:00Z",
    )

    assert reclaimed.unwrap() == _lease(leases)
    assert leases.read_lease(path=path, owner_uid=_uid()).unwrap().lease_expires_at == (
        "2026-09-12T16:00:00Z"
    )


def test_an_unreadable_or_unwritable_lease_path_refuses_without_taking_the_account(tmp_path):
    (leases,) = _modules()
    directory = tmp_path / "lease.json"
    directory.mkdir()
    dangling = tmp_path / "gone"
    dangling.symlink_to(tmp_path / "absent-directory")

    unreadable = leases.acquire_lease(
        path=directory, lease=_lease(leases), owner_uid=_uid(), now="2026-09-12T10:00:00Z"
    )
    unwritable = leases.acquire_lease(
        path=dangling / "lease.json",
        lease=_lease(leases),
        owner_uid=_uid(),
        now="2026-09-12T10:00:00Z",
    )

    assert unreadable.failure().message == "lease.json is not a regular file"
    assert unwritable.failure().error_type == "store-unavailable"
    assert unwritable.failure().message == "gone is a symlink"


def test_release_removes_only_this_run_and_record_and_is_idempotent(tmp_path):
    (leases,) = _modules()
    path = _held(leases, tmp_path)

    foreign_run = leases.release_lease(
        path=path, consumer_run_id="run-b", record_id=_RECORD_ID, owner_uid=_uid()
    )
    foreign_record = leases.release_lease(
        path=path, consumer_run_id="run-a", record_id=_OTHER_RECORD, owner_uid=_uid()
    )
    mine = leases.release_lease(
        path=path, consumer_run_id="run-a", record_id=_RECORD_ID, owner_uid=_uid()
    )
    again = leases.release_lease(
        path=path, consumer_run_id="run-a", record_id=_RECORD_ID, owner_uid=_uid()
    )

    assert foreign_run.unwrap() == leases.LEASE_FOREIGN
    assert foreign_record.unwrap() == leases.LEASE_FOREIGN
    assert mine.unwrap() == leases.LEASE_RELEASED
    assert again.unwrap() == leases.LEASE_ABSENT
    assert not path.exists()
    assert set(leases.LEASE_RELEASE_OUTCOMES) == {"released", "absent", "foreign"}


def test_release_reports_an_unsafe_path_and_a_failed_unlink_rather_than_claiming_success(
    tmp_path, monkeypatch
):
    (leases,) = _modules()
    path = _held(leases, tmp_path)
    directory = tmp_path / "lease.json"
    directory.mkdir()

    unsafe = leases.release_lease(
        path=directory, consumer_run_id="run-a", record_id=_RECORD_ID, owner_uid=_uid()
    )

    def _refuse(self) -> None:  # stands in for Path.unlink
        raise PermissionError(13, "simulated")

    monkeypatch.setattr(leases.Path, "unlink", _refuse)
    blocked = leases.release_lease(
        path=path, consumer_run_id="run-a", record_id=_RECORD_ID, owner_uid=_uid()
    )

    assert unsafe.failure().message == "lease.json is not a regular file"
    assert blocked.failure().error_type == "store-unavailable"
    assert blocked.failure().message == "lease.json was not released: PermissionError"


def test_a_lease_that_vanishes_between_the_read_and_the_unlink_is_simply_absent(
    tmp_path, monkeypatch
):
    (leases,) = _modules()
    path = _held(leases, tmp_path)

    def _vanished(self) -> None:  # stands in for Path.unlink
        raise FileNotFoundError(2, "simulated")

    monkeypatch.setattr(leases.Path, "unlink", _vanished)
    raced = leases.release_lease(
        path=path, consumer_run_id="run-a", record_id=_RECORD_ID, owner_uid=_uid()
    )

    assert raced.unwrap() == leases.LEASE_ABSENT
