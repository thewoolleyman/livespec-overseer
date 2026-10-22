"""Codex adoption reads only carriers in the daemon's OWN Codex home (overseer-crjbmp).

Codex identity comes from a HOST-WIDE ``/proc`` scan: every pid whose ``comm`` is
``codex`` is a carrier, and each one's cwd, fd table and ``CODEX_HOME`` are read as
adoption evidence. Nothing scoped that scan, so a daemon running against a scratch
``CODEX_HOME`` -- which is what the isolated live exercise
(``tests/test_codex_herdr_live_exercise_controller.py``) runs -- read the operator's
own authenticated Codex processes beside its stub. Measured on the release host
2026-10-22 with ``pgrep -c codex`` at 7: the exercise's adoption stage failed because
the daemon's snapshot never bound ``exercise-topic`` to the stub's rollout.

**Pane membership is NOT a sufficient scope, which is why this scopes by Codex home.**
The exercise daemon's pane map is not confined to the exercise's own terminal instance:
``pane_router_reads._tmux_pid_coordinates`` folds in the AMBIENT tmux server whenever
the daemon's environment names no explicit tmux socket, so the operator's real panes --
and the Codex processes inside them -- resolve to coordinates the exercise daemon can
see. Measured in the factory 2026-10-22 by running seven decoy ``codex``-named
processes inside real tmux panes beside an exercise run. So ``OUTSIDE_PANE_PID`` below
is deliberately IN the pane map: a scope that only asked "is this carrier in a pane I
can see" would admit it.

The Codex home is the right seam because it is the one the daemon's own joins already
turn on. The index that names a session (``session_index.jsonl``), the rollouts whose
filenames carry its id, and the state database that binds it to a repository all live
under ONE Codex home. A carrier running under a DIFFERENT one cannot be named by this
daemon's index and cannot have a row in this daemon's database, so reading it can only
add noise -- and noise in the live-id candidate set is what turns a clean binding into
an ambiguity refusal.

**It narrows nothing on the real fleet, and that is deliberate.** Every carrier there
shares the daemon account's ``~/.codex``, declared or inherited, so the scoped set is
the whole set and every ambiguity guard sees exactly the candidates it sees today. The
exclusion needs POSITIVE evidence of a different home: a carrier whose environ cannot
be read at all stays in scope, which is what
``test_a_carrier_whose_environ_cannot_be_read_stays_in_scope`` pins.

Every assertion here is a BEHAVIOUR assertion over the shipped readers rather than a
probe for a new symbol, so the Red moment is the leak itself: the recorded reads name
the operator's pids, and the operator's session id is in the candidate set. Two of the
four tests are controls that pass in both directions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import _supervisor_codex_adoption
import _supervisor_codex_identity
import codex_sessions
import herdr_identity
from test_supervisor_builders import adopt_sup, codex_idle_capture, make_plan
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

# The exercise's stub Codex, in the exercise's own pane, holding its own rollout.
EXERCISE_PID = 9000
EXERCISE_PANE_PID = 7001
# The operator's own authenticated Codex: a 0.16x carrier holding no rollout of its own,
# whose shared app-server holds it instead. Its pane IS in the daemon's pane map.
OUTSIDE_PID = 9100
OUTSIDE_PANE_PID = 7002
OUTSIDE_APP_SERVER_PID = 9200
# A carrier in the exercise's own pane whose environ cannot be read at all.
UNREADABLE_PID = 9300

EXERCISE_SESSION_ID = "01a0f0d2-8ae8-7ec3-9c29-5ff9bef058f2"
OUTSIDE_SESSION_ID = "019f0000-0000-7000-8000-000000000001"

OUTSIDE_CARRIER_PIDS = (OUTSIDE_PID, OUTSIDE_APP_SERVER_PID)


def coordinate(*, pane_id: str) -> str:
    """A backend-qualified herdr coordinate for one pane of one server generation."""
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path="/run/herdr.sock",
            server_pid=401,
            server_starttime="2026-10-22T00:00:00Z",
            pane_id=pane_id,
        )
    )


EXERCISE_COORDINATE = coordinate(pane_id="w1:p1")
OUTSIDE_COORDINATE = coordinate(pane_id="w9:p9")


def rollout(*, codex_home: Path, session_id: str) -> str:
    """The rollout PATH for a session id -- a filename, never a body."""
    day = codex_home / "sessions" / "2026" / "10" / "22"
    return str(day / f"rollout-2026-10-22T00-00-00-{session_id}.jsonl")


def index_record(*, codex_home: Path, session_id: str, topic: str) -> None:
    """The durable ``id -> thread_name`` record a ``/rename`` appends."""
    codex_home.mkdir(parents=True, exist_ok=True)
    _ = (codex_home / "session_index.jsonl").write_text(
        json.dumps({"id": session_id, "thread_name": topic}) + "\n", encoding="utf-8"
    )


@dataclass(kw_only=True)
class Reads:
    """Which pids each host reader was actually asked about."""

    cwd: set[int] = field(default_factory=set)
    fd_targets: set[int] = field(default_factory=set)


@dataclass(frozen=True, kw_only=True)
class World:
    """One host: the exercise's stub Codex beside the operator's own Codex."""

    sup: object
    repo: Path
    exercise_home: Path
    outside_home: Path
    reads: Reads


def make_world(*, tmp_path: Path) -> World:
    """The measured topology, with every Codex host coupling injected and RECORDED."""
    repo, topic = make_plan(tmp_path=tmp_path, topic="topic")
    operator_repo, _ = make_plan(tmp_path=tmp_path, repo_name="operator", topic="operator")
    exercise_home = tmp_path / "scratch" / ".codex"
    outside_home = tmp_path / "operator-home" / ".codex"
    index_record(codex_home=exercise_home, session_id=EXERCISE_SESSION_ID, topic=topic)
    index_record(codex_home=outside_home, session_id=OUTSIDE_SESSION_ID, topic=topic)

    fake = FakeTmux()
    fake.serve(
        session=EXERCISE_COORDINATE, repo=repo, capture=codex_idle_capture(ctx=40), cmd="bun"
    )
    fake.serve(
        session=OUTSIDE_COORDINATE,
        repo=operator_repo,
        capture=codex_idle_capture(ctx=40),
        cmd="bun",
    )
    # The operator's pane is deliberately visible to this daemon -- see the module header.
    fake.pane_pids = {
        EXERCISE_PANE_PID: EXERCISE_COORDINATE,
        OUTSIDE_PANE_PID: OUTSIDE_COORDINATE,
    }

    fd_targets = {
        EXERCISE_PID: [rollout(codex_home=exercise_home, session_id=EXERCISE_SESSION_ID)],
        OUTSIDE_APP_SERVER_PID: [rollout(codex_home=outside_home, session_id=OUTSIDE_SESSION_ID)],
    }
    cwds = {
        EXERCISE_PID: str(repo),
        OUTSIDE_PID: str(operator_repo),
        OUTSIDE_APP_SERVER_PID: "/",
        UNREADABLE_PID: str(repo),
    }
    environs = {
        EXERCISE_PID: f"CODEX_HOME={exercise_home}\0HOME={tmp_path / 'scratch'}\0",
        # The operator's real shape: no CODEX_HOME at all, so its Codex home is the
        # `.codex` under the HOME it declares.
        OUTSIDE_PID: f"HOME={tmp_path / 'operator-home'}\0",
        OUTSIDE_APP_SERVER_PID: f"HOME={tmp_path / 'operator-home'}\0",
    }

    reads = Reads()

    def cwd_of(*, pid: int) -> str | None:
        reads.cwd.add(pid)
        return cwds.get(pid)

    def fd_targets_of(*, pid: int) -> list[str]:
        reads.fd_targets.add(pid)
        return fd_targets.get(pid, [])

    def environ_of(*, pid: int) -> bytes | None:
        declared = environs.get(pid)
        return None if declared is None else declared.encode()

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={
            EXERCISE_PID: EXERCISE_PANE_PID,
            OUTSIDE_PID: OUTSIDE_PANE_PID,
            OUTSIDE_APP_SERVER_PID: OUTSIDE_PID,
            UNREADABLE_PID: EXERCISE_PANE_PID,
        },
        starttimes={},
        watch_repos=[str(repo)],
        codex_home=str(exercise_home),
        codex_pids_of_comm=lambda *, comm: (
            [EXERCISE_PID, OUTSIDE_PID, OUTSIDE_APP_SERVER_PID, UNREADABLE_PID]
            if comm == codex_sessions.CODEX_COMM
            else []
        ),
        codex_fd_targets_of=fd_targets_of,
        codex_cwd_of=cwd_of,
        children_of=lambda *, pid: [OUTSIDE_APP_SERVER_PID] if pid == OUTSIDE_PID else [],
        environ_of=environ_of,
    )
    return World(
        sup=sup,
        repo=repo,
        exercise_home=exercise_home,
        outside_home=outside_home,
        reads=reads,
    )


def test_an_outside_codex_carriers_cwd_and_fd_table_are_never_read(*, tmp_path):
    """The DEFECT, stated as the rule it broke: out-of-home carriers are not evidence.

    A whole tick's worth of Codex reading runs here -- the adoption join, the per-tick
    live map and the identity pass all go through the same scan -- and not one of them
    may reach the operator's ``/proc`` cwd or fd table.
    """
    world = make_world(tmp_path=tmp_path)

    world.sup.refresh_codex_sessions()
    _ = world.sup.adopt_sessions()

    assert world.reads.cwd.isdisjoint(OUTSIDE_CARRIER_PIDS), (
        "the daemon read the /proc cwd of a Codex carrier running under another "
        f"CODEX_HOME: {sorted(world.reads.cwd & set(OUTSIDE_CARRIER_PIDS))}"
    )
    assert world.reads.fd_targets.isdisjoint(OUTSIDE_CARRIER_PIDS), (
        "the daemon read the /proc fd table of a Codex carrier running under another "
        f"CODEX_HOME: {sorted(world.reads.fd_targets & set(OUTSIDE_CARRIER_PIDS))}"
    )


def test_an_outside_sessions_rollout_never_enters_the_live_candidate_set(*, tmp_path):
    """A foreign rollout id is not a live candidate, so it cannot force an ambiguity.

    The live-id set is deliberately unattributed, but it is still SCOPED: an id no
    reachable index can name and no reachable database can bind has nothing to
    contribute except another candidate for a refusal to count.
    """
    identity = _supervisor_codex_identity
    world = make_world(tmp_path=tmp_path)

    # Built through the SHIPPED bundle builder, so this cannot pass against a reader
    # surface the daemon itself does not assemble.
    readers = _supervisor_codex_adoption.codex_host_readers(sup=world.sup)
    carriers = identity.pane_codex_carriers(
        sup=world.sup,
        pane_pid_to_session=world.sup.tmux.pane_pid_sessions(),
        readers=readers,
    )

    assert OUTSIDE_SESSION_ID not in identity.live_rollout_ids(
        carriers=[EXERCISE_PID, OUTSIDE_PID, OUTSIDE_APP_SERVER_PID, UNREADABLE_PID],
        readers=readers,
    ), "the operator's live session id entered this daemon's live-id candidate set"
    assert sorted(carrier.pid for carrier in carriers) == [EXERCISE_PID, UNREADABLE_PID], (
        "the identity pass considered a carrier from another Codex home: "
        f"{sorted(carrier.pid for carrier in carriers)}"
    )


def test_the_exercise_carrier_is_still_adopted_with_an_outside_carrier_present(*, tmp_path):
    """The control: scoping must not cost the run its own binding.

    This is the exercise's adoption stage, in miniature -- the snapshot binds the topic
    to the stub's own rollout -- and it is what the release host could not reach.
    """
    world = make_world(tmp_path=tmp_path)

    world.sup.refresh_codex_sessions()

    live = world.sup.live_codex
    assert list(live) == [(EXERCISE_COORDINATE, "topic")]
    assert live[(EXERCISE_COORDINATE, "topic")].session_id == EXERCISE_SESSION_ID
    assert live[(EXERCISE_COORDINATE, "topic")].pid == EXERCISE_PID


def test_a_carrier_whose_environ_cannot_be_read_stays_in_scope(*, tmp_path):
    """Exclusion needs POSITIVE evidence of another home; unreadable is not evidence.

    The safe direction is to keep reading a carrier the daemon cannot classify, so a
    transient unreadable environ can never make a live track invisible.
    """
    world = make_world(tmp_path=tmp_path)

    world.sup.refresh_codex_sessions()

    assert UNREADABLE_PID in world.reads.cwd, (
        "a carrier whose environ could not be read was dropped from the scan, so an "
        "unreadable environ can hide a live track"
    )
