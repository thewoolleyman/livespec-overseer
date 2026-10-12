"""Green-only coverage for accepted Herdr review refusal branches."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import _herdr_replacement_authorization
import _herdr_replacement_process
import _herdr_replacement_store
import _supervisor_herdr_recovery
import _supervisor_herdr_signal_recovery
import herdr_identity
import herdr_replacement_process
import pytest
import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

_DELETE = object()


def _target(*, tmp_path: Path) -> str:
    return herdr_identity.encode_herdr_target(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=str(tmp_path / "herdr.sock"),
            server_pid=700,
            server_starttime="server-start",
            pane_id="w1:p9",
        )
    )


def _transaction(*, target: str, phase: str = "signal-attempted") -> dict[str, object]:
    return {
        "version": 1,
        "phase": phase,
        "target": target,
        "server": {
            "socket_path": "/tmp/herdr.sock",
            "pid": 700,
            "starttime": "server-start",
            "pane_id": "w1:p9",
        },
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
        "round": {
            "ready_mtime": 1001.0,
            "round_at": 1000.0,
            "session_identity": "claude:201:runtime-old:topic",
        },
        "launch": {
            "command": "claude --dangerously-skip-permissions -n topic",
            "cwd": "/repo",
            "env": {"ANTHROPIC_MODEL": None},
        },
    }


def _mutate(
    *, record: dict[str, object], path: tuple[str, ...], value: object
) -> dict[str, object]:
    changed = deepcopy(record)
    parent = changed
    for key in path[:-1]:
        parent = cast(dict[str, object], parent[key])
    if value is _DELETE:
        del parent[path[-1]]
    else:
        parent[path[-1]] = value
    return changed


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("version",), 2),
        (("version",), True),
        (("phase",), "unknown"),
        (("target",), ""),
        (("runtime",), "other"),
        (("server",), []),
        (("server", "pane_id"), _DELETE),
        (("server", "socket_path"), ""),
        (("server", "pid"), 0),
        (("server", "pid"), True),
        (("server", "starttime"), ""),
        (("server", "pane_id"), ""),
        (("predecessor", "pid"), _DELETE),
        (("predecessor", "pid"), 0),
        (("predecessor", "process_group"), 0),
        (("predecessor", "starttime"), ""),
        (("shell", "executable"), ""),
        (("shell", "argv"), "not-a-list"),
        (("shell", "argv"), []),
        (("shell", "argv"), [1]),
        (("shell", "session_id"), 0),
        (("round",), []),
        (("round", "session_identity"), _DELETE),
        (("round", "ready_mtime"), True),
        (("round", "round_at"), "not-a-number"),
        (("round", "session_identity"), ""),
        (("launch",), []),
        (("launch", "env"), _DELETE),
        (("launch", "command"), ""),
        (("launch", "cwd"), ""),
        (("launch", "env"), []),
        (("launch", "env"), {"NAME": 1}),
    ],
)
def test_each_malformed_transaction_shape_is_refused(
    *, tmp_path: Path, path: tuple[str, ...], value: object
) -> None:
    record = _mutate(record=_transaction(target=_target(tmp_path=tmp_path)), path=path, value=value)
    record_path = tmp_path / "transaction.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises((TypeError, ValueError), match="malformed durable Herdr"):
        _herdr_replacement_store.read_transaction(path=record_path)


def test_malformed_round_shape_cannot_reach_final_authorization(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    track = registry.Track(repo=str(tmp_path), topic="topic", tmux="session")
    sup = SimpleNamespace(stamp_path=tmp_path / "stamp")
    monkeypatch.setattr(
        signals,
        "read_state",
        lambda **_kwargs: SimpleNamespace(token=signals.STATE_READY, mtime=1001.0),
    )
    monkeypatch.setattr(
        registry,
        "read_round_record",
        lambda **_kwargs: SimpleNamespace(
            malformed_reason=None,
            at=1000.0,
            session_identity="claude:201:runtime-old:topic",
        ),
    )

    assert not _herdr_replacement_authorization.round_still_authorizes(
        sup=cast("Supervisor", sup),
        track=track,
        transaction={"round": []},
    )


@pytest.mark.parametrize("act", [False, True])
def test_signal_attempt_observation_failures_remain_diagnostic(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, act: bool
) -> None:
    target = _target(tmp_path=tmp_path)
    track = registry.Track(repo=str(tmp_path), topic="topic", tmux=target)
    transaction = _transaction(target=target)
    scratch = _herdr_replacement_store.scratch_path(track=track)
    _herdr_replacement_store.durable_write(
        path=scratch / _herdr_replacement_store.RECORD_NAME,
        value=transaction,
    )
    tmux = SimpleNamespace(
        herdr_replacement_snapshot=lambda **_kwargs: (_ for _ in ()).throw(
            ValueError("observation failed")
        )
    )
    sup = SimpleNamespace(tmux=tmux, stamp_path=tmp_path / "stamp")
    monkeypatch.setattr(herdr_replacement_process, "proc_starttime", lambda **_kwargs: None)

    row = _supervisor_herdr_recovery.reconcile_bare_shell(
        sup=cast("Supervisor", sup),
        track=track,
        target=target,
        act=act,
    )

    assert row is not None and row.status == "replacement-failed"
    assert "observation failed" in row.note


@pytest.mark.parametrize(
    ("case", "phase"),
    [("missing", "signal-attempted"), ("changed", "signal-attempted"), ("phase", "before-stop")],
)
def test_signal_recovery_refuses_a_changed_durable_record(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    phase: str,
) -> None:
    target = _target(tmp_path=tmp_path)
    transaction = _transaction(target=target, phase=phase)
    current = deepcopy(transaction)
    if case == "missing":
        current = None
    elif case == "changed":
        current["target"] = "changed"
    monkeypatch.setattr(_herdr_replacement_store, "read_transaction", lambda **_kwargs: current)
    track = registry.Track(repo=str(tmp_path), topic="topic", tmux=target)

    recovered, reason = _supervisor_herdr_signal_recovery.recover_signal_attempt(
        sup=cast("Supervisor", SimpleNamespace(tmux=SimpleNamespace())),
        track=track,
        target=target,
        transaction=transaction,
    )

    assert recovered is None
    assert reason == "durable replacement changed while proving predecessor exit"


@pytest.mark.parametrize(
    ("observed_starttime", "expected"),
    [("runtime-old", "replacement-failed"), (None, "replacement-pending")],
)
def test_read_only_signal_recovery_reports_process_evidence(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    observed_starttime: str | None,
    expected: str,
) -> None:
    target = _target(tmp_path=tmp_path)
    track = registry.Track(repo=str(tmp_path), topic="topic", tmux=target)
    transaction = _transaction(target=target)
    scratch = _herdr_replacement_store.scratch_path(track=track)
    _herdr_replacement_store.durable_write(
        path=scratch / _herdr_replacement_store.RECORD_NAME,
        value=transaction,
    )
    sup = SimpleNamespace(
        tmux=SimpleNamespace(
            herdr_replacement_snapshot=lambda **_kwargs: SimpleNamespace(processes=())
        ),
        stamp_path=tmp_path / "stamp",
    )
    monkeypatch.setattr(
        herdr_replacement_process,
        "proc_starttime",
        lambda **_kwargs: observed_starttime,
    )

    row = _supervisor_herdr_recovery.reconcile_bare_shell(
        sup=cast("Supervisor", sup),
        track=track,
        target=target,
        act=False,
    )

    assert row is not None and row.status == expected


def test_signal_recovery_uses_the_live_snapshot_when_proc_reports_absence(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transaction = _transaction(target=_target(tmp_path=tmp_path))
    monkeypatch.setattr(herdr_replacement_process, "proc_starttime", lambda **_kwargs: None)
    snapshot = SimpleNamespace(processes=(SimpleNamespace(pid=201, starttime="runtime-old"),))

    reason = _supervisor_herdr_signal_recovery.signal_attempt_refusal(
        transaction=transaction,
        snapshot=cast("_herdr_replacement_process.ReplacementSnapshot", snapshot),
    )

    assert reason == "predecessor survived the one termination attempt"
