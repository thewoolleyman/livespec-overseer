"""Integration-tier v005 shell-only low-context wrap-up behavior."""

import contextlib
import io as _io

import pytest

from overseer import codex_sessions, registry, signals
from overseer.test_supervisor_builders import (
    arm_ready_marker,
    busy_capture,
    codex_busy_capture,
    codex_idle_capture,
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    wrapup_count,
)
from overseer.test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _codex_shell_sup(*, tmp_path, fake, repo, topic, session):
    fake.pane_pid_map[session] = 100
    children = {100: [200]}
    comms = {200: "bash"}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        children_of=lambda *, pid: children.get(pid, []),
        comm_of=lambda *, pid: comms.get(pid),
    )
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=321, name=topic, cwd=str(repo), session_id="codex-1"
        )
    }
    return sup


def test_claude_status_shell_allows_guarded_low_context_wrapup(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session = {session: "shell"}

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "warned"
    assert wrapup_count(fake=fake) == 1
    assert fake.has(method="keys")
    assert not fake.has(method="respawn")


def test_codex_descendant_shell_allows_structural_guarded_low_context_wrapup(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    captures = [codex_idle_capture(ctx=40, topic=topic)] * 5
    captures.append(codex_busy_capture(ctx=40))
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=captures, cmd="bun")
    sup = _codex_shell_sup(tmp_path=tmp_path, fake=fake, repo=repo, topic=topic, session=session)

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "warned"
    assert wrapup_count(fake=fake) == 1
    assert fake.has(method="keys")
    assert not fake.has(method="respawn")


@pytest.mark.parametrize(
    ("capture", "claude_status", "expected_note"),
    [
        (busy_capture(ctx=40), None, None),
        (idle_capture(ctx=40), "busy", "sub-agent (Claude busy)"),
    ],
)
def test_generating_and_sub_agent_evidence_still_suppress_wrapup(
    *, tmp_path, capture, claude_status, expected_note
):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=capture)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    if claude_status is not None:
        sup.claude_status_by_session = {session: claude_status}

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "working"
    assert view.note == expected_note
    assert wrapup_count(fake=fake) == 0
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )
    assert not fake.has(method="respawn")


@pytest.mark.parametrize(
    ("state_value", "expected_status"),
    [
        ("blocked: need human", "blocked:human"),
        (signals.STATE_WINDING_DOWN, "winding-down"),
        ("nonsense", "warned"),
    ],
)
def test_declarations_suppress_shell_only_wrapup(*, tmp_path, state_value, expected_status):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session = {session: "shell"}
    declare(repo=repo, topic=topic, value=state_value, mtime=1001.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == expected_status
    assert wrapup_count(fake=fake) == 0
    assert not fake.has(method="respawn")


def test_ready_declaration_suppresses_shell_only_wrapup_and_does_not_restart(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session = {session: "shell"}
    registry.write_injection_stamp(repo=str(repo), topic=topic, ts=900.0, stamp_path=sup.stamp_path)
    marker = arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "working"
    assert wrapup_count(fake=fake) == 0
    assert marker.exists()
    assert not fake.has(method="respawn")


def test_uncertified_ready_declaration_suppresses_shell_only_wrapup(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session = {session: "shell"}
    marker = arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "settling"
    assert wrapup_count(fake=fake) == 0
    assert marker.exists()
    assert not fake.has(method="respawn")


@pytest.mark.parametrize(
    "capture",
    [
        "Do you want to proceed?\n❯ 1. Yes\n  2. No\n  Ctx: 40% left\n",
        "prior output\nCtx: 40% left\n",
    ],
)
def test_gate_or_missing_input_suppresses_shell_only_wrapup(*, tmp_path, capture):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=capture)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session = {session: "shell"}

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status in {"blocked:human", "settling"}
    assert wrapup_count(fake=fake) == 0
    assert not fake.has(method="respawn")


def test_unknown_claude_status_cancels_before_shell_only_wrapup(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session = {session: "mystery"}

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "settling"
    assert wrapup_count(fake=fake) == 0
    assert not fake.has(method="respawn")


def test_pre_paste_recheck_cancels_when_capture_changes_after_settle(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session,
        repo=repo,
        capture=[
            idle_capture(ctx=40),
            idle_capture(ctx=40),
            idle_capture(ctx=40),
            busy_capture(ctx=40),
        ],
    )
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session = {session: "shell"}

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "settling"
    assert wrapup_count(fake=fake) == 0
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )


def test_pre_paste_recheck_cancels_when_identity_changes_after_settle(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=40), cmd=["node", "node", "zsh"]
    )
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session = {session: "shell"}

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "settling"
    assert wrapup_count(fake=fake) == 0
    assert not fake.has(method="respawn")


def test_pre_paste_recheck_cancels_when_runtime_changes_after_settle(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session,
        repo=repo,
        capture=idle_capture(ctx=40),
        cmd=["node", "node", "node", "bun", "bun"],
    )
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session = {session: "shell"}
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=321, name=topic, cwd=str(repo), session_id="codex-1"
        )
    }

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "settling"
    assert wrapup_count(fake=fake) == 0
    assert not fake.has(method="respawn")


def test_shell_only_danger_wrapup_is_report_only_and_never_restarts_or_writes_state(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=20))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session = {session: "shell"}

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "danger"
    assert wrapup_count(fake=fake) == 1
    assert "NOT RESPONDING — ctx 20% left" in err.getvalue()
    assert not fake.has(method="respawn")
    assert not fake.has(method="new")
    assert signals.read_state(repo=str(repo), topic=topic) is None
