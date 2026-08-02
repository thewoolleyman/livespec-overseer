"""Regression tests for startup MCP launch-chain shell evidence."""

from __future__ import annotations

import inspect

import claude_sessions
import codex_sessions
import registry
from test_supervisor_builders import codex_idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def children_of(*, children: dict[int, list[int]]):
    return lambda *, pid: children.get(pid, [])


def comm_of(*, comms: dict[int, str]):
    return lambda *, pid: comms.get(pid)


def starttime_of(*, starttimes: dict[int, str]):
    return lambda *, pid: starttimes.get(pid)


def active_subshell(*, children, comms, starttimes):
    assert "starttime_of" in inspect.signature(claude_sessions.has_active_subshell).parameters
    return claude_sessions.has_active_subshell(
        root_pid=100,
        children_of=children_of(children=children),
        comm_of=comm_of(comms=comms),
        starttime_of=starttime_of(starttimes=starttimes),
    )


def test_session_start_mcp_launch_chain_is_not_active_subshell_evidence():
    assert (
        active_subshell(
            children={100: [200], 200: [300], 300: [400], 400: [500], 500: [600]},
            comms={200: "codex", 300: "sh", 400: "op", 500: "bash", 600: "node"},
            starttimes={200: "1000", 300: "1001", 400: "1002", 500: "1003", 600: "1004"},
        )
        is False
    )


def test_starttime_reader_is_injected_for_shell_walk_tests():
    assert "starttime_of" in inspect.signature(claude_sessions.has_active_subshell).parameters


def test_later_task_shell_remains_active_subshell_evidence():
    assert (
        active_subshell(
            children={100: [200], 200: [300]},
            comms={200: "codex", 300: "bash"},
            starttimes={200: "1000", 300: "2600"},
        )
        is True
    )


def test_ambiguous_starttime_evidence_fails_busy():
    assert (
        active_subshell(
            children={100: [200], 200: [300]},
            comms={200: "codex", 300: "bash"},
            starttimes={200: "1000"},
        )
        is True
    )
    assert (
        active_subshell(
            children={100: [200], 200: [300]},
            comms={200: "codex", 300: "bash"},
            starttimes={300: "1001"},
        )
        is True
    )


def test_relaunched_launch_chain_remains_active_subshell_evidence():
    assert (
        active_subshell(
            children={100: [200], 200: [300], 300: [400], 400: [500], 500: [600]},
            comms={200: "codex", 300: "sh", 400: "op", 500: "bash", 600: "node"},
            starttimes={200: "1000", 300: "2600", 400: "2601", 500: "2602", 600: "2603"},
        )
        is True
    )


def test_codex_launch_chain_can_reach_threshold_handling(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=codex_idle_capture(ctx=40, topic=topic), cmd="bun"
    )
    fake.pane_pid_map[session] = 100
    children = {100: [200], 200: [300], 300: [400], 400: [500], 500: [600]}
    comms = {200: "codex", 300: "sh", 400: "op", 500: "bash", 600: "node"}
    starttimes = {200: "1000", 300: "1001", 400: "1002", 500: "1003", 600: "1004"}
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        children_of=children_of(children=children),
        comm_of=comm_of(comms=comms),
        starttime_of=starttime_of(starttimes=starttimes),
    )
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=321, name=topic, cwd=str(repo), session_id="codex-1"
        )
    }
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "warned"
    assert view.note is None
    assert fake.has(method="paste")
