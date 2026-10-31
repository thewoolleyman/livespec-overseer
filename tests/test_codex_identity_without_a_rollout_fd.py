"""A live Codex track whose carrier holds no rollout file open (overseer-iffpgw).

Measured 2026-10-14 on daemon 5.28.3: `factory-test-first-enforcement` was running as
Codex in herdr pane `w2H:p3`, and both `supervisor.py list` and the daemon reported it
`session-gone`. Two facts combined. Its mapping row still carried the LEGACY TMUX
locator retired on 2026-10-10, and nothing rebound a mapped row from a dead tmux
locator to a live herdr pane. And Codex identity discovery joins a live carrier to its
session through the rollout file that carrier holds OPEN — which a Codex 0.16x carrier
does not hold at all, because persistence moved into a SHARED managed app-server whose
rollout set belongs to many independent sessions.

So the identity comes from the evidence that remains, and only from live process
evidence: the carrier's own cwd and `CODEX_HOME`, the live session ids any carrier or
descendant holds open (unattributed — a shared app-server is no obstacle), and the
carrier's own state database binding exactly one of those ids to its repository.
Nothing is read from a rollout body, and nothing is inferred from which rollout was
written most recently.

The subject module is imported INSIDE the test bodies via `importlib`, so the Red
moment is a genuine assertion failure ("the module is not on disk yet") rather than a
collection error that would only prove the module unimportable.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import _supervisor_evaluate_target
import _supervisor_view
import codex_sessions
import herdr_identity
import registry
from test_supervisor_builders import adopt_sup, codex_idle_capture, make_plan
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

_PACKAGE = Path(__file__).resolve().parent.parent / "overseer"

# The tracked carrier holds NO rollout fd; the shared app-server holds every live
# session's rollout and is a descendant of a DIFFERENT carrier (the operator's), which
# is the topology measured on 2026-09-30 and again on 2026-10-14.
TRACKED_PID = 9000
OPERATOR_PID = 9100
APP_SERVER_PID = 9200
PANELESS_PID = 9300
CWD_LESS_PID = 9400
TRACKED_PANE_PID = 7001
OPERATOR_PANE_PID = 7002

SESSION_ID = "01a0f0d2-8ae8-7ec3-9c29-5ff9bef058f2"
OPERATOR_SESSION_ID = "019f0000-0000-7000-8000-000000000001"
SUCCESSOR_SESSION_ID = "01a0ffff-ffff-7fff-8fff-ffffffffffff"
DEAD_TMUX = "factory-test-first-enforcement"

_SCHEMA = "CREATE TABLE threads (id TEXT PRIMARY KEY, model TEXT, cwd TEXT)"
_INSERT = "INSERT INTO threads (id, model, cwd) VALUES (?, ?, ?)"
_SCHEMA_WITHOUT_CWD = "CREATE TABLE threads (id TEXT PRIMARY KEY, model TEXT)"
_INSERT_WITHOUT_CWD = "INSERT INTO threads (id, model) VALUES (?, ?)"


def codex_identity():
    """The Codex pane-identity module, imported once it exists on disk."""
    assert (
        _PACKAGE / "_supervisor_codex_identity.py"
    ).is_file(), "overseer/_supervisor_codex_identity.py has not been implemented yet"
    return importlib.import_module("_supervisor_codex_identity")


def codex_runtime_model():
    """The Codex state-database reader, which gains the repository-binding predicate."""
    module = importlib.import_module("_codex_runtime_model")
    assert hasattr(
        module, "read_state_database_repository"
    ), "_codex_runtime_model.read_state_database_repository has not been implemented yet"
    return module


def codex_rebind():
    """The coordinate-rebinding module, imported once it exists on disk."""
    assert (
        _PACKAGE / "_supervisor_codex_rebind.py"
    ).is_file(), "overseer/_supervisor_codex_rebind.py has not been implemented yet"
    return importlib.import_module("_supervisor_codex_rebind")


def row_of(*, store, topic="topic"):
    """The one mapping row for `topic`, re-read from the store."""
    return next(row for row in registry.read_valid_mapping(store_path=store) if row.topic == topic)


def resolve(*, world, act, topic="topic"):
    """Drive the REAL evaluation target resolution, capturing the daemon's own log."""
    world.sup.refresh_codex_sessions()
    log = io.StringIO()
    with contextlib.redirect_stderr(log):
        outcome = _supervisor_evaluate_target.resolve_evaluate_target(
            sup=world.sup, track=row_of(store=world.store, topic=topic), act=act
        )
    return outcome, log.getvalue()


def coordinate(*, pane_id: str) -> str:
    """A backend-qualified herdr coordinate for one pane of one server generation."""
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path="/run/herdr.sock",
            server_pid=401,
            server_starttime="2026-10-10T00:00:00Z",
            pane_id=pane_id,
        )
    )


TRACKED_COORDINATE = coordinate(pane_id="w2H:p3")
OPERATOR_COORDINATE = coordinate(pane_id="w1:p1")


def write_state_database(*, path, rows=(), schema=_SCHEMA, insert=_INSERT):
    """A real SQLite state database, so the reader is exercised rather than simulated."""
    connection = sqlite3.connect(path)
    with connection:
        _ = connection.execute(schema)
        if rows:
            _ = connection.executemany(insert, rows)
    connection.close()


def rollout(*, codex_home, session_id) -> str:
    """The rollout PATH for a session id — a filename, never a body."""
    day = Path(codex_home) / "sessions" / "2026" / "10" / "14"
    return str(day / f"rollout-2026-10-14T00-00-00-{session_id}.jsonl")


def add_row(*, store, repo, topic, tmux, identity):
    registry.append_mapping(
        track=registry.PlanTrack(
            topic=topic,
            repo=str(repo),
            tmux=tmux,
            epic=f"epic-{topic}",
            observed_session_identity=identity,
        ),
        store_path=store,
    )


@dataclass(frozen=True, kw_only=True)
class World:
    """One host: a tracked Codex pane, an operator pane, and their shared app-server."""

    sup: object
    repo: Path
    other_repo: Path
    home: Path
    store: Path


def make_world(*, tmp_path, rows=None, cwds=None, panes=None, indexed=None):
    """The measured topology, with every Codex host coupling injected.

    `rows` overrides the mapping store's contents, `cwds` the carriers' cwds and `panes`
    the pane-pid map, so a test can drive one refusal without re-stating the whole host.
    `indexed` gives the TRACKED carrier a rollout fd of its own, named in the Codex
    index — the pre-0.159 topology, which the ordinary indexed join answers for.
    """
    repo, topic = make_plan(tmp_path=tmp_path, topic="topic")
    other_repo, _other_topic = make_plan(tmp_path=tmp_path, repo_name="operator", topic="operator")
    home = tmp_path / "codex-home"
    home.mkdir()
    write_state_database(
        path=home / "state_1.sqlite",
        rows=[
            (SESSION_ID, "gpt-5.6-luna", str(repo)),
            (OPERATOR_SESSION_ID, "gpt-5.6-luna", str(other_repo)),
        ],
    )
    fake = FakeTmux()
    fake.serve(session=TRACKED_COORDINATE, repo=repo, capture=codex_idle_capture(ctx=40), cmd="bun")
    fake.serve(
        session=OPERATOR_COORDINATE,
        repo=other_repo,
        capture=codex_idle_capture(ctx=40),
        cmd="bun",
    )
    fake.pane_pids = (
        panes
        if panes is not None
        else {
            TRACKED_PANE_PID: TRACKED_COORDINATE,
            OPERATOR_PANE_PID: OPERATOR_COORDINATE,
        }
    )
    # Only the app-server holds rollout fds, and it holds BOTH live sessions' — unless a
    # test opts the tracked carrier back into holding its own, indexed rollout.
    fd_targets = {
        APP_SERVER_PID: [
            rollout(codex_home=home, session_id=SESSION_ID),
            rollout(codex_home=home, session_id=OPERATOR_SESSION_ID),
        ]
    }
    if indexed is not None:
        fd_targets[TRACKED_PID] = [rollout(codex_home=home, session_id=indexed)]
        (home / "session_index.jsonl").write_text(
            json.dumps({"id": indexed, "thread_name": "topic"}) + "\n", encoding="utf-8"
        )
    carrier_cwds = (
        cwds
        if cwds is not None
        else {
            TRACKED_PID: str(repo),
            OPERATOR_PID: str(other_repo),
            APP_SERVER_PID: "/",
            PANELESS_PID: str(repo),
        }
    )
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    store = tmp_path / "map.jsonl"
    for row in rows if rows is not None else [(repo, "topic", DEAD_TMUX, f"codex:{SESSION_ID}")]:
        add_row(store=store, repo=row[0], topic=row[1], tmux=row[2], identity=row[3])
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={
            TRACKED_PID: TRACKED_PANE_PID,
            OPERATOR_PID: OPERATOR_PANE_PID,
            APP_SERVER_PID: OPERATOR_PID,
            CWD_LESS_PID: TRACKED_PANE_PID,
        },
        starttimes={},
        watch_repos=[str(repo), str(other_repo)],
        codex_home=str(home),
        codex_pids_of_comm=lambda *, comm: (
            [TRACKED_PID, OPERATOR_PID, APP_SERVER_PID, PANELESS_PID, CWD_LESS_PID]
            if comm == codex_sessions.CODEX_COMM
            else []
        ),
        codex_foreground_pgrp_of=lambda *, pid: (pid if pid != APP_SERVER_PID else None),
        codex_fd_targets_of=lambda *, pid: fd_targets.get(pid, []),
        codex_cwd_of=lambda *, pid: carrier_cwds.get(pid),
        children_of=lambda *, pid: [APP_SERVER_PID] if pid == OPERATOR_PID else [],
        environ_of=lambda *, pid: b"",
    )
    return World(sup=sup, repo=repo, other_repo=other_repo, home=home, store=store)


# --- assertion 1: identity from live process evidence, with no rollout fd -------------


def test_a_codex_carrier_holding_no_rollout_fd_resolves_to_its_own_live_session(*, tmp_path):
    _module = codex_identity()
    world = make_world(tmp_path=tmp_path)

    world.sup.refresh_codex_sessions()

    live = world.sup.live_codex
    assert list(live) == [(TRACKED_COORDINATE, "topic")]
    assert live[(TRACKED_COORDINATE, "topic")].session_id == SESSION_ID
    assert live[(TRACKED_COORDINATE, "topic")].cwd == str(world.repo)
    assert live[(TRACKED_COORDINATE, "topic")].pid == TRACKED_PID


def test_the_shared_app_servers_rollout_set_names_no_carrier_of_its_own(*, tmp_path):
    """Liveness comes from the unattributed set; attribution from the state database.

    The app-server's own cwd is bound to no thread row, so the carrier that physically
    holds every rollout resolves to no session at all — the mis-attribution the shared
    daemon makes possible is structurally unavailable here.
    """
    module = codex_identity()
    world = make_world(tmp_path=tmp_path)
    readers = codex_sessions.CodexHostReaders(
        codex_home=str(world.home),
        pids_of_comm=world.sup.codex_pids_of_comm,
        cwd_of=world.sup.codex_cwd_of,
        fd_targets_of=world.sup.codex_fd_targets_of,
        children_of=world.sup.children_of,
        environ_of=world.sup.environ_of,
        foreground_pgrp_of=world.sup.codex_foreground_pgrp_of,
    )

    carriers = module.pane_codex_carriers(
        sup=world.sup,
        pane_pid_to_session=world.sup.tmux.pane_pid_sessions(),
        readers=readers,
    )

    assert module.live_rollout_ids(
        carriers=[TRACKED_PID, OPERATOR_PID, APP_SERVER_PID], readers=readers
    ) == frozenset({SESSION_ID, OPERATOR_SESSION_ID})
    # The detached app-server, paneless carrier, and unreadable-cwd process are dropped.
    by_pid = {carrier.pid: carrier for carrier in carriers}
    assert sorted(by_pid) == [TRACKED_PID, OPERATOR_PID]
    assert by_pid[TRACKED_PID].session_id == SESSION_ID
    assert by_pid[OPERATOR_PID].session_id == OPERATOR_SESSION_ID


def test_two_rows_recording_one_identity_bind_nothing(*, tmp_path):
    """Ambiguous evidence binds no track, rather than naming whichever row came first."""
    _module = codex_identity()
    duplicated = tmp_path / "duplicated"
    duplicated.mkdir()
    world = make_world(tmp_path=duplicated)
    add_row(
        store=world.store,
        repo=world.repo,
        topic="twin",
        tmux="dead-twin",
        identity=f"codex:{SESSION_ID}",
    )

    world.sup.refresh_codex_sessions()

    assert world.sup.live_codex == {}


def test_a_row_recording_the_identity_outside_the_carriers_repo_binds_nothing(*, tmp_path):
    """The operator row records the tracked identity, but its repo holds no carrier."""
    _module = codex_identity()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    world = make_world(
        tmp_path=elsewhere,
        rows=[(elsewhere / "operator", "operator", "dead-operator", f"codex:{SESSION_ID}")],
    )

    world.sup.refresh_codex_sessions()

    assert world.sup.live_codex == {}


def test_an_unresolvable_carrier_cwd_leaves_every_session_unidentified(*, tmp_path):
    """Two live sessions in ONE repository leave both unidentified rather than guessing."""
    _module = codex_identity()
    shared = tmp_path / "shared"
    shared.mkdir()
    world = make_world(tmp_path=shared)
    write_state_database(
        path=world.home / "state_2.sqlite",
        rows=[
            (SESSION_ID, "gpt-5.6-luna", str(world.repo)),
            (OPERATOR_SESSION_ID, "gpt-5.6-luna", str(world.repo)),
        ],
    )

    world.sup.refresh_codex_sessions()

    assert world.sup.live_codex == {}


def test_a_backend_reported_session_identifies_its_own_carrier_among_repo_siblings(*, tmp_path):
    """Pane-scoped backend evidence resolves a named track among repo siblings."""
    _module = codex_identity()
    shared = tmp_path / "reported"
    shared.mkdir()
    world = make_world(
        tmp_path=shared,
        rows=[(shared / "repo", "topic", DEAD_TMUX, "claude:dead:topic")],
        cwds={
            TRACKED_PID: str(shared / "repo"),
            OPERATOR_PID: str(shared / "repo"),
            APP_SERVER_PID: "/",
            PANELESS_PID: str(shared / "repo"),
        },
    )
    write_state_database(
        path=world.home / "state_2.sqlite",
        rows=[
            (SESSION_ID, "gpt-5.6-luna", str(world.repo)),
            (OPERATOR_SESSION_ID, "gpt-5.6-luna", str(world.repo)),
        ],
    )
    (world.home / "session_index.jsonl").write_text(
        json.dumps({"id": SESSION_ID, "thread_name": "topic"}) + "\n",
        encoding="utf-8",
    )
    world.sup.tmux.pane_agent_session = lambda *, session: (
        SESSION_ID if session == TRACKED_COORDINATE else None
    )

    world.sup.refresh_codex_sessions()

    live = world.sup.live_codex
    assert (TRACKED_COORDINATE, "topic") in live
    assert live[(TRACKED_COORDINATE, "topic")].session_id == SESSION_ID


# --- assertion 2: the dead tmux coordinate is rebound, old and new logged ------------


def test_a_dead_tmux_coordinate_is_rebound_to_the_pane_running_its_recorded_session(*, tmp_path):
    _module = codex_rebind()
    world = make_world(tmp_path=tmp_path)

    _outcome, log = resolve(world=world, act=True)

    assert row_of(store=world.store).tmux == TRACKED_COORDINATE
    # Both coordinates are named, so an operator reading the history can see what moved
    # where rather than only that something moved.
    assert DEAD_TMUX in log
    assert TRACKED_COORDINATE in log


def test_a_row_whose_recorded_identity_is_not_codex_is_never_rebound(*, tmp_path):
    """Only a recorded Codex identity can be matched against a resolved Codex pane."""
    _module = codex_rebind()
    claude = tmp_path / "claude"
    claude.mkdir()
    world = make_world(
        tmp_path=claude, rows=[(claude / "repo", "topic", DEAD_TMUX, "claude:4242:99:topic")]
    )

    _outcome, log = resolve(world=world, act=True)

    assert row_of(store=world.store).tmux == DEAD_TMUX
    assert TRACKED_COORDINATE not in log


def test_a_stored_herdr_coordinate_is_left_to_its_own_backend_rules(*, tmp_path):
    """This rebind answers a DEAD TMUX locator only; a herdr target has its own re-key.

    The sharp control: the live pane IS resolved to this row's recorded identity, so the
    refusal is the stored coordinate's backend and nothing else.
    """
    _module = codex_rebind()
    qualified = tmp_path / "qualified"
    qualified.mkdir()
    dead_pane = coordinate(pane_id="w9:p9")
    world = make_world(
        tmp_path=qualified,
        rows=[(qualified / "repo", "topic", dead_pane, f"codex:{SESSION_ID}")],
    )

    _outcome, log = resolve(world=world, act=True)

    assert row_of(store=world.store).tmux == dead_pane
    assert TRACKED_COORDINATE not in log


def test_a_recorded_identity_no_live_pane_resolves_to_leaves_the_coordinate_alone(*, tmp_path):
    _module = codex_rebind()
    unknown = tmp_path / "unknown"
    unknown.mkdir()
    world = make_world(
        tmp_path=unknown,
        rows=[(unknown / "repo", "topic", DEAD_TMUX, "codex:019f1111-1111-7111-8111-111111111111")],
    )

    _outcome, log = resolve(world=world, act=True)

    assert row_of(store=world.store).tmux == DEAD_TMUX
    assert "rebound" not in log


def test_a_live_pane_already_at_the_recorded_coordinate_rebinds_nothing(*, tmp_path):
    """The carrier resolves to the coordinate the row already stores: nothing moved."""
    _module = codex_rebind()
    same = tmp_path / "same"
    same.mkdir()
    world = make_world(tmp_path=same, panes={TRACKED_PANE_PID: DEAD_TMUX})

    _outcome, log = resolve(world=world, act=True)

    assert row_of(store=world.store).tmux == DEAD_TMUX
    assert "rebound" not in log


# --- assertion 3: the rebound track is supervised, not reported session-gone ---------


def test_the_rebound_track_is_supervised_as_its_live_session(*, tmp_path):
    """Rebinding the ROW is only half the fix; this tick must supervise the live pane.

    A rebind that only rewrote the store would leave the track reading `session-gone`
    for the rest of the tick that fixed it, which is the status the operator was
    complaining about in the first place.
    """
    _module = codex_rebind()
    world = make_world(tmp_path=tmp_path)

    outcome, _log = resolve(world=world, act=True)

    assert isinstance(outcome, _supervisor_evaluate_target.EvaluateTarget)
    assert outcome.pane == TRACKED_COORDINATE
    assert outcome.session == TRACKED_COORDINATE
    assert outcome.track.tmux == TRACKED_COORDINATE


def test_a_track_with_no_rebindable_pane_still_reports_session_gone(*, tmp_path):
    """The control: nothing about the refusal path changed."""
    _module = codex_rebind()
    unknown = tmp_path / "unknown"
    unknown.mkdir()
    world = make_world(
        tmp_path=unknown,
        rows=[(unknown / "repo", "topic", DEAD_TMUX, "codex:019f1111-1111-7111-8111-111111111111")],
    )

    outcome, _log = resolve(world=world, act=True)

    assert not isinstance(outcome, _supervisor_evaluate_target.EvaluateTarget)
    assert outcome.status == "session-gone"


# --- assertion 4: no pane matching the recorded identity leaves the row alone --------


def test_a_live_pane_whose_resolved_identity_differs_never_moves_the_row(*, tmp_path):
    """A same-topic pane is not evidence; the RECORDED identity is what has to match.

    This is the shape a Codex restart leaves behind: the index now names a NEW rollout
    for the same topic while the row still records the predecessor. Following that would
    bind the row to a session it never observed — and adoption's own re-point already
    handles a live INDEXED session correctly, on evidence this rebind does not have.
    """
    _module = codex_rebind()
    successor = tmp_path / "successor"
    successor.mkdir()
    world = make_world(tmp_path=successor, indexed=SUCCESSOR_SESSION_ID)

    outcome, log = resolve(world=world, act=True)

    assert world.sup.live_codex[(TRACKED_COORDINATE, "topic")].session_id == SUCCESSOR_SESSION_ID
    assert row_of(store=world.store).tmux == DEAD_TMUX
    assert "rebound" not in log
    assert not isinstance(outcome, _supervisor_evaluate_target.EvaluateTarget)


# --- assertion 5: an unidentifiable Codex pane is its own status ---------------------


def test_an_unidentifiable_codex_pane_is_reported_as_such_and_not_as_session_gone(*, tmp_path):
    """`session-gone` asserts the session is NOT THERE; here the daemon cannot tell.

    Two live sessions bound to one repository leave both unidentified, so the daemon has
    a live Codex pane it cannot name. Reporting that as `session-gone` — the only red
    status — would claim the work was lost on evidence that says nothing of the kind.
    """
    _module = codex_rebind()
    ambiguous = tmp_path / "ambiguous"
    ambiguous.mkdir()
    world = make_world(tmp_path=ambiguous)
    write_state_database(
        path=world.home / "state_2.sqlite",
        rows=[
            (SESSION_ID, "gpt-5.6-luna", str(world.repo)),
            (OPERATOR_SESSION_ID, "gpt-5.6-luna", str(world.repo)),
        ],
    )

    outcome, _log = resolve(world=world, act=True)

    assert not isinstance(outcome, _supervisor_evaluate_target.EvaluateTarget)
    assert outcome.status == "codex-unidentified"
    assert outcome.status in _supervisor_view.ATTENTION_STATUSES
    assert _supervisor_view.row_color(status=outcome.status) != _supervisor_view.row_color(
        status="session-gone"
    )
    assert row_of(store=world.store).tmux == DEAD_TMUX


# --- assertion 6: the read-only list path reports without rewriting ------------------


def test_the_read_only_list_path_reports_the_rebindable_track_without_writing(*, tmp_path):
    """`supervisor.py list` classifies; only an ACTING tick may mutate the store.

    The read-only path must still tell the truth about the track — it is the surface an
    operator reads when deciding whether to touch anything — so it resolves the live
    coordinate in memory and leaves the stored one alone.
    """
    _module = codex_rebind()
    world = make_world(tmp_path=tmp_path)

    outcome, log = resolve(world=world, act=False)

    assert isinstance(outcome, _supervisor_evaluate_target.EvaluateTarget)
    assert outcome.pane == TRACKED_COORDINATE
    assert row_of(store=world.store).tmux == DEAD_TMUX
    assert "rebound" not in log


# --- carrier_session_id: the database and home resolution ----------------------------


def test_carrier_session_id_is_none_without_an_active_state_database(*, tmp_path):
    module = codex_identity()
    empty = tmp_path / "empty-home"
    empty.mkdir()

    assert (
        module.carrier_session_id(
            pid=TRACKED_PID,
            cwd=str(tmp_path),
            candidates=frozenset({SESSION_ID}),
            codex_home=str(empty),
            environ_of=lambda *, pid: b"",
        )
        is None
    )


def test_carrier_session_id_falls_back_to_the_daemon_accounts_codex_home(*, tmp_path, monkeypatch):
    module = codex_identity()
    account = tmp_path / "account-home"
    (account / ".codex").mkdir(parents=True)
    write_state_database(
        path=account / ".codex" / "state_1.sqlite",
        rows=[(SESSION_ID, "gpt-5.6-luna", str(tmp_path))],
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: account))

    assert (
        module.carrier_session_id(
            pid=TRACKED_PID,
            cwd=str(tmp_path),
            candidates=frozenset({SESSION_ID}),
            codex_home=None,
            environ_of=lambda *, pid: b"",
        )
        == SESSION_ID
    )


# --- read_state_database_repository: the repository-binding predicate ----------------


def test_the_repository_predicate_accepts_only_an_exact_row_naming_that_repository(*, tmp_path):
    crm = codex_runtime_model()
    database = tmp_path / "state_1.sqlite"
    write_state_database(
        path=database,
        rows=[
            (SESSION_ID, "gpt-5.6-luna", str(tmp_path)),
            (OPERATOR_SESSION_ID, None, str(tmp_path / "elsewhere")),
            ("no-cwd", "gpt-5.6-luna", None),
        ],
    )

    def bound(*, session_id, cwd=str(tmp_path), path=database):
        return crm.read_state_database_repository(database=path, session_id=session_id, cwd=cwd)

    # A row with NO recorded model token still identifies its session: gating identity
    # on a model would make a session unidentifiable for an unrelated reason.
    assert bound(session_id=SESSION_ID) is True
    assert bound(session_id=OPERATOR_SESSION_ID, cwd=str(tmp_path / "elsewhere")) is True
    assert bound(session_id=OPERATOR_SESSION_ID) is False
    assert bound(session_id="no-cwd") is False
    assert bound(session_id="no-such-thread") is False


def test_the_repository_predicate_fails_closed_for_every_database_defect(*, tmp_path):
    crm = codex_runtime_model()
    corrupt = tmp_path / "corrupt.sqlite"
    corrupt.write_bytes(b"definitely not a sqlite file")
    no_cwd_column = tmp_path / "no-cwd-column.sqlite"
    write_state_database(
        path=no_cwd_column,
        schema=_SCHEMA_WITHOUT_CWD,
        insert=_INSERT_WITHOUT_CWD,
        rows=[(SESSION_ID, "gpt-5.6-luna")],
    )

    def bound(*, path):
        return crm.read_state_database_repository(
            database=path, session_id=SESSION_ID, cwd=str(tmp_path)
        )

    assert bound(path=tmp_path / "absent.sqlite") is False
    assert bound(path=corrupt) is False
    assert bound(path=no_cwd_column) is False


def test_the_repository_predicate_fails_closed_on_a_locked_database(*, tmp_path):
    crm = codex_runtime_model()
    database = tmp_path / "state_1.sqlite"
    write_state_database(path=database, rows=[(SESSION_ID, "gpt-5.6-luna", str(tmp_path))])
    holder = sqlite3.connect(database)
    holder.isolation_level = None
    _ = holder.execute("BEGIN EXCLUSIVE")
    try:
        assert (
            crm.read_state_database_repository(
                database=database, session_id=SESSION_ID, cwd=str(tmp_path)
            )
            is False
        )
    finally:
        _ = holder.execute("ROLLBACK")
        holder.close()
