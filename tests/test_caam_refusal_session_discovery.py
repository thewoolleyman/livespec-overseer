"""Which sessions a pass reads refusals from, in production.

The join is the one model enforcement already makes -- a tmux pane's process
tree walked for the environment a Claude session publishes -- asked for one more
fact. Both values are read from the SAME environment block, which is what makes
the configuration directory trustworthy as a credential discriminator: it
belongs to the very process that wrote the transcript.
"""

from __future__ import annotations

from pathlib import Path

import caam_refusal_sessions
import pytest
from caam_refusal_sessions import discover_tracked_sessions, tracked_sessions_from_panes

__all__: list[str] = []


def environ(*, values: tuple[str, ...]) -> bytes:
    return "\0".join(values).encode()


def test_a_session_publishing_no_configuration_directory_is_on_the_default_one() -> None:
    """Which is what the agent itself does with the variable unset."""
    sessions = tracked_sessions_from_panes(
        home=Path("/home/op"),
        pane_pids=(10,),
        children_of=lambda *, pid: [11] if pid == 10 else [],
        environ_of=lambda *, pid: (
            environ(values=("TERM=xterm", "CLAUDE_CODE_SESSION_ID=abc")) if pid == 11 else None
        ),
    )

    assert len(sessions) == 1
    assert sessions[0].session_id == "abc"
    assert sessions[0].config_dir == Path("/home/op/.claude")
    assert sessions[0].provider == "anthropic"


def test_a_sandbox_session_carries_the_configuration_directory_it_published() -> None:
    sessions = tracked_sessions_from_panes(
        home=Path("/home/op"),
        pane_pids=(10,),
        children_of=lambda *, pid: [],
        environ_of=lambda *, pid: environ(
            values=(
                "CLAUDE_CODE_SESSION_ID=sandbox-session",
                "CLAUDE_CONFIG_DIR=/tmp/caam-refresh/anthropic-1",
            )
        )
        if pid == 10
        else None,
    )

    assert sessions[0].config_dir == Path("/tmp/caam-refresh/anthropic-1")


def test_one_session_reachable_from_two_panes_is_read_once() -> None:
    """Reading its transcript twice would double every refusal it carries."""
    sessions = tracked_sessions_from_panes(
        home=Path("/home/op"),
        pane_pids=(10, 20),
        children_of=lambda *, pid: [],
        environ_of=lambda *, pid: environ(values=("CLAUDE_CODE_SESSION_ID=shared",)),
    )

    assert tuple(session.session_id for session in sessions) == ("shared",)


@pytest.mark.parametrize(
    "block",
    [
        pytest.param(None, id="no-environ-at-all"),
        pytest.param(b"", id="empty-environ"),
        pytest.param(b"TERM=xterm", id="no-session-id"),
        pytest.param(b"CLAUDE_CODE_SESSION_ID=", id="empty-session-id"),
    ],
)
def test_a_process_that_names_no_session_contributes_nothing(*, block: bytes | None) -> None:
    assert (
        tracked_sessions_from_panes(
            home=Path("/home/op"),
            pane_pids=(10,),
            children_of=lambda *, pid: [],
            environ_of=lambda *, pid: block,
        )
        == ()
    )


def test_production_discovery_asks_tmux_for_every_pane_once(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One tmux call for the whole host, then `/proc` per pane.

    The tmux seam is patched at the binding this module READS, not at its
    definition, so the real call is never made from a test host.
    """
    calls: list[str] = []

    class _Tmux:
        def pane_pid_sessions(self) -> dict[int, str]:
            calls.append("pane_pid_sessions")
            return {10: "livespec", 20: "overseer"}

    monkeypatch.setattr(caam_refusal_sessions, "real_picker_tmux", _Tmux)
    monkeypatch.setattr(caam_refusal_sessions.claude_sessions, "proc_children", lambda *, pid: [])
    monkeypatch.setattr(
        caam_refusal_sessions.claude_sessions,
        "proc_environ",
        lambda *, pid: environ(values=(f"CLAUDE_CODE_SESSION_ID=session-{pid}",)),
    )

    sessions = discover_tracked_sessions(home=Path("/home/op"))

    assert calls == ["pane_pid_sessions"]
    assert sorted(session.session_id for session in sessions) == ["session-10", "session-20"]
