"""A live track resumed under a RESTARTED herdr server is re-adopted (overseer-rwrkkr).

Measured on daemon 5.32.0, 2026-10-19: the host was powered off at 10:49Z and herdr
came back as a new server process on the SAME socket, resuming each pane's agent.
Every mapped row still named the dead server generation, and adoption re-points a
herdr row only within its own instance (overseer-bce3), so 23 live tracks read
`session-gone` until their rows were unassigned by hand.

A restart is not a namesake. The re-point is allowed only when the recorded generation
is PROVABLY gone (its server pid no longer runs with the recorded start time) and the
same socket now answers with the live session's generation; the live named session must
claim the topic uniquely, and an unfinished daemon replacement keeps priority. The row
then records the NEW generation, never the former one.
"""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import _herdr_replacement_store
import _supervisor_discovery_adoption
import herdr_identity
import pytest
import registry
import supervisor

__all__: list[str] = []

_PREDECESSOR = "claude:709305:875535464:topic"
_RESUMED = "claude:952011:574120000:topic"
_SOCKET = "/home/ubuntu/.config/herdr/herdr.sock"


def _coordinate(*, pane_id: str, pid: int, socket_path: str = _SOCKET) -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=socket_path,
            server_pid=pid,
            server_starttime=f"start-{pid}",
            pane_id=pane_id,
        )
    )


_RECORDED = _coordinate(pane_id="w5:p5", pid=3384132)
_RESTARTED = _coordinate(pane_id="w5:p5", pid=169821)


def _mapped(*, tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    (repo / "plan" / "topic").mkdir(parents=True)
    store = tmp_path / "mapping.jsonl"
    registry.append_mapping(
        track=registry.PlanTrack(
            topic="topic",
            repo=str(repo),
            tmux=_RECORDED,
            epic="topic",
            observed_session_identity=_PREDECESSOR,
        ),
        store_path=store,
    )
    return repo, store


def _row(*, store: Path) -> registry.Track:
    return registry.read_valid_mapping(store_path=store)[0]


def _adopt(
    *,
    tmp_path: Path,
    monkeypatch: Any,
    live: list[str],
    running: dict[int, str],
    open_replacement: bool = False,
) -> registry.Track:
    repo, store = _mapped(tmp_path=tmp_path)
    if open_replacement:
        _herdr_replacement_store.durable_write(
            path=_herdr_replacement_store.scratch_path(track=_row(store=store))
            / _herdr_replacement_store.RECORD_NAME,
            value={"version": 1, "phase": "resume-attempted", "target": _RECORDED},
        )
    sup = supervisor.Supervisor(
        tmux=SimpleNamespace(pane_pid_sessions=dict, capture_pane=lambda **_kwargs: ""),
        store_path=store,
        stamp_path=tmp_path / "stamps.json",
        out=io.StringIO(),
        require_render_terminal=False,
        now=lambda: 1000.0,
        sleep=lambda _seconds: None,
        codex_home=tmp_path / "no-codex",
        codex_pids_of_comm=lambda *, comm: [],
        runtime_model_of=lambda *, pid: None,
    )
    sup.starttime_of = lambda *, pid: running.get(pid)
    sup.claude_identity_by_session = {(session, "topic"): _RESUMED for session in live}
    monkeypatch.setattr(
        _supervisor_discovery_adoption,
        "_adoptable_live_sessions",
        lambda *, sup, pane_pids: [(session, "topic", str(repo)) for session in live],
    )
    monkeypatch.setattr(
        _supervisor_discovery_adoption, "_live_profile_sources", lambda *, sup, pane_pids: {}
    )
    assert _supervisor_discovery_adoption.adopt_sessions(sup=sup, watch=[str(repo)]) == []
    return _row(store=store)


def test_a_track_resumed_under_a_restarted_herdr_server_is_readopted_with_its_identity(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = _adopt(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        live=[_RESTARTED],
        running={169821: "start-169821"},
    )

    assert (row.tmux, row.observed_session_identity) == (_RESTARTED, _RESUMED)


def test_the_readopted_row_carries_only_the_live_server_generation(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = _adopt(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        live=[_RESTARTED],
        running={3384132: "start-of-a-reused-pid", 169821: "start-169821"},
    )

    target = herdr_identity.decode_target(value=row.tmux or "").herdr
    assert target is not None
    assert (target.server_pid, target.server_starttime) == (169821, "start-169821")


@pytest.mark.parametrize(
    ("case", "live", "running", "open_replacement"),
    [
        (
            "recorded-generation-still-running",
            [_RESTARTED],
            {3384132: "start-3384132", 169821: "start-169821"},
            False,
        ),
        (
            "namesake-on-another-socket",
            [_coordinate(pane_id="w5:p5", pid=169821, socket_path="/run/other.sock")],
            {169821: "start-169821"},
            False,
        ),
        (
            "two-live-sessions-claim-the-topic",
            [_RESTARTED, _coordinate(pane_id="w6:p2", pid=169821)],
            {169821: "start-169821"},
            False,
        ),
        ("unfinished-daemon-replacement", [_RESTARTED], {169821: "start-169821"}, True),
    ],
)
def test_an_unproven_restart_leaves_the_row_untouched(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    live: list[str],
    running: dict[int, str],
    open_replacement: bool,
) -> None:
    row = _adopt(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        live=live,
        running=running,
        open_replacement=open_replacement,
    )

    assert (case, row.tmux, row.observed_session_identity) == (case, _RECORDED, _PREDECESSOR)
