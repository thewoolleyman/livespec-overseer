"""Exact process, rollout, naming, and continuation controls for Codex successors."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import _herdr_replacement_store
import _supervisor_herdr_codex
import _supervisor_herdr_codex_naming
import _supervisor_herdr_codex_successor
import herdr_identity
import herdr_write
import pane_router_replacement
import pytest
from _codex_session_models import CodexSession
from _supervisor_launch_profile import CodexLaunchPlan
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


@pytest.mark.parametrize("report_ok", [False, True])
def test_fresh_codex_without_rollout_reports_its_named_thread_and_still_resumes_on_rejection(
    *, tmp_path, monkeypatch, report_ok: bool
) -> None:
    sup, fake, track, target, transaction, path = _world(tmp_path=tmp_path)
    del sup.live_codex[(target, track.topic)]
    reports = []
    resumes = []
    alerts = []
    fake.report_agent_session = lambda **kwargs: reports.append(kwargs) or herdr_write.WriteOutcome(
        ok=report_ok,
        error="denied" if not report_ok else "",
        effect_unknown=False,
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
    assert reports == [{"session": target, "source": "herdr:codex", "agent_session_id": NEW}]
    assert resumes == ["read the durable handoff"]
    assert bool(alerts) is not report_ok
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["successor_thread"] == NEW
    assert record["backend_report"] == {"thread": NEW, "accepted": report_ok}


def test_unconfirmed_fresh_codex_without_rollout_is_neither_reported_nor_resumed(
    *, tmp_path, monkeypatch
) -> None:
    sup, fake, track, target, transaction, _path = _world(tmp_path=tmp_path)
    del sup.live_codex[(target, track.topic)]
    reports = []
    fake.report_agent_session = lambda **kwargs: reports.append(kwargs) or pytest.fail(
        "unexpected report"
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


def test_herdr_writer_reports_only_the_explicit_backend_pane(*, monkeypatch) -> None:
    target = herdr_identity.HerdrPaneTarget(
        socket_path="/tmp/herdr.sock",
        server_pid=700,
        server_starttime="server-start",
        pane_id="w1:p9",
    )
    writer = herdr_write.HerdrWriter()
    calls = []
    monkeypatch.setattr(
        herdr_write.HerdrWriter,
        "request",
        lambda _self, **kwargs: calls.append(kwargs)
        or SimpleNamespace(ok=True, error="", effect_unknown=False),
    )

    assert hasattr(writer, "report_agent_session")
    outcome = writer.report_agent_session(target=target, source="overseerd", agent_session_id=NEW)

    assert outcome.ok
    assert calls == [
        {
            "target": target,
            "method": "pane.report_agent_session",
            "params": {
                "pane_id": "w1:p9",
                "source": "overseerd",
                "agent": "codex",
                "agent_session_id": NEW,
            },
            "expect": herdr_write.herdr_write_calls.EXPECT_OK,
        }
    ]


STALE = "019f548d-0000-7000-8000-000000000002"


def test_launch_records_every_preexisting_thread_before_proving_the_successor(
    *, monkeypatch
) -> None:
    """A thread renamed after launch is not evidence that this launch created it."""
    target = "herdr:target"
    track = SimpleNamespace(repo="/repo", topic="topic", tmux=target)
    sup = SimpleNamespace(
        live_codex={(target, "topic"): SimpleNamespace(pid=101, session_id=OLD)},
        codex_home="/codex",
        starttime_of=lambda **_kwargs: "start",
    )
    captured = []
    sentinel = object()
    monkeypatch.setattr(
        _supervisor_herdr_codex.codex_sessions,
        "read_thread_names",
        lambda **_kwargs: {OLD: "topic", STALE: "unrelated-name"},
    )
    monkeypatch.setattr(_supervisor_herdr_codex, "resume_for_track", lambda **_kwargs: "resume")
    monkeypatch.setattr(
        _supervisor_herdr_codex,
        "codex_fresh_launch_plan",
        lambda **_kwargs: CodexLaunchPlan(command="codex", env={}),
    )
    monkeypatch.setattr(_supervisor_herdr_codex, "statusline_mismatch", lambda **_kwargs: False)
    monkeypatch.setattr(
        _supervisor_herdr_codex._supervisor_herdr_replacement,
        "begin_herdr_replacement",
        lambda **kwargs: captured.append(kwargs["binding"]) or sentinel,
    )

    assert (
        _supervisor_herdr_codex.begin_codex_replacement(sup=sup, track=track, target=target)
        is sentinel
    )
    assert captured[0].predecessor_named_threads == (OLD, STALE)


def test_rolloutless_proof_refuses_multiple_fresh_codex_carriers() -> None:
    snapshot = SimpleNamespace(
        foreground_group=300,
        processes=(
            SimpleNamespace(pid=301, executable="/usr/bin/codex"),
            SimpleNamespace(pid=302, executable="/usr/bin/codex"),
        ),
    )
    sup = SimpleNamespace(tmux=SimpleNamespace(report_agent_session=lambda **_kwargs: None))
    module_path = Path(_supervisor_herdr_codex_successor.__file__).with_name(
        "_supervisor_herdr_codex_carrier.py"
    )
    assert module_path.is_file()
    carrier_module = importlib.import_module("_supervisor_herdr_codex_carrier")

    carrier, reason = carrier_module.carrier_without_rollout(sup=sup, snapshot=snapshot)

    assert carrier is None
    assert reason == "fresh Codex successor is not uniquely observable in the retained shell"


def test_successor_proof_refuses_a_carrier_that_is_not_fresh(*, monkeypatch) -> None:
    carrier = SimpleNamespace(pid=301, starttime="new")
    snapshot = SimpleNamespace()
    sup = SimpleNamespace(
        tmux=SimpleNamespace(herdr_replacement_snapshot=lambda **_kwargs: snapshot),
        refresh_codex_sessions=lambda: None,
        live_codex={("pane", "topic"): object()},
    )
    track = SimpleNamespace(topic="topic")
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_launch,
        "session_of",
        lambda **_kwargs: "pane",
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_herdr_codex_carrier,
        "carrier_from_live_rollout",
        lambda **_kwargs: (carrier, None),
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._herdr_replacement_process,
        "proven_successor",
        lambda **_kwargs: None,
    )

    successor, reason = _supervisor_herdr_codex_successor._prove_successor(
        sup=sup, track=track, target="pane", current={}
    )

    assert successor is None
    assert reason == "Codex successor is not a fresh process in the retained shell"


def test_successor_stays_unproven_when_the_post_wait_index_lookup_is_empty(
    *, tmp_path, monkeypatch
) -> None:
    sup = SimpleNamespace(
        tmux=SimpleNamespace(capture_pane=lambda **_kwargs: "Codex idle"),
        sleep=lambda _seconds: None,
    )
    track = SimpleNamespace(topic="topic")
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor.signals,
        "is_structured_gate",
        lambda **_kwargs: False,
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor.signals,
        "is_codex_idle_input",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_herdr_codex_naming,
        "name_fresh_successor",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        _supervisor_herdr_codex_successor._supervisor_herdr_codex_naming,
        "named_thread",
        lambda **_kwargs: None,
    )

    reason = _supervisor_herdr_codex_successor._rename_successor(
        sup=sup,
        track=track,
        target="pane",
        current={"phase": "launch-attempted", "predecessor_rollout": OLD},
        record_path=tmp_path / "record.json",
        rollout=OLD,
    )

    assert reason == "fresh Codex successor was never named for this plan topic"


def test_agent_session_report_routes_only_to_the_coordinate_backend() -> None:
    target = herdr_identity.HerdrPaneTarget(
        socket_path="/tmp/herdr.sock",
        server_pid=700,
        server_starttime="start",
        pane_id="w1:p9",
    )
    calls = []
    writer = SimpleNamespace(
        report_agent_session=lambda **kwargs: calls.append(kwargs) or "reported"
    )
    host = SimpleNamespace(herdr_writer=writer)

    outcome = pane_router_replacement.report_agent_session(
        host,
        session=herdr_identity.encode_herdr_target(target=target),
        source="overseerd",
        agent_session_id=STALE,
    )

    assert outcome == "reported"
    assert calls == [{"target": target, "source": "overseerd", "agent_session_id": STALE}]
