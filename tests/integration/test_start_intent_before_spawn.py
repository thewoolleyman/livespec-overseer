"""Integration tests for the start-intent record written BEFORE a session spawn.

SPECIFICATION/spec.md requires an authorized unattended operator surface to
durably record a start-intent BEFORE it spawns a tracked session, naming the
action, the target track, and the invoker on whose behalf it acts, for EVERY
start it performs. SPECIFICATION/contracts.md puts that record under the
per-repository gitignored scratch area and states that a record carrying no
outcome MUST be read as an attempt that FAILED rather than as work in progress.

THE ORDERING IS THE PROPERTY, AND IT IS WHY THESE TESTS FORK AND KILL. A control
that asserts only the record's CONTENT passes identically against an
implementation that journals at the TAIL of its dispatch — which is exactly the
implementation this scenario exists to refuse, because such a record cannot
describe an act that did not return. So the load-bearing tests run `act` in a
forked child whose spawn seam SIGKILLs its own process: SIGKILL cannot be
caught, handled, or deferred, so no post-hoc write is possible and a record that
is nonetheless on file can only have been written before the spawn was issued.
"""

from __future__ import annotations

import importlib
import json
import os
import signal
import sys
from pathlib import Path

import pytest

__all__: list[str] = []

OVERSEER_DIR = Path(__file__).resolve().parents[2] / "overseer"
WORK_ITEM_ID = "overseer-vts4lo"
INVOKER = "operator-seat-1"
# Distinct from any signalled death, so a child that RETURNS from `act` instead
# of dying at the spawn is reported as a returned child rather than as a kill.
CHILD_RETURNED = 91


def foreman_act():
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_act")


def plan_document(*, repo: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "repo": str(repo),
        "sources": {"snapshot": {"status": "ok", "mode": "daemon-snapshot"}},
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "tick_generation": 7,
            "rows": [
                {
                    "repo": str(repo),
                    "topic": "alpha",
                    "tmux": "alpha",
                    "runtime": "claude",
                    "status": "session-gone",
                    "session_identity": f"none:{repo}:alpha",
                }
            ],
        },
        "dispatch_journal": [],
    }


def work_item_document(*, repo: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "repo": str(repo),
        "sources": {
            "snapshot": {"status": "ok", "mode": "daemon-snapshot"},
            "dispatch_journal": {"status": "ok", "records_read": 1},
        },
        "snapshot": {"daemon_instance_id": "daemon-1", "tick_generation": 7, "rows": []},
        "needs_attention": {"items": [{"id": WORK_ITEM_ID, "kind": "work-item"}]},
        "dispatch_journal": [],
    }


def plan_proposal(
    *, repo: Path, action_id: str = "plan_start", invoker: str | None = INVOKER
) -> dict[str, object]:
    proposal: dict[str, object] = {
        "schema_version": 1,
        "action_id": action_id,
        "repo": str(repo),
        "topic": "alpha",
        "session_name": "alpha",
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "tick_generation": 7,
            "session_identity": f"none:{repo}:alpha",
        },
        "classifier": {
            "action": "start",
            "start": {"repo": str(repo), "topic": "alpha", "session_name": "alpha"},
        },
    }
    if invoker is not None:
        proposal["invoker"] = invoker
    return proposal


def work_item_proposal(*, repo: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "action_id": "work_item_session_start",
        "repo": str(repo),
        "topic": WORK_ITEM_ID,
        "session_name": WORK_ITEM_ID,
        "invoker": INVOKER,
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "tick_generation": 7,
            "session_identity": None,
        },
        "classifier": {
            "action": "start",
            "start": {"repo": str(repo), "topic": WORK_ITEM_ID, "session_name": WORK_ITEM_ID},
        },
        "work_item_session": {
            "work_item_id": WORK_ITEM_ID,
            "session_name": WORK_ITEM_ID,
            "handoff": "durable handoff\n",
        },
    }


def intent_records(*, repo: Path) -> list[Path]:
    root = repo / "tmp" / "overseer" / "foreman" / "start-intents"
    return sorted(root.rglob("*.json"))


def sole_intent_record(*, repo: Path) -> dict[str, object]:
    records = intent_records(repo=repo)
    assert len(records) == 1, f"expected exactly one start-intent record, found {records}"
    parsed = json.loads(records[0].read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def act_in_a_child_killed_at_the_spawn(
    *, proposal: dict[str, object], document: dict[str, object]
) -> int:
    """Run `act` in a forked child whose spawn seam kills that child outright.

    `os._exit` in the `finally` leg keeps a child that never reaches the spawn
    from unwinding back into the parent's pytest frame and running the rest of
    the session a second time; the parent tells the two apart by the wait status.
    """
    pid = os.fork()
    if pid == 0:
        try:
            module = foreman_act()
            _ = module.act(
                proposal=proposal,
                seams=module.ActSeams(
                    gather=lambda *, repo, snapshot_path: document,
                    run=kill_this_process,
                    append_journal=lambda *, repo, record: None,
                ),
            )
        finally:
            os._exit(CHILD_RETURNED)
    _pid, status = os.waitpid(pid, 0)
    return status


def kill_this_process(*, argv: list[str]) -> None:
    """The spawn seam: die between issuing the spawn and returning from it."""
    assert argv
    os.kill(os.getpid(), signal.SIGKILL)


def assert_killed_at_the_spawn(*, status: int) -> None:
    assert os.WIFSIGNALED(status), (
        "the child must have died AT the spawn for this to be an ordering control; "
        f"it exited normally with status {status}"
    )
    assert os.WTERMSIG(status) == signal.SIGKILL


@pytest.mark.integration
def test_a_killed_plan_start_leaves_an_attempted_and_failed_record_naming_its_invoker(*, tmp_path):
    """The scenario's own control: the record survives a surface that does not.

    `plan_start` is the half research note 002 measured as writing NOTHING before
    its spawn, so this is the leg that a fix scoped to the already-instrumented
    work-item path would leave untouched.
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    status = act_in_a_child_killed_at_the_spawn(
        proposal=plan_proposal(repo=repo), document=plan_document(repo=repo)
    )

    assert_killed_at_the_spawn(status=status)
    record = sole_intent_record(repo=repo)
    assert record["action_id"] == "plan_start"
    assert record["target"] == "alpha"
    assert record["invoker"] == INVOKER
    # No outcome: per contracts.md this record reads as an attempt that FAILED,
    # which is what distinguishes it both from live work and from a start that
    # was never attempted at all.
    assert record["outcome"] is None


@pytest.mark.integration
def test_a_killed_work_item_session_start_leaves_the_same_attempted_and_failed_record(*, tmp_path):
    """The other start family, whose pre-spawn claim is NOT this record.

    The claim carries neither the action nor the invoker, so its presence cannot
    discharge the obligation — and this asserts the claim is still written, since
    the intent is meant to build on that machinery rather than replace it.
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    status = act_in_a_child_killed_at_the_spawn(
        proposal=work_item_proposal(repo=repo), document=work_item_document(repo=repo)
    )

    assert_killed_at_the_spawn(status=status)
    record = sole_intent_record(repo=repo)
    assert record["action_id"] == "work_item_session_start"
    assert record["target"] == WORK_ITEM_ID
    assert record["invoker"] == INVOKER
    assert record["outcome"] is None
    claim = repo / "tmp" / "overseer" / "foreman" / "work-items" / WORK_ITEM_ID / "claim.json"
    assert claim.is_file()


@pytest.mark.integration
@pytest.mark.parametrize(
    "action_id", ["plan_start", "qualifying_session_start", "supervisor_pair_start"]
)
def test_every_start_action_has_its_intent_on_file_by_the_time_it_spawns(
    *, tmp_path, action_id: str
):
    """The obligation attaches to EVERY start, and the run seam is the observer.

    Reading the record from inside the spawn seam is an ordering assertion the
    surviving process can make: at that instant the spawn has been issued and
    `act` has not returned, so a record readable there was written before it.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    module = foreman_act()
    observed: list[dict[str, object]] = []

    def observe_then_succeed(*, argv: list[str]):
        assert argv
        observed.append(sole_intent_record(repo=repo))
        return module.CommandResult(returncode=0, stderr="", stdout="")

    result = module.act(
        proposal=plan_proposal(repo=repo, action_id=action_id),
        seams=module.ActSeams(
            gather=lambda *, repo, snapshot_path: plan_document(repo=Path(repo)),
            run=observe_then_succeed,
            append_journal=lambda *, repo, record: None,
        ),
    )

    assert result["outcome"] == "acted"
    assert observed == [
        {
            "schema_version": 1,
            "kind": "foreman-start-intent",
            "action_id": action_id,
            "target": "alpha",
            "invoker": INVOKER,
            "outcome": None,
        }
    ]


@pytest.mark.integration
def test_a_proposal_naming_no_invoker_records_the_surfaces_own_identity(*, tmp_path):
    """An unnamed invoker means the surface acted on its own behalf.

    That is a true answer rather than a placeholder, which matters because the
    record's whole job is to say who made the attempt.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    module = foreman_act()

    result = module.act(
        proposal=plan_proposal(repo=repo, invoker=None),
        seams=module.ActSeams(
            gather=lambda *, repo, snapshot_path: plan_document(repo=Path(repo)),
            run=lambda *, argv: module.CommandResult(returncode=0, stderr="", stdout=""),
            append_journal=lambda *, repo, record: None,
        ),
    )

    assert result["outcome"] == "acted"
    assert sole_intent_record(repo=repo)["invoker"] == "repo-foreman"


@pytest.mark.integration
def test_a_start_intent_that_cannot_be_persisted_refuses_the_spawn(*, tmp_path, capsys):
    """Fail CLOSED: an unrecordable intent must not become an unrecorded attempt."""
    repo = tmp_path / "repo"
    (repo / "tmp" / "overseer" / "foreman").mkdir(parents=True)
    # A regular file where the record root must be a directory, so the write
    # fails for a reason no amount of retrying inside the surface can fix.
    (repo / "tmp" / "overseer" / "foreman" / "start-intents").write_text("", encoding="utf-8")
    module = foreman_act()
    spawns: list[list[str]] = []

    result = module.act(
        proposal=plan_proposal(repo=repo),
        seams=module.ActSeams(
            gather=lambda *, repo, snapshot_path: plan_document(repo=Path(repo)),
            run=lambda *, argv: spawns.append(argv) or 0,
            append_journal=lambda *, repo, record: None,
        ),
    )

    assert result == {
        "action_id": "plan_start",
        "mutated": False,
        "outcome": "refused",
        "reason": "start_intent_write_failed",
    }
    assert spawns == []
    _ = capsys.readouterr()


@pytest.mark.integration
def test_a_work_item_session_start_whose_intent_fails_leaves_no_claim(*, tmp_path, capsys):
    """The intent precedes the claim, so a failed intent leaves nothing reading as live."""
    repo = tmp_path / "repo"
    (repo / "tmp" / "overseer" / "foreman").mkdir(parents=True)
    (repo / "tmp" / "overseer" / "foreman" / "start-intents").write_text("", encoding="utf-8")
    module = foreman_act()
    spawns: list[list[str]] = []

    result = module.act(
        proposal=work_item_proposal(repo=repo),
        seams=module.ActSeams(
            gather=lambda *, repo, snapshot_path: work_item_document(repo=Path(repo)),
            run=lambda *, argv: spawns.append(argv) or 0,
            append_journal=lambda *, repo, record: None,
        ),
    )

    assert result["outcome"] == "refused"
    assert result["reason"] == "start_intent_write_failed"
    assert spawns == []
    claim = repo / "tmp" / "overseer" / "foreman" / "work-items" / WORK_ITEM_ID / "claim.json"
    assert not claim.exists()
    _ = capsys.readouterr()


@pytest.mark.integration
def test_the_foreman_act_disposition_record_names_the_invoker(*, tmp_path):
    """This repository owns its own journal shape, so the invoker is discharged here."""
    repo = tmp_path / "repo"
    repo.mkdir()
    module = foreman_act()
    journaled: list[dict[str, object]] = []

    result = module.act(
        proposal=plan_proposal(repo=repo),
        seams=module.ActSeams(
            gather=lambda *, repo, snapshot_path: plan_document(repo=Path(repo)),
            run=lambda *, argv: module.CommandResult(returncode=0, stderr="", stdout=""),
            append_journal=lambda *, repo, record: journaled.append(record),
        ),
    )

    assert result["outcome"] == "acted"
    assert journaled == [
        {
            "stage": "foreman-act",
            "action_id": "plan_start",
            "outcome": "acted",
            "reason": "started",
            "mutated": True,
            "invoker": INVOKER,
        }
    ]
