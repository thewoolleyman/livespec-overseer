"""Exact process, rollout, naming, and continuation controls for Codex successors."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import _herdr_replacement_store
import _supervisor_herdr_codex_naming
import _supervisor_herdr_codex_successor
import herdr_identity
import herdr_write
import pane_router
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


def test_index_named_successor_without_rollout_is_reported_and_resumed(
    *, tmp_path, monkeypatch
) -> None:
    """A managed carrier has process proof and an indexed thread, not a rollout fd."""
    sup, _fake, track, target, transaction, path = _world(tmp_path=tmp_path)
    sup.live_codex.clear()
    reports: list[dict[str, object]] = []
    resumes: list[str] = []
    sup.tmux.report_agent_session = lambda **kwargs: reports.append(kwargs) or SimpleNamespace(
        ok=True, error=""
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_naming.codex_sessions,
        "latest_session_for_thread_name",
        lambda **kwargs: NEW,
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_launch,
        "submit_prompt",
        lambda **kwargs: resumes.append(kwargs["text"]) or True,
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
    assert reports == [{"session": target, "agent_session_id": NEW, "source": "overseerd"}]
    assert resumes == ["read the durable handoff"]
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["successor_thread"] == NEW


def test_unconfirmed_rename_leaves_the_managed_successor_unreported(
    *, tmp_path, monkeypatch
) -> None:
    """No new index thread means no backend identity claim or resume submission."""
    sup, _fake, track, target, transaction, path = _world(tmp_path=tmp_path)
    sup.live_codex.clear()
    reports: list[dict[str, object]] = []
    sup.tmux.report_agent_session = lambda **kwargs: reports.append(kwargs) or SimpleNamespace(
        ok=True, error=""
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_naming.codex_sessions,
        "latest_session_for_thread_name",
        lambda **kwargs: OLD,
    )

    reason = _supervisor_herdr_codex_successor.continue_codex_successor(
        sup=sup, track=track, target=target, transaction=transaction
    )

    assert reason == "fresh Codex successor was never named for this plan topic"
    assert reports == []
    record = json.loads(path.read_text(encoding="utf-8"))
    assert "successor_thread" not in record


def test_named_thread_rejects_the_predecessor_rollout(*, tmp_path, monkeypatch) -> None:
    """The index must not let the predecessor masquerade as the renamed successor."""
    sup, _fake, track, _target, _transaction_value, _path = _world(tmp_path=tmp_path)
    monkeypatch.setattr(
        _supervisor_herdr_codex_naming.codex_sessions,
        "latest_session_for_thread_name",
        lambda **kwargs: OLD,
    )

    assert (
        _supervisor_herdr_codex_naming.named_thread(sup=sup, track=track, predecessor=OLD) is None
    )


def test_managed_successor_requires_a_unique_codex_carrier(*, tmp_path) -> None:
    """A backend report is allowed only after process proof identifies one carrier."""
    sup, fake, track, target, transaction, _path = _world(tmp_path=tmp_path)
    sup.live_codex.clear()
    sup.tmux.report_agent_session = lambda **_kwargs: SimpleNamespace(ok=True, error="")

    def two_carriers(*, session: str):
        snapshot = _snapshot()
        return SimpleNamespace(
            shell=snapshot.shell,
            foreground_group=snapshot.foreground_group,
            processes=(*snapshot.processes, _process(pid=302, starttime="runtime-other", pgrp=300)),
        )

    fake.herdr_replacement_snapshot = two_carriers

    reason = _supervisor_herdr_codex_successor.continue_codex_successor(
        sup=sup, track=track, target=target, transaction=transaction
    )

    assert reason == "fresh Codex successor is not uniquely observable in the retained shell"


def test_no_turn_rename_uses_the_stateless_enter_fallback(*, tmp_path, monkeypatch) -> None:
    """The naming proof also supports a pane without Herdr's exact-payload retry."""
    sup, fake, track, target, _transaction_value, _path = _world(tmp_path=tmp_path)
    sent: list[dict[str, object]] = []
    fake.retry_prompt_enter_once = None
    fake.send_keys = lambda **kwargs: sent.append(kwargs) or True
    monkeypatch.setattr(
        _supervisor_herdr_codex_naming.codex_sessions,
        "latest_session_for_thread_name",
        lambda **kwargs: NEW,
    )

    named = _supervisor_herdr_codex_naming.name_fresh_successor(
        sup=sup,
        track=track,
        target=target,
        text=f"/rename {track.topic}",
        rollout=NEW,
        predecessor=OLD,
    )

    assert named
    assert sent == [{"session": target, "keys": "Enter"}]


def test_rejected_codex_agent_session_report_keeps_the_successor_proven(
    *, tmp_path, monkeypatch
) -> None:
    """A backend refusal is surfaced but cannot prevent delivery of the resume line."""
    sup, _fake, track, target, transaction, path = _world(tmp_path=tmp_path)
    sup.live_codex.clear()
    alerts: list[dict[str, object]] = []
    resumes: list[str] = []
    sup.tmux.report_agent_session = lambda **_kwargs: SimpleNamespace(
        ok=False, error="rejected by herdr"
    )
    sup.alert = lambda **kwargs: alerts.append(kwargs)
    monkeypatch.setattr(
        _supervisor_herdr_codex_naming.codex_sessions,
        "latest_session_for_thread_name",
        lambda **kwargs: NEW,
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_launch,
        "submit_prompt",
        lambda **kwargs: resumes.append(kwargs["text"]) or True,
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
    assert resumes == ["read the durable handoff"]
    assert alerts[0]["condition"] == "herdr-agent-session-report-rejected"
    assert json.loads(path.read_text(encoding="utf-8"))["backend_report"] == {
        "thread": NEW,
        "accepted": False,
    }


def test_writer_reports_a_codex_thread_to_the_exact_recorded_pane(*, monkeypatch) -> None:
    """The report uses the replacement's qualified pane, not any process environment."""
    written: list[dict[str, object]] = []
    writer = herdr_write.HerdrWriter()
    target = SimpleNamespace(pane_id="w1:p9")
    outcome = SimpleNamespace(ok=True, error="")
    monkeypatch.setattr(
        herdr_write.HerdrWriter,
        "_write",
        lambda _self, **kwargs: written.append(kwargs) or outcome,
    )

    actual = writer.report_agent_session(
        target=target,
        source="overseerd",
        agent_session_id=NEW,
    )

    assert actual is outcome
    assert written == [
        {
            "target": target,
            "params": {
                "pane_id": "w1:p9",
                "source": "overseerd",
                "agent": "codex",
                "agent_session_id": NEW,
            },
        }
    ]


def test_mixed_pane_driver_reports_only_the_qualified_herdr_pane(*, tmp_path) -> None:
    """The route decodes the durable replacement coordinate, never an environment pane."""
    target = herdr_identity.HerdrPaneTarget(
        socket_path=str(tmp_path / "herdr.sock"),
        server_pid=700,
        server_starttime="server-start",
        pane_id="w1:p9",
    )
    reported: list[dict[str, object]] = []
    writer = SimpleNamespace(
        report_agent_session=lambda **kwargs: reported.append(kwargs) or SimpleNamespace(ok=True)
    )
    driver = pane_router.MixedPaneDriver(herdr_writer=writer)

    outcome = driver.report_agent_session(
        session=herdr_identity.encode_herdr_target(target=target),
        source="overseerd",
        agent_session_id=NEW,
    )

    assert outcome.ok
    assert reported == [{"target": target, "source": "overseerd", "agent_session_id": NEW}]


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
