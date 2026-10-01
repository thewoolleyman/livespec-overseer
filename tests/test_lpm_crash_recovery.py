"""Crash and retry discriminators: what an identical second attempt must and must not do.

Every local write in this package is individually crash-safe, and that says NOTHING about a crash
BETWEEN two of them. These tests are the ones that can tell a correct sequence from an incorrect
one,
because each drives a command, INTERRUPTS it at a chosen boundary, and then runs the identical
request
again — asserting on what the second attempt did rather than on what it answered.

They exist because the first cut of this composition passed every other test in the suite while
being
wrong in exactly these two places:

* `provision` wrote its assignment AFTER the target commit, so a crash in between left no durable
  record of the assignment. An identical retry then SELECTED AGAIN and wrote a second credential
  into
  a destination that already held a committed one — consuming the run identity twice, and able to
  leave two accounts leased to one run.
  `test_a_target_commit_whose_assignment_write_failed_does_not_
  select_anew` is the discriminator: it forces the post-commit write to fail, then re-runs and
  asserts
  the second attempt reaches NO selection at all.
* `report` applied the credential-status transition, then the lease release, then the marker. The
  marker is the duplicate check's evidence and is written LAST, so a crash after the transition left
  no marker and the next invocation suspected the credential a SECOND time.
  `test_a_metadata_transition_whose_marker_write_failed_reconciles_exactly_once` forces that gap and
  asserts the transition happens once across both attempts.

HOW A CRASH IS SIMULATED. By making ONE collaborator fail where a crash would have stopped the
process, through the module attribute the code under test actually reads. That is strictly more
precise than killing a subprocess: it puts the interruption at a NAMED boundary, so a failure of
these tests says which window regressed. The state left on disk afterwards is the same state a
real crash at that point would leave, which is what the second attempt is then run against.

WHAT RECONCILES, AND WHAT IS STILL OWED. These commands are idempotent by AUTHORITATIVE
POSTCONDITION rather than by a checkpoint: the contract requires each effect to inspect its own
postcondition so that "an effect commit followed by a crash before `completed_step` advancement
replay as one logical effect". That is why the hardest window below -- a crash IMMEDIATELY after
an effect commits, with no checkpoint written at all -- is covered rather than being the gap a
checkpoint-only design leaves. The ratified phased write-ahead record of contracts.md 986-990 is
still owed for ORDERING and for the effects neither command yet performs; it is not what makes
these two reconcile.
"""

from __future__ import annotations

import json
import os
import pathlib
from typing import Any

import pytest

__all__: list[str] = []

_RUN = "run-1"
_RECORD_ID = "d1f0c2a4-8b6e-4c1a-9f3d-0e7a5b2c4d69"
_OTHER_RECORD_ID = "7c1b4e92-5d3a-4b60-8f2e-1a9c6d4b8305"
_GENERATION = "9b3e7c51-0a2d-4f68-b1c4-7e5a2d9f06b8"
_NOW = "2026-09-30T20:00:00Z"
_REFERENCE = "ref-abcdef0123456789"
_SECRET = b"sk-ant-oat0-the-credential-bytes"

# Every `sleep` advances the fake clock by at least this much, so a bounded wait always terminates.
_CLOCK_TICK = 0.5


def _failure(*, message: str) -> Any:
    from _lpm_results import store_unavailable

    from overseer._vendor.returns.result import Failure

    return Failure(store_unavailable(message=message))


def _record(**overrides: object) -> Any:
    from _lpm_record import CredentialRecord

    fields: dict[str, object] = {
        "record_id": _RECORD_ID,
        "provider": "anthropic",
        "account_id": "acct-1",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": _NOW,
        "expires_at": None,
        "last_validated": _NOW,
        "value_generation": _GENERATION,
        "value_ref": f"op://LPM Values/{_RECORD_ID}.{_GENERATION}/credential",
        "previous_value_ref": None,
    }
    fields.update(overrides)
    return CredentialRecord(**fields)  # pyright: ignore[reportArgumentType]


def _records(*records: Any) -> Any:
    from overseer._vendor.returns.result import Success

    return lambda: Success(tuple(records))


def _unwritable_status(*, record: Any, next_status: str, now: str) -> Any:
    _ = (record, next_status, now)
    return _failure(message="this host cannot persist a credential status transition")


def _advancing_clock() -> tuple[Any, Any]:
    """A deterministic clock whose `sleep` ACTUALLY advances the monotonic reading.

    A frozen `monotonic` plus a no-op `sleep` makes `_lpm_locks.take_lock`'s bounded wait
    non-terminating: the loop polls until `monotonic() - started >= timeout_seconds`, and with both
    seams inert that difference stays at zero forever. The bug is in the TEST double, not in the
    production wait, so the fix belongs here -- shortening the production timeout or weakening the
    loop would hide a real contention hang rather than exercise it.
    """
    reading = [0.0]

    def _monotonic() -> float:
        return reading[0]

    def _sleep(seconds: float) -> None:
        reading[0] += max(seconds, _CLOCK_TICK)

    return _monotonic, _sleep


def _host(*, tmp_path: pathlib.Path, **overrides: object) -> Any:
    from _lpm_command_host import ManagerHost
    from _lpm_config import default_config

    from overseer._vendor.returns.result import Success

    monotonic, sleep = _advancing_clock()
    fields: dict[str, object] = {
        "state_dir": tmp_path / "state",
        "config": default_config(),
        "owner_uid": os.getuid(),
        "now": _NOW,
        "read_input": lambda: "",
        "records": _records(_record()),
        "read_value": lambda *, value_ref: Success(_SECRET),
        "write_status": _unwritable_status,
        "new_reference": lambda: _REFERENCE,
        "monotonic": monotonic,
        "sleep": sleep,
    }
    fields.update(overrides)
    return ManagerHost(**fields)  # pyright: ignore[reportArgumentType]


def _ran(*, arguments: list[str], host: Any) -> dict[str, Any]:
    from _lpm_commands import run_manager_command

    outcome = run_manager_command(arguments=arguments, host=host)
    return {"body": json.loads(outcome.stdout), "exit_status": outcome.exit_status}


def _object_host(*, tmp_path: pathlib.Path, body: object, **overrides: object) -> Any:
    return _host(tmp_path=tmp_path, read_input=lambda: json.dumps(body), **overrides)


def _provision_request(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "version": 1,
        "provider": "anthropic",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "consumer_run_id": _RUN,
        "target_ref": _REFERENCE,
    }
    body.update(overrides)
    return body


def _report(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "version": 1,
        "consumer_run_id": _RUN,
        "record_id": _RECORD_ID,
        "occurred_at": _NOW,
        "classification": "authentication",
    }
    body.update(overrides)
    return body


def _issued(*, tmp_path: pathlib.Path) -> None:
    _ = _ran(
        arguments=["target", "--target-json", "-"],
        host=_object_host(
            tmp_path=tmp_path,
            body={"version": 1, "consumer_run_id": _RUN, "adapter": "isolated-run"},
        ),
    )


def _provisioned(*, tmp_path: pathlib.Path, **overrides: object) -> dict[str, Any]:
    return _ran(
        arguments=["provision", "--request-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_provision_request(), **overrides),
    )


def _reported(*, tmp_path: pathlib.Path, body: object, **overrides: object) -> dict[str, Any]:
    return _ran(
        arguments=["report", "--report-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=body, **overrides),
    )


def _assignment(*, tmp_path: pathlib.Path) -> Any:
    from _lpm_assignment import read_assignment

    return read_assignment(
        state_dir=tmp_path / "state", consumer_run_id=_RUN, owner_uid=os.getuid()
    ).unwrap()


def _lease_exists(*, tmp_path: pathlib.Path) -> bool:
    from _lpm_paths import local_record_path

    return (
        local_record_path(
            state_dir=tmp_path / "state", family="lease", identity=["anthropic", "acct-1"]
        )
        .unwrap()
        .is_file()
    )


# --------------------------------------------------------------------------------------
# provision — the prepared record is written BEFORE the target write.
# --------------------------------------------------------------------------------------


def test_the_prepared_assignment_exists_before_the_target_is_written(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ordering, observed from inside the write itself rather than inferred from the outcome."""
    import _lpm_command_provision

    _issued(tmp_path=tmp_path)
    observed: list[Any] = []
    real = _lpm_command_provision.provision_selected

    def _watched(**kwargs: Any) -> Any:
        observed.append(_assignment(tmp_path=tmp_path))
        return real(**kwargs)

    monkeypatch.setattr(_lpm_command_provision, "provision_selected", _watched)

    ran = _provisioned(tmp_path=tmp_path)

    assert ran["exit_status"] == 0
    assert len(observed) == 1
    prepared = observed[0]
    assert prepared is not None, "the target must not be written before a durable prepared record"
    assert prepared.status == "prepared"
    assert prepared.target_committed_at is None
    assert prepared.record_id == _RECORD_ID


def test_a_target_commit_whose_assignment_write_failed_does_not_select_anew(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE discriminator for the first finding: a retry must resume, never choose again."""
    import _lpm_assignment_lifecycle
    import _lpm_provision_context

    _issued(tmp_path=tmp_path)
    real_write = _lpm_assignment_lifecycle.write_assignment
    writes: list[Any] = []

    def _fails_on_promote(**kwargs: Any) -> Any:
        writes.append(kwargs["assignment"].status)
        if kwargs["assignment"].status == "committed":
            return _failure(message="the assignment record was not replaced")
        return real_write(**kwargs)

    monkeypatch.setattr(_lpm_assignment_lifecycle, "write_assignment", _fails_on_promote)
    interrupted = _provisioned(tmp_path=tmp_path)
    monkeypatch.undo()

    assert interrupted["body"]["error_type"] == "store-unavailable"
    assert writes == ["prepared", "committed"]
    assert _assignment(tmp_path=tmp_path).status == "prepared"

    selections: list[Any] = []
    real_select = _lpm_provision_context.select_record

    def _watched_select(**kwargs: Any) -> Any:
        selections.append(kwargs)
        return real_select(**kwargs)

    monkeypatch.setattr(_lpm_provision_context, "select_record", _watched_select)

    retried = _provisioned(tmp_path=tmp_path)

    assert selections == [], "an identical retry must resume the prepared account, not re-select"
    assert retried["exit_status"] == 0
    assert retried["body"]["receipt"]["record_id"] == _RECORD_ID
    assert _assignment(tmp_path=tmp_path).status == "committed"


def test_a_resumed_provision_keeps_its_account_even_when_a_fresher_one_is_eligible(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reason re-selection is unsafe, made visible: a second account is available and unused."""
    import _lpm_assignment_lifecycle

    _issued(tmp_path=tmp_path)
    real_write = _lpm_assignment_lifecycle.write_assignment

    def _fails_on_promote(**kwargs: Any) -> Any:
        if kwargs["assignment"].status == "committed":
            return _failure(message="the assignment record was not replaced")
        return real_write(**kwargs)

    monkeypatch.setattr(_lpm_assignment_lifecycle, "write_assignment", _fails_on_promote)
    _ = _provisioned(tmp_path=tmp_path)
    monkeypatch.undo()

    retried = _provisioned(
        tmp_path=tmp_path,
        records=_records(_record(record_id=_OTHER_RECORD_ID, account_id="acct-2"), _record()),
    )

    assert retried["body"]["receipt"]["account_id"] == "acct-1"
    assert _assignment(tmp_path=tmp_path).account_id == "acct-1"


def test_a_committed_run_replays_its_own_receipt_and_writes_nothing(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import _lpm_assignment_lifecycle

    _issued(tmp_path=tmp_path)
    first = _provisioned(tmp_path=tmp_path)

    def _forbidden(**_kwargs: Any) -> Any:
        raise AssertionError("a committed replay must not write an assignment")

    monkeypatch.setattr(_lpm_assignment_lifecycle, "write_assignment", _forbidden)

    replay = _provisioned(tmp_path=tmp_path)

    assert replay["body"] == first["body"]
    assert replay["exit_status"] == 0


def test_a_different_request_for_a_consumed_run_is_refused(tmp_path: pathlib.Path) -> None:
    _issued(tmp_path=tmp_path)
    _ = _provisioned(tmp_path=tmp_path)

    ran = _ran(
        arguments=["provision", "--request-json", "-"],
        host=_object_host(tmp_path=tmp_path, body=_provision_request(purpose="interactive")),
    )

    assert ran["body"]["error_type"] == "invalid-request"
    assert "different request" in ran["body"]["message"]


def test_a_prepared_run_whose_credential_vanished_is_an_internal_bug(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A resume cannot substitute another credential for the one it prepared."""
    import _lpm_assignment_lifecycle

    _issued(tmp_path=tmp_path)
    real_write = _lpm_assignment_lifecycle.write_assignment

    def _fails_on_promote(**kwargs: Any) -> Any:
        if kwargs["assignment"].status == "committed":
            return _failure(message="the assignment record was not replaced")
        return real_write(**kwargs)

    monkeypatch.setattr(_lpm_assignment_lifecycle, "write_assignment", _fails_on_promote)
    _ = _provisioned(tmp_path=tmp_path)
    monkeypatch.undo()

    retried = _provisioned(tmp_path=tmp_path, records=_records(_record(value_generation=None)))

    assert retried["body"]["error_type"] == "internal-bug"


def test_an_unreadable_assignment_refuses_before_selecting(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recovery reads the assignment FIRST, so an untrustworthy one stops the command there.

    A provision that could not determine whether its run was already assigned must not go on to
    select and write -- that is the same hazard as re-selecting after a crash, reached by a
    different
    route.
    """
    import _lpm_command_provision
    import _lpm_provision_context

    _issued(tmp_path=tmp_path)
    _ = _provisioned(tmp_path=tmp_path)
    monkeypatch.setattr(
        _lpm_command_provision,
        "read_assignment",
        lambda **_kwargs: _failure(message="the assignment record is unreadable"),
    )

    def _forbidden(**_kwargs: Any) -> Any:
        raise AssertionError("an unreadable assignment must not reach selection")

    monkeypatch.setattr(_lpm_provision_context, "select_record", _forbidden)

    ran = _provisioned(tmp_path=tmp_path)

    assert ran["body"]["error_type"] == "store-unavailable"
    assert ran["exit_status"] == 4


def test_a_contended_run_lock_refuses_without_mutating(tmp_path: pathlib.Path) -> None:
    """Per-run serialization: a run already held is `store-unavailable` with nothing written."""
    from _lpm_command_host import manager_lock_path, run_serialization
    from _lpm_locks import release_lock

    _issued(tmp_path=tmp_path)
    host = _host(tmp_path=tmp_path)
    held = run_serialization(host=host, consumer_run_id=_RUN)
    assert manager_lock_path(state_dir=tmp_path / "state", family="run", identity=[_RUN]).is_file()

    try:
        ran = _provisioned(tmp_path=tmp_path)
    finally:
        release_lock(held=held.unwrap())

    assert ran["body"]["error_type"] == "store-unavailable"
    assert ran["exit_status"] == 4
    assert _assignment(tmp_path=tmp_path) is None


# --------------------------------------------------------------------------------------
# report — the metadata transition happens exactly once across attempts.
# --------------------------------------------------------------------------------------


def _committed_run(*, tmp_path: pathlib.Path) -> None:
    _issued(tmp_path=tmp_path)
    ran = _provisioned(tmp_path=tmp_path)
    assert ran["exit_status"] == 0


def _stateful_store() -> tuple[list[tuple[str, str]], Any, Any]:
    """A metadata store that REMEMBERS the transitions written through it.

    A writer that records calls but hands back an unchanged record is not a store -- it is a store
    that lost the write, and testing reconciliation against one would assert something false. The
    whole point of postcondition reconciliation is that the retry READS the state the first attempt
    committed, so the double has to actually hold it.
    """
    from overseer._vendor.returns.result import Success

    moves: list[tuple[str, str]] = []
    held = [_record()]

    def _write_status(*, record: Any, next_status: str, now: str) -> Any:
        from dataclasses import replace

        _ = now
        moves.append((record.record_id, next_status))
        held[0] = replace(held[0], status=next_status)
        return Success(None)

    def _records_port() -> Any:
        return Success((held[0],))

    return moves, _write_status, _records_port


def test_a_metadata_transition_whose_marker_write_failed_reconciles_exactly_once(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE discriminator for the second finding: one transition across two attempts, not two."""
    import _lpm_command_report

    _committed_run(tmp_path=tmp_path)
    moves, writer, records = _stateful_store()
    monkeypatch.setattr(
        _lpm_command_report,
        "write_assignment",
        lambda **_kwargs: _failure(message="the assignment record was not replaced"),
    )

    interrupted = _reported(tmp_path=tmp_path, body=_report(), write_status=writer, records=records)
    monkeypatch.undo()

    assert interrupted["body"]["error_type"] == "store-unavailable"
    assert moves == [(_RECORD_ID, "suspect")]
    assert (
        _assignment(tmp_path=tmp_path).report_markers == ()
    ), "no marker: the report is unfinished"

    retried = _reported(tmp_path=tmp_path, body=_report(), write_status=writer, records=records)

    assert retried["body"] == {
        "version": 1,
        "status": "ok",
        "operation": "report",
        "duplicate": False,
    }
    assert moves == [(_RECORD_ID, "suspect")], "the transition must NOT be applied a second time"
    assert [marker.classification for marker in _assignment(tmp_path=tmp_path).report_markers] == [
        "authentication"
    ]


def test_a_status_transition_crashing_before_any_checkpoint_still_applies_once(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The window a checkpoint cannot cover: the process stops the INSTANT the transition commits.

    `write_status` succeeds and then nothing else runs -- no lease release, no marker, and no
    checkpoint record, because the crash lands between the effect committing and anything recording
    that it did. A design whose exactly-once depended on that record would re-apply the transition
    here. Reconciliation against the credential's own status is what makes the retry a no-op: the
    lifecycle table admits `report` only from `valid` and `revalidating`, so a credential already at
    `suspect` yields no second transition.
    """
    import _lpm_command_report

    _committed_run(tmp_path=tmp_path)
    moves, writer, records = _stateful_store()

    def _crash_right_after_the_transition(*, record: Any, next_status: str, now: str) -> Any:
        outcome = writer(record=record, next_status=next_status, now=now)
        monkeypatch.setattr(
            _lpm_command_report,
            "release_lease",
            lambda **_kwargs: _failure(message="the process stopped here"),
        )
        return outcome

    interrupted = _reported(
        tmp_path=tmp_path,
        body=_report(),
        write_status=_crash_right_after_the_transition,
        records=records,
    )
    monkeypatch.undo()

    assert interrupted["body"]["error_type"] == "store-unavailable"
    assert moves == [(_RECORD_ID, "suspect")]
    assert _assignment(tmp_path=tmp_path).report_markers == ()
    assert _lease_exists(tmp_path=tmp_path), "the release never ran"

    retried = _reported(tmp_path=tmp_path, body=_report(), write_status=writer, records=records)

    assert retried["body"]["duplicate"] is False
    assert moves == [(_RECORD_ID, "suspect")], "the committed transition must not be re-applied"
    assert not _lease_exists(tmp_path=tmp_path), "the retry still owes the lease release"
    assert [m.classification for m in _assignment(tmp_path=tmp_path).report_markers] == [
        "authentication"
    ]


def test_a_lease_release_whose_marker_write_failed_is_not_released_twice(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import _lpm_command_report

    _committed_run(tmp_path=tmp_path)
    moves, writer, records = _stateful_store()
    releases: list[Any] = []
    real_release = _lpm_command_report.release_lease

    def _watched_release(**kwargs: Any) -> Any:
        outcome = real_release(**kwargs)
        releases.append(outcome.unwrap())
        return outcome

    monkeypatch.setattr(_lpm_command_report, "release_lease", _watched_release)
    monkeypatch.setattr(
        _lpm_command_report,
        "write_assignment",
        lambda **_kwargs: _failure(message="the assignment record was not replaced"),
    )
    _ = _reported(tmp_path=tmp_path, body=_report(), write_status=writer, records=records)

    monkeypatch.setattr(_lpm_command_report, "write_assignment", real_write_assignment())
    retried = _reported(tmp_path=tmp_path, body=_report(), write_status=writer, records=records)

    assert retried["body"]["duplicate"] is False
    assert releases == ["released", "absent"], (
        "the retry must reconcile against the lease's own absence rather than release a second "
        "time -- `release_lease` is conditioned on this run AND this record, so `absent` is the "
        "committed postcondition and no later run's lease can be deleted by a replay"
    )


def real_write_assignment() -> Any:
    """The genuine writer, re-bound after a monkeypatched failure window closes."""
    from _lpm_assignment import write_assignment

    return write_assignment


def test_a_fully_applied_report_answers_duplicate_and_leaves_no_pending_operation(
    tmp_path: pathlib.Path,
) -> None:
    _committed_run(tmp_path=tmp_path)
    _moves, writer, records = _stateful_store()

    first = _reported(tmp_path=tmp_path, body=_report(), write_status=writer, records=records)
    replay = _reported(tmp_path=tmp_path, body=_report(), write_status=writer, records=records)

    assert first["body"]["duplicate"] is False
    assert replay["body"]["duplicate"] is True


def test_a_second_distinct_report_is_accepted_on_its_own_terms(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A distinct report records its OWN marker, and still cannot re-transition the credential.

    Two things are true at once here and it is worth seeing both. The second report is a different
    report -- different classification -- so it is accepted rather than answered `duplicate`,
    and its
    marker joins the array beside the first. But the credential it names is already `suspect`, and
    `admitted_move` admits `report` only from `valid` and `revalidating`, so there is no second
    transition to apply. Reconciliation is per-credential, not per-report.
    """
    import _lpm_command_report

    _committed_run(tmp_path=tmp_path)
    moves, writer, records = _stateful_store()
    monkeypatch.setattr(
        _lpm_command_report,
        "write_assignment",
        lambda **_kwargs: _failure(message="the assignment record was not replaced"),
    )
    _ = _reported(tmp_path=tmp_path, body=_report(), write_status=writer, records=records)
    monkeypatch.undo()

    other = _reported(
        tmp_path=tmp_path,
        body=_report(classification="rate-limit"),
        write_status=writer,
        records=records,
    )

    assert other["body"]["duplicate"] is False
    assert moves == [
        (_RECORD_ID, "suspect")
    ], "the credential was already suspect, so there was no second transition to apply"
    assert [marker.classification for marker in _assignment(tmp_path=tmp_path).report_markers] == [
        "rate-limit"
    ], "the interrupted first report left no marker; the second recorded its own"


def test_a_contended_run_lock_refuses_a_report_without_mutating(
    tmp_path: pathlib.Path,
) -> None:
    from _lpm_command_host import run_serialization
    from _lpm_locks import release_lock

    _committed_run(tmp_path=tmp_path)
    _moves, writer, records = _stateful_store()
    held = run_serialization(host=_host(tmp_path=tmp_path), consumer_run_id=_RUN)

    try:
        ran = _reported(tmp_path=tmp_path, body=_report(), write_status=writer, records=records)
    finally:
        release_lock(held=held.unwrap())

    assert ran["body"]["error_type"] == "store-unavailable"
    assert _assignment(tmp_path=tmp_path).report_markers == ()
