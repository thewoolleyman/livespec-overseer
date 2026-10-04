"""A merge replayed from a stale checkpoint keeps a LATER concurrent contribution.

SPECIFICATION/contracts.md makes `selection-update` and `proof-update` the two provision
`postcommit` effects that mutate a SHARED record, and requires every read-modify-write of
`selection-state.json` and `coexistence-proof.json` to hold its named exclusive lock through atomic
replacement, "preventing lost updates across runs". For the proof it fixes the two run-scoped rules:
a committed `anthropic` `factory` assignment sets or RETAINS `rollout_started_at`, and a qualifying
completion whose marker is already present makes the update a COMPLETED NO-OP that must not reapply
any one-time rule.

THE LOST-UPDATE THE LOCK CANNOT PREVENT IS THE ONE THESE TESTS ARE FOR. A lock serializes writers;
it does nothing about a writer whose in-memory value is stale. The crash window this engine survives
re-enters a phase at an OLD checkpoint, so the replaying writer IS that stale writer — and if it
wrote a remembered whole-record snapshot it would silently erase every contribution that landed in
between, under a correctly-held lock. Each test therefore lands a peer contribution BETWEEN the
first attempt and the replay, then asserts the peer survives.

THE RECORDS ARE REAL FILES ON DISK, read back through their own validators rather than compared in
memory, because "the merge preserved it" and "the merge preserved it and the result is still a valid
record" are different claims and only the second one matters to the next reader.

TIMESTAMP STABILITY IS ASSERTED AS CONVERGENCE, not as "unchanged". `rollout_started_at` moves only
EARLIER, so the field settles on the earliest committed rollout whatever order the contributions
arrive in — a replay of an early commit corrects it, a replay of a later one leaves it alone, and
repeating either changes nothing. That is a stronger property than idempotence and it is what makes
the field safe to write from a retry.
"""

from __future__ import annotations

import importlib
import os
import pathlib

__all__: list[str] = []

_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_PEER_RECORD_ID = "5c2f1b8a-6d3e-4a9b-8c7d-2e1f0a9b8c7d"
_EARLY = "2026-09-30T10:00:00Z"
_LATE = "2026-09-30T14:00:00Z"


def _module(name: str):
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / f"{name}.py"
    assert module_path.is_file(), f"overseer/{name}.py must exist"
    return importlib.import_module(name)


def _merge():
    return _module("_lpm_merge_effects")


def _proof():
    return _module("_lpm_proof")


def _selection():
    return _module("_lpm_selection_state")


def _uid() -> int:
    return os.geteuid()


def _marker(*, run_id: str, record_id: str, completed_at: str):
    return _proof().CompletionMarker(
        consumer_run_id=run_id, record_id=record_id, completed_at=completed_at
    )


def _write_proof(*, path: pathlib.Path, proof) -> None:
    written = _module("_lpm_localstate").write_local_record(
        path=path, value=_proof().proof_object(proof=proof), owner_uid=_uid()
    )
    assert written.unwrap() is None


def _write_selection(*, path: pathlib.Path, state) -> None:
    written = _module("_lpm_localstate").write_local_record(
        path=path,
        value=_selection().selection_state_object(state=state),
        owner_uid=_uid(),
    )
    assert written.unwrap() is None


# ---------------------------------------------------------------------------
# The proof record's shape and its absent-file default
# ---------------------------------------------------------------------------


def test_an_absent_proof_file_means_a_rollout_that_has_not_started(tmp_path):
    module = _proof()
    path = tmp_path / "state" / "coexistence-proof.json"

    read = module.read_proof_record(path=path, owner_uid=_uid()).unwrap()

    assert module.PROOF_MEMBERS == (
        "version",
        "rollout_started_at",
        "successful_consumer_dates",
        "completion_markers",
        "soak_started_at",
        "simultaneous_spread",
        "production_success",
        "legacy_pool_absence_success",
        "last_auth_failure_at",
    )
    assert read == module.initial_proof_record()
    assert module.proof_object(proof=read) == {
        "version": 1,
        "rollout_started_at": None,
        "successful_consumer_dates": [],
        "completion_markers": [],
        "soak_started_at": None,
        "simultaneous_spread": None,
        "production_success": None,
        "legacy_pool_absence_success": None,
        "last_auth_failure_at": None,
    }


def test_an_unreadable_proof_file_is_never_read_as_a_rollout_that_has_not_started(tmp_path):
    module = _proof()
    path = tmp_path / "coexistence-proof.json"
    path.write_text("{", encoding="utf-8")
    path.chmod(0o600)
    broad = tmp_path / "broad.json"
    broad.write_text("{}", encoding="utf-8")
    broad.chmod(0o644)

    assert module.read_proof_record(path=path, owner_uid=_uid()).failure().error_type == (
        "store-unavailable"
    )
    assert (
        module.read_proof_record(path=broad, owner_uid=_uid())
        .failure()
        .message.endswith("is more broadly accessible")
    ), "answering a governance question from an unreadable record would be absence of evidence"


def test_a_proof_record_with_no_rollout_may_carry_nothing_else(tmp_path):
    module = _proof()
    stored = module.proof_object(proof=module.initial_proof_record())

    assert module.proof_from_object(
        parsed={**stored, "soak_started_at": _EARLY}
    ).failure().message == ("a proof record with no rollout must have a null soak_started_at")
    assert module.proof_from_object(
        parsed={**stored, "successful_consumer_dates": ["2026-09-30"]}
    ).failure().message == (
        "a proof record with no rollout must have empty successful_consumer_dates"
    )
    assert (
        module.proof_from_object(
            parsed={
                **stored,
                "completion_markers": [
                    {"consumer_run_id": "run-7", "record_id": _RECORD_ID, "completed_at": _EARLY}
                ],
            }
        )
        .failure()
        .message
        == "a proof record with no rollout must have empty completion_markers"
    )


def test_every_proof_shape_defect_fails_closed():
    module = _proof()
    started = module.ProofRecord(rollout_started_at=_EARLY)
    stored = module.proof_object(proof=started)
    missing = dict(stored)
    del missing["soak_started_at"]

    assert module.proof_from_object(parsed="not an object").failure().message == (
        "the proof record must be a JSON object"
    )
    assert module.proof_from_object(parsed=missing).failure().message == (
        "the proof record is missing soak_started_at"
    )
    assert module.proof_from_object(parsed={**stored, "extra": 1}).failure().message == (
        "the proof record has extra member extra"
    )
    assert module.proof_from_object(parsed={**stored, "version": 2}).failure().message == (
        "the proof record version must be the integer 1"
    )
    assert module.proof_from_object(
        parsed={**stored, "last_auth_failure_at": "whenever"}
    ).failure().message == (
        "a proof last_auth_failure_at must be null or a UTC RFC 3339-second timestamp"
    )
    assert (
        module.proof_from_object(parsed={**stored, "production_success": "run-7"}).failure().message
        == "a proof production_success must be null or a JSON object"
    )
    assert (
        module.proof_from_object(parsed={**stored, "successful_consumer_dates": {}})
        .failure()
        .message
        == "proof successful_consumer_dates must be an array"
    )
    assert (
        module.proof_from_object(parsed={**stored, "successful_consumer_dates": ["2026-9-30"]})
        .failure()
        .message
        == "each proof successful_consumer_date must be a YYYY-MM-DD string"
    )
    assert (
        module.proof_from_object(parsed={**stored, "completion_markers": {}}).failure().message
        == "proof completion_markers must be an array"
    )


def test_every_completion_marker_shape_defect_fails_closed():
    module = _proof()
    stored = module.proof_object(proof=module.ProofRecord(rollout_started_at=_EARLY))
    good = {"consumer_run_id": "run-7", "record_id": _RECORD_ID, "completed_at": _LATE}

    def _defect(entry: object) -> str:
        return (
            module.proof_from_object(parsed={**stored, "completion_markers": [entry]})
            .failure()
            .message
        )

    assert module.COMPLETION_MARKER_MEMBERS == ("consumer_run_id", "record_id", "completed_at")
    assert _defect("run-7") == "a completion marker must be a JSON object"
    assert _defect({"consumer_run_id": "run-7"}) == (
        "a completion marker must contain exactly consumer_run_id, record_id, completed_at"
    )
    assert _defect({**good, "consumer_run_id": ""}) == (
        "a completion marker consumer_run_id must be non-empty"
    )
    assert _defect({**good, "record_id": "nope"}) == (
        "a completion marker record_id must be a lowercase UUIDv4"
    )
    assert _defect({**good, "completed_at": "nope"}) == (
        "a completion marker completed_at must be canonical"
    )
    assert (
        module.proof_from_object(parsed={**stored, "completion_markers": [good, dict(good)]})
        .failure()
        .message
        == "proof completion_markers must be unique by identity"
    )


# ---------------------------------------------------------------------------
# The selection merge: a replay keeps a peer row
# ---------------------------------------------------------------------------


def test_a_selection_replay_from_a_stale_checkpoint_keeps_a_peer_row(tmp_path):
    merge, selection = _merge(), _selection()
    path = tmp_path / "state" / "selection-state.json"
    _write_selection(path=path, state=selection.initial_selection_state())

    first = merge.selection_incumbent_update(
        state=selection.read_selection_state(path=path, owner_uid=_uid()).unwrap(),
        provider="anthropic",
        kind="claude-code-oauth",
        purpose="factory",
        record_id=_RECORD_ID,
        target_committed_at=_EARLY,
    )
    _write_selection(path=path, state=first)
    stale = first

    peer = merge.selection_incumbent_update(
        state=selection.read_selection_state(path=path, owner_uid=_uid()).unwrap(),
        provider="anthropic",
        kind="claude-code-oauth",
        purpose="interactive",
        record_id=_PEER_RECORD_ID,
        target_committed_at=_LATE,
    )
    _write_selection(path=path, state=peer)

    replayed = merge.selection_incumbent_update(
        state=selection.read_selection_state(path=path, owner_uid=_uid()).unwrap(),
        provider="anthropic",
        kind="claude-code-oauth",
        purpose="factory",
        record_id=_RECORD_ID,
        target_committed_at=_EARLY,
    )
    _write_selection(path=path, state=replayed)
    final = selection.read_selection_state(path=path, owner_uid=_uid()).unwrap()

    assert len(stale.incumbents) == 1, "the stale snapshot knew of only its own row"
    assert len(final.incumbents) == 2, "the replay kept the peer row that landed in between"
    assert {incumbent.purpose for incumbent in final.incumbents} == {"factory", "interactive"}
    assert merge.is_incumbent_recorded(
        state=final,
        provider="anthropic",
        kind="claude-code-oauth",
        purpose="factory",
        record_id=_RECORD_ID,
        target_committed_at=_EARLY,
    ), "the replayed contribution's own postcondition holds, so a replay can skip it"


def test_a_replay_that_rewrites_its_own_row_changes_nothing_else(tmp_path):
    merge, selection = _merge(), _selection()
    path = tmp_path / "state" / "selection-state.json"
    _write_selection(path=path, state=selection.initial_selection_state())
    seeded = merge.last_assignment_update(
        state=merge.selection_incumbent_update(
            state=selection.initial_selection_state(),
            provider="anthropic",
            kind="claude-code-oauth",
            purpose="factory",
            record_id=_RECORD_ID,
            target_committed_at=_EARLY,
        ),
        record_id=_PEER_RECORD_ID,
        assigned_at=_LATE,
    )
    _write_selection(path=path, state=seeded)

    replayed = merge.selection_incumbent_update(
        state=selection.read_selection_state(path=path, owner_uid=_uid()).unwrap(),
        provider="anthropic",
        kind="claude-code-oauth",
        purpose="factory",
        record_id=_RECORD_ID,
        target_committed_at=_EARLY,
    )
    _write_selection(path=path, state=replayed)
    final = selection.read_selection_state(path=path, owner_uid=_uid()).unwrap()

    assert final == seeded, "re-applying the same row is byte-stable, peers included"
    assert len(final.last_assignments) == 1
    assert (
        final.last_assignments[0].assigned_at == _LATE
    ), "a spread peer's last-assignment time survives a consume-first replay"


# ---------------------------------------------------------------------------
# The proof merge: a replay keeps a peer marker, and the rollout converges
# ---------------------------------------------------------------------------


def test_a_proof_replay_from_a_stale_checkpoint_keeps_a_peer_marker(tmp_path):
    merge, proof = _merge(), _proof()
    path = tmp_path / "state" / "coexistence-proof.json"
    _write_proof(path=path, proof=proof.ProofRecord(rollout_started_at=_EARLY))
    mine = _marker(run_id="run-7", record_id=_RECORD_ID, completed_at=_EARLY)
    theirs = _marker(run_id="run-9", record_id=_PEER_RECORD_ID, completed_at=_LATE)

    first = merge.completion_marker_update(
        proof=proof.read_proof_record(path=path, owner_uid=_uid()).unwrap(), marker=mine
    )
    _write_proof(path=path, proof=first)
    stale = first
    _write_proof(
        path=path,
        proof=merge.completion_marker_update(
            proof=proof.read_proof_record(path=path, owner_uid=_uid()).unwrap(), marker=theirs
        ),
    )

    replayed = merge.completion_marker_update(
        proof=proof.read_proof_record(path=path, owner_uid=_uid()).unwrap(), marker=mine
    )
    _write_proof(path=path, proof=replayed)
    final = proof.read_proof_record(path=path, owner_uid=_uid()).unwrap()

    assert len(stale.completion_markers) == 1
    assert len(final.completion_markers) == 2, "the peer's marker survived the replay"
    assert [marker.consumer_run_id for marker in final.completion_markers] == [
        "run-7",
        "run-9",
    ], "markers are stored sorted by completed_at, then run, then record"
    assert merge.is_completion_marker_recorded(proof=final, marker=mine)


def test_re_contributing_a_marker_is_a_completed_no_op_that_reapplies_nothing(tmp_path):
    merge, proof = _merge(), _proof()
    path = tmp_path / "state" / "coexistence-proof.json"
    mine = _marker(run_id="run-7", record_id=_RECORD_ID, completed_at=_EARLY)
    seeded = merge.completion_marker_update(
        proof=proof.ProofRecord(
            rollout_started_at=_EARLY,
            production_success={"consumer_run_id": "run-7", "completed_at": _EARLY},
        ),
        marker=mine,
    )
    _write_proof(path=path, proof=seeded)

    repeated = merge.completion_marker_update(
        proof=proof.read_proof_record(path=path, owner_uid=_uid()).unwrap(), marker=mine
    )

    assert repeated == seeded, "the already-present case returns the SAME record"
    assert repeated.production_success == {
        "consumer_run_id": "run-7",
        "completed_at": _EARLY,
    }, "a repeat must not reapply a one-time rule, so first-writer evidence is untouched"
    assert merge.is_completion_marker_recorded(
        proof=repeated,
        marker=_marker(run_id="run-7", record_id=_RECORD_ID, completed_at=_LATE),
    ), "the contribution identity is run plus record; the instant is not part of it"


def test_the_rollout_start_converges_on_the_earliest_commit_in_any_order(tmp_path):
    merge, proof = _merge(), _proof()
    path = tmp_path / "state" / "coexistence-proof.json"
    _write_proof(path=path, proof=proof.initial_proof_record())

    def _apply(committed_at: str) -> None:
        _write_proof(
            path=path,
            proof=merge.rollout_update(
                proof=proof.read_proof_record(path=path, owner_uid=_uid()).unwrap(),
                target_committed_at=committed_at,
            ),
        )

    _apply(_LATE)
    after_late = proof.read_proof_record(path=path, owner_uid=_uid()).unwrap()
    _apply(_EARLY)
    after_early = proof.read_proof_record(path=path, owner_uid=_uid()).unwrap()
    _apply(_LATE)
    after_replay = proof.read_proof_record(path=path, owner_uid=_uid()).unwrap()

    assert after_late.rollout_started_at == _LATE
    assert (
        after_early.rollout_started_at == _EARLY
    ), "a later replay of an EARLIER commit corrects it"
    assert (
        after_replay.rollout_started_at == _EARLY
    ), "and a replay of the later one leaves it alone"
    assert merge.is_rollout_satisfied(proof=after_replay, target_committed_at=_LATE)
    assert not merge.is_rollout_satisfied(
        proof=proof.initial_proof_record(), target_committed_at=_EARLY
    )


def test_only_an_anthropic_factory_assignment_qualifies_for_the_rollout_rule():
    merge = _merge()

    assert merge.ROLLOUT_PROVIDER == "anthropic"
    assert merge.ROLLOUT_PURPOSE == "factory"
    assert merge.qualifies_for_rollout(provider="anthropic", purpose="factory")
    assert not merge.qualifies_for_rollout(provider="anthropic", purpose="interactive")
    assert not merge.qualifies_for_rollout(provider="openai", purpose="factory")


def test_a_rollout_write_preserves_every_field_it_does_not_own():
    merge, proof = _merge(), _proof()
    standing = proof.ProofRecord(
        rollout_started_at=_LATE,
        successful_consumer_dates=("2026-09-30",),
        completion_markers=(
            _marker(run_id="run-9", record_id=_PEER_RECORD_ID, completed_at=_LATE),
        ),
        soak_started_at=_LATE,
        simultaneous_spread={"first_consumer_run_id": "run-1"},
        production_success={"consumer_run_id": "run-9", "completed_at": _LATE},
        legacy_pool_absence_success={"consumer_run_id": "run-9", "completed_at": _LATE},
        last_auth_failure_at=_LATE,
    )

    corrected = merge.rollout_update(proof=standing, target_committed_at=_EARLY)

    assert corrected.rollout_started_at == _EARLY
    for member in (
        "successful_consumer_dates",
        "completion_markers",
        "soak_started_at",
        "simultaneous_spread",
        "production_success",
        "legacy_pool_absence_success",
        "last_auth_failure_at",
    ):
        assert getattr(corrected, member) == getattr(
            standing, member
        ), f"{member} belongs to the deferred seven-day proof slice and must survive untouched"
