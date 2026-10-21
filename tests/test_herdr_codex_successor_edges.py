"""Exact process, rollout, naming, and continuation controls for Codex successors."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import _herdr_replacement_store
import _supervisor_herdr_codex_naming
import _supervisor_herdr_codex_successor
import pytest
from _codex_session_models import CodexSession
from test_supervisor_builders import (
    FakeTmux,
    codex_idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)

OLD = "019f548d-0000-7000-8000-000000000001"
NEW = "019f548d-0000-7000-8000-000000000002"


def _process(*, pid: int, starttime: str, pgrp: int):
    return SimpleNamespace(
        pid=pid,
        starttime=starttime,
        executable="/usr/bin/codex",
        argv=("codex",),
        process_group=pgrp,
        session_id=90,
    )


def _snapshot(*, runtime_pid: int = 301):
    shell = SimpleNamespace(
        pid=100,
        starttime="shell-start",
        executable="/bin/bash",
        argv=("/bin/bash",),
        process_group=100,
        session_id=90,
    )
    leader = _process(pid=300, starttime="leader-new", pgrp=300)
    runtime = _process(pid=runtime_pid, starttime="runtime-new", pgrp=300)
    return SimpleNamespace(shell=shell, foreground_group=300, processes=(shell, leader, runtime))


def _transaction(*, target: str, repo: Path, phase: str) -> dict[str, object]:
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
        "runtime": "codex",
        "predecessor": {"pid": 201, "starttime": "runtime-old", "process_group": 200},
        "predecessor_rollout": OLD,
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
            "session_identity": "codex:201:runtime-old:topic",
        },
        "launch": {"command": "codex", "cwd": str(repo), "env": {}},
        "resume": "read the durable handoff",
    }


def _world(*, tmp_path, phase="launch-attempted"):
    repo, topic = make_plan(tmp_path=tmp_path)
    target = "pane"
    fake = FakeTmux()
    fake.serve(session=target, repo=repo, capture=codex_idle_capture(ctx=100), cmd="codex")
    fake.herdr_replacement_snapshot = lambda *, session: _snapshot()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.live_codex[(target, topic)] = CodexSession(
        pid=301, name=topic, cwd=str(repo), session_id=NEW
    )
    sup.starttime_of = lambda *, pid: "runtime-new" if pid == 301 else None
    sup.refresh_codex_sessions = lambda: None
    track = mapped_track(repo=repo, topic=topic, session=target)
    transaction = _transaction(target=target, repo=repo, phase=phase)
    path = _herdr_replacement_store.scratch_path(track=track) / _herdr_replacement_store.RECORD_NAME
    _herdr_replacement_store.durable_write(path=path, value=transaction)
    return sup, fake, track, target, transaction, path


def test_codex_successor_is_named_resumed_and_completed_once(*, tmp_path, monkeypatch) -> None:
    sup, fake, track, target, transaction, path = _world(tmp_path=tmp_path)
    prompts = []
    monkeypatch.setattr(
        _supervisor_herdr_codex_naming.codex_sessions,
        "latest_session_for_thread_name",
        lambda **kwargs: NEW,
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_launch,
        "submit_prompt",
        lambda **kwargs: prompts.append(kwargs["text"]) or True,
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_herdr_completion,
        "complete_replacement_round",
        lambda **kwargs: None,
    )

    reason = _supervisor_herdr_codex_successor.continue_codex_successor(
        sup=sup, track=track, target=target, transaction=transaction
    )

    assert reason is None
    # The no-turn rename is delivered WITHOUT the held-attempt submitter, so only the
    # resume line reaches `submit_prompt`; the rename shows up as the pane paste it is.
    assert prompts == ["read the durable handoff"]
    assert fake.paste_texts() == [f"/rename {track.topic}"]
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["phase"] == "completed"
    assert record["successor_rollout"] == NEW
    assert record["successor"]["pid"] == 301


@pytest.mark.parametrize("hazard", ["missing", "same-rollout", "invalid-rollout", "wrong-cwd"])
def test_codex_successor_refuses_wrong_live_rollout(*, tmp_path, hazard: str) -> None:
    sup, _fake, track, target, transaction, _path = _world(tmp_path=tmp_path)
    if hazard == "missing":
        sup.live_codex.clear()
    else:
        live = sup.live_codex[(target, track.topic)]
        sup.live_codex[(target, track.topic)] = CodexSession(
            pid=live.pid,
            name=live.name,
            cwd="/foreign" if hazard == "wrong-cwd" else live.cwd,
            session_id={"same-rollout": OLD, "invalid-rollout": "bad"}.get(hazard, NEW),
        )

    reason = _supervisor_herdr_codex_successor.continue_codex_successor(
        sup=sup, track=track, target=target, transaction=transaction
    )

    assert reason == "fresh Codex rollout is not yet observable in the original pane"


@pytest.mark.parametrize("hazard", ["starttime", "process-proof", "recorded-process"])
def test_codex_successor_refuses_unproven_process_generation(*, tmp_path, hazard: str) -> None:
    sup, fake, track, target, transaction, path = _world(tmp_path=tmp_path)
    if hazard == "starttime":
        sup.starttime_of = lambda *, pid: None
    elif hazard == "process-proof":
        fake.herdr_replacement_snapshot = lambda *, session: _snapshot(runtime_pid=302)
    else:
        transaction["successor"] = {"pid": 999}
        _herdr_replacement_store.durable_write(path=path, value=transaction)

    reason = _supervisor_herdr_codex_successor.continue_codex_successor(
        sup=sup, track=track, target=target, transaction=transaction
    )

    expected = {
        "starttime": "fresh Codex process generation is not readable",
        "process-proof": "Codex successor is not a fresh process in the retained shell",
        "recorded-process": "Codex successor no longer matches its durable process generation",
    }
    assert reason == expected[hazard]


def test_codex_successor_refuses_changed_transaction(*, tmp_path) -> None:
    sup, _fake, track, target, transaction, path = _world(tmp_path=tmp_path)
    changed = dict(transaction)
    changed["phase"] = "completed"
    _herdr_replacement_store.durable_write(path=path, value=changed)

    reason = _supervisor_herdr_codex_successor.continue_codex_successor(
        sup=sup, track=track, target=target, transaction=transaction
    )

    assert reason == "durable replacement changed during Codex successor verification"


@pytest.mark.parametrize("phase", ["successor-observed", "completed"])
def test_codex_successor_reentry_never_repeats_naming(*, tmp_path, monkeypatch, phase: str) -> None:
    sup, _fake, track, target, transaction, _path = _world(tmp_path=tmp_path, phase=phase)
    prompts = []
    completed = []
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_launch,
        "submit_prompt",
        lambda **kwargs: prompts.append(kwargs["text"]) or True,
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_herdr_completion,
        "complete_replacement_round",
        lambda **kwargs: completed.append(kwargs) or None,
    )

    reason = _supervisor_herdr_codex_successor.continue_codex_successor(
        sup=sup, track=track, target=target, transaction=transaction
    )

    assert "/rename topic" not in prompts
    if phase == "successor-observed":
        assert reason is None
        assert prompts == ["read the durable handoff"]
        assert len(completed) == 1
    else:
        assert reason is None
        assert prompts == []
        assert len(completed) == 1


def test_codex_successor_rename_refusal_skips_completion(*, tmp_path, monkeypatch) -> None:
    sup, fake, track, target, transaction, _path = _world(tmp_path=tmp_path)
    fake.panes[target] = "› 1. Yes, continue\n  2. No"
    completed = []
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_herdr_completion,
        "complete_replacement_round",
        lambda **kwargs: completed.append(kwargs),
    )

    reason = _supervisor_herdr_codex_successor.continue_codex_successor(
        sup=sup, track=track, target=target, transaction=transaction
    )

    assert reason == "fresh Codex successor is waiting at a structured gate"
    assert completed == []
