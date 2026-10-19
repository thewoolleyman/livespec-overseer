"""A herdr session relaunched by hand in another pane is re-adopted (overseer-bce3).

Measured on daemon 5.31.1: gitops-fleet-capacity-monitoring was relaunched by hand
into a new pane of the SAME herdr instance, and its row then read `session-gone` for
about 2.5 days. Three gates each refused it on their own: adoption re-pointed only
legacy tmux rows, the recorded-identity gate still named the predecessor, and a
completed replacement record for the old pane stalled the track.
"""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import _herdr_replacement_store
import _supervisor_discovery_adoption
import _supervisor_evaluate_target
import _supervisor_herdr_recovery
import herdr_identity
import pytest
import registry
import supervisor

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = []

_PREDECESSOR = "claude:3368048:853366328:topic"
_MOVED = "claude:124578:853708136:topic"


def _coordinate(*, pane_id: str, socket_path: str = "/run/herdr.sock", pid: int = 401) -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=socket_path,
            server_pid=pid,
            server_starttime=f"start-{pid}",
            pane_id=pane_id,
        )
    )


def _transaction(*, target: str, phase: str) -> dict[str, object]:
    """A well-formed durable replacement record (the shape `read_transaction` accepts)."""
    return {
        "version": 1,
        "phase": phase,
        "target": target,
        "server": {"socket_path": "/run/herdr.sock", "pid": 401, "starttime": "s", "pane_id": "w"},
        "runtime": "claude",
        "predecessor": {"pid": 201, "starttime": "runtime-old", "process_group": 200},
        "shell": {
            "pid": 100,
            "starttime": "shell-start",
            "executable": "/bin/bash",
            "argv": ["/bin/bash"],
            "process_group": 100,
            "session_id": 90,
        },
        "round": {"ready_mtime": 1001.0, "round_at": 1000.0, "session_identity": _PREDECESSOR},
        "launch": {"command": "claude -n topic", "cwd": "/repo", "env": {}},
    }


def _mapped(*, tmp_path: Path, target: str) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    (repo / "plan" / "topic").mkdir(parents=True)
    store = tmp_path / "mapping.jsonl"
    registry.append_mapping(
        track=registry.PlanTrack(
            topic="topic",
            repo=str(repo),
            tmux=target,
            epic="topic",
            observed_session_identity=_PREDECESSOR,
        ),
        store_path=store,
    )
    return repo, store


def _row(*, store: Path) -> registry.Track:
    return registry.read_valid_mapping(store_path=store)[0]


def _adopt(*, tmp_path: Path, monkeypatch: Any, live: str) -> registry.Track:
    repo, _store = _mapped(tmp_path=tmp_path, target=_coordinate(pane_id="w2J:p5"))
    sup = supervisor.Supervisor(
        tmux=SimpleNamespace(pane_pid_sessions=dict, capture_pane=lambda **_kwargs: ""),
        store_path=tmp_path / "mapping.jsonl",
        stamp_path=tmp_path / "stamps.json",
        out=io.StringIO(),
        require_render_terminal=False,
        now=lambda: 1000.0,
        sleep=lambda _seconds: None,
        codex_home=tmp_path / "no-codex",
        codex_pids_of_comm=lambda *, comm: [],
        runtime_model_of=lambda *, pid: None,
    )
    sup.claude_identity_by_session = {(live, "topic"): _MOVED}
    monkeypatch.setattr(
        _supervisor_discovery_adoption,
        "_adoptable_live_sessions",
        lambda *, sup, pane_pids: [(live, "topic", str(repo))],
    )
    monkeypatch.setattr(
        _supervisor_discovery_adoption, "_live_profile_sources", lambda *, sup, pane_pids: {}
    )
    assert _supervisor_discovery_adoption.adopt_sessions(sup=sup, watch=[str(repo)]) == []
    return _row(store=sup.store_path)


def test_a_session_moved_within_its_herdr_instance_is_repointed_with_its_identity(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    moved = _coordinate(pane_id="w2J:pA")

    row = _adopt(tmp_path=tmp_path, monkeypatch=monkeypatch, live=moved)

    assert (row.tmux, row.observed_session_identity) == (moved, _MOVED)


def test_a_namesake_on_another_herdr_instance_is_still_never_adopted(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    namesake = _coordinate(pane_id="w2J:pA", socket_path="/run/other.sock", pid=402)

    row = _adopt(tmp_path=tmp_path, monkeypatch=monkeypatch, live=namesake)

    assert (row.tmux, row.observed_session_identity) == (
        _coordinate(pane_id="w2J:p5"),
        _PREDECESSOR,
    )


def _evaluation_sup(
    *, store: Path, session: str, names: set[str], located: str | None = None
) -> SimpleNamespace:
    """`located` is where the re-key scan finds the relaunched process (default: here)."""

    def scan(*, session: str, observed_session_identity: str | None, **_kwargs: Any) -> Any:
        return (located or session) if observed_session_identity == _MOVED else None

    return SimpleNamespace(
        tmux=SimpleNamespace(renumbered_herdr_coordinate=scan),
        claude_identity_by_session={(session, "topic"): _MOVED},
        claude_names_by_session={session: names},
        store_path=store,
        starttime_of=lambda **_kwargs: None,
        log=lambda **_kwargs: None,
    )


def _resolve(*, sup: SimpleNamespace, store: Path, act: bool) -> tuple[Any, ...]:
    return _supervisor_evaluate_target._resolve_herdr_target(
        sup=cast("Supervisor", sup),
        track=_row(store=store),
        session=_row(store=store).tmux or "",
        act=act,
    )


@pytest.mark.parametrize("act", [True, False])
def test_a_hand_relaunch_in_the_recorded_pane_replaces_the_recorded_identity(
    *, tmp_path: Path, act: bool
) -> None:
    session = _coordinate(pane_id="w2J:p5")
    _repo, store = _mapped(tmp_path=tmp_path, target=session)
    sup = _evaluation_sup(store=store, session=session, names={"topic"})

    track, resolved, target, refuses = _resolve(sup=sup, store=store, act=act)

    assert (resolved, target, refuses) == (session, session, False)
    assert track.observed_session_identity == _MOVED
    # Only an acting tick writes; the read-only `list` path classifies without mutating.
    assert _row(store=store).observed_session_identity == (_MOVED if act else _PREDECESSOR)


@pytest.mark.parametrize(
    "case", ["unnamed", "open-replacement", "unreadable-record", "foreign-process"]
)
def test_the_recorded_identity_still_refuses_an_unproven_pane(*, tmp_path: Path, case: str) -> None:
    session = _coordinate(pane_id="w2J:p5")
    _repo, store = _mapped(tmp_path=tmp_path, target=session)
    names = {"other"} if case == "unnamed" else {"topic"}
    if case == "open-replacement":
        _herdr_replacement_store.durable_write(
            path=_herdr_replacement_store.scratch_path(track=_row(store=store))
            / _herdr_replacement_store.RECORD_NAME,
            value=_transaction(target=session, phase="launch-attempted"),
        )
    if case == "unreadable-record":
        record = _herdr_replacement_store.scratch_path(track=_row(store=store))
        record.mkdir(parents=True)
        (record / _herdr_replacement_store.RECORD_NAME).write_text("{", encoding="utf-8")
    located = _coordinate(pane_id="w5:p6") if case == "foreign-process" else None
    sup = _evaluation_sup(store=store, session=session, names=names, located=located)

    _track, _resolved, target, refuses = _resolve(sup=sup, store=store, act=True)

    assert (target, refuses) == (None, True)
    assert _row(store=store).observed_session_identity == _PREDECESSOR


@pytest.mark.parametrize(("phase", "gates"), [("completed", False), ("launch-attempted", True)])
def test_only_an_unfinished_replacement_for_another_pane_gates_the_track(
    *, tmp_path: Path, phase: str, gates: bool
) -> None:
    track = registry.Track(repo=str(tmp_path), topic="topic", tmux=_coordinate(pane_id="w2J:pA"))
    _herdr_replacement_store.durable_write(
        path=_herdr_replacement_store.scratch_path(track=track)
        / _herdr_replacement_store.RECORD_NAME,
        value=_transaction(target=_coordinate(pane_id="w2J:p5"), phase=phase),
    )

    row = _supervisor_herdr_recovery.reconcile_bare_shell(
        sup=cast("Supervisor", SimpleNamespace()),
        track=track,
        target=_coordinate(pane_id="w2J:pA"),
        act=True,
    )

    assert (row is not None and row.status == "replacement-failed") is gates
