"""Claude identity evidence supplied by a Herdr foreground process group."""

from __future__ import annotations

from types import SimpleNamespace

import herdr_adapter
import herdr_calls
import herdr_identity
import pane_router
import pane_router_reads
import pytest
import registry
from test_supervisor_builders import idle_capture, make_plan, make_supervisor, mapped_track
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_launch_shell_with_a_named_claude_group_member_is_a_live_track(*, tmp_path):
    """A launch shell does not hide its in-group Claude session from supervision."""
    repo, topic = make_plan(tmp_path=tmp_path, topic="launch-shell")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=80), cmd="bash")
    fake.pane_claude_cwds = lambda *, session: (str(repo),)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_names_by_session = {session: {topic}}

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=False)

    assert view.status == "idle-with-context-left"
    assert view.ctx == 80


def test_launch_shell_without_a_claude_group_member_stays_session_gone(*, tmp_path):
    """A launch shell alone is not evidence that this topic's Claude is live."""
    repo, topic = make_plan(tmp_path=tmp_path, topic="launch-shell-gone")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=80), cmd="bash")
    fake.pane_claude_cwds = lambda *, session: ()
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_names_by_session = {session: {topic}}

    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=False)

    assert view.status == "session-gone"


def test_herdr_read_preserves_a_launch_shells_claude_member_cwd():
    """The exact-pane read carries the Claude member, not only the bash leader."""
    process = herdr_calls.foreground_process(
        result={
            "process_info": {
                "pane_id": "w1:p1",
                "shell_pid": 10,
                "foreground_process_group_id": 20,
                "foreground_processes": [
                    {"pid": 20, "name": "bash", "cmdline": "bash launch.sh", "cwd": "/shell"},
                    {
                        "pid": 21,
                        "name": "claude",
                        "cmdline": "claude -n launch-shell",
                        "cwd": "/repo",
                    },
                ],
            }
        }
    )

    assert process is not None
    assert getattr(process, "claude_cwds", ()) == ("/repo",)

    target = herdr_identity.HerdrPaneTarget(
        socket_path="/run/herdr.sock",
        server_pid=1,
        server_starttime="start",
        pane_id="w1:p1",
    )
    reads = pane_router_reads.PaneRoutingReads(
        tmux=SimpleNamespace(),
        herdr=SimpleNamespace(
            foreground=lambda *, target: herdr_adapter.ForegroundReading(
                ok=True, process=process, error=""
            )
        ),
        herdr_endpoints=lambda: (),
        tmux_run=lambda **_kwargs: "",
        coordinates=set(),
    )

    session = herdr_identity.encode_herdr_target(target=target)
    assert getattr(reads, "pane_claude_cwds", lambda *, session: ())(session=session) == ("/repo",)
    assert getattr(reads, "pane_claude_cwds", lambda *, session: ())(session="legacy") == ()

    driver = pane_router.MixedPaneDriver(tmux=SimpleNamespace(), herdr=reads.herdr)
    assert getattr(driver, "pane_claude_cwds", lambda *, session: ())(session=session) == ("/repo",)
