"""Tests for tmuxio.py — READS plus the fail-soft/liveness guarantees.

Run: ``uv run pytest .claude/skills/overseer/ -q``. No REAL tmux runs: a fake
``run`` callable (same shape as ``subprocess.run``) is injected from
`test_tmuxio_fakes`, so we assert on the exact argv tmux would be invoked with,
and on fail-soft sentinels.

The WRITE half lives in `test_tmuxio_writes.py`. The two were one module until
it crossed the 250-LLOC hard ceiling; the split follows the section banners the
file already carried, so no test changed meaning.
"""

import subprocess

from test_tmuxio_fakes import io as _io

__all__: list[str] = []

# --------------------------------------------------------------------------- #
# Reads.
# --------------------------------------------------------------------------- #


def test_capture_pane_argv_and_output():
    io, fake = _io(stdout="pane text here\n")
    assert io.capture_pane(session="livespec:topic") == "pane text here\n"
    assert fake.calls[0]["argv"] == ["tmux", "capture-pane", "-p", "-t", "livespec:topic"]


def test_capture_pane_empty_on_error():
    io, _ = _io(returncode=1, stdout="ignored")
    assert io.capture_pane(session="s") == ""


def test_pane_current_command_strips_and_nones():
    # Reliable read via list-panes (not the flaky display-message); the row is
    # `#{pane_id}\t#{pane_active}\t<field>`.
    io, fake = _io(stdout="%1\t1\tnode\n")
    assert io.pane_current_command(session="s") == "node"
    assert fake.calls[0]["argv"] == [
        "tmux",
        "list-panes",
        "-t",
        "s",
        "-F",
        "#{pane_id}\t#{pane_active}\t#{pane_current_command}",
    ]
    io2, _ = _io(stdout="%1\t1\t   \n")  # whitespace-only field → None
    assert io2.pane_current_command(session="s") is None
    io3, _ = _io(returncode=1)
    assert io3.pane_current_command(session="s") is None


def test_pane_current_path_format():
    io, fake = _io(stdout="%1\t1\t/data/projects/livespec\n")
    assert io.pane_current_path(session="s") == "/data/projects/livespec"
    assert fake.calls[0]["argv"][-1] == "#{pane_id}\t#{pane_active}\t#{pane_current_path}"


def test_pane_id_format():
    # RB3: resolve the exact pane id to target instead of the prefix-prone name.
    io, fake = _io(stdout="%5\t1\t%5\n")
    assert io.pane_id(session="s") == "%5"
    assert fake.calls[0]["argv"] == [
        "tmux",
        "list-panes",
        "-t",
        "s",
        "-F",
        "#{pane_id}\t#{pane_active}\t#{pane_id}",
    ]
    io2, _ = _io(returncode=1)  # session gone → None (fail-soft)
    assert io2.pane_id(session="s") is None


def test_pane_field_pane_id_target_filters_exact_pane():
    # A PANE-ID target selects THAT pane's field, not the active/first (RB3).
    io, _ = _io(stdout="%1\t0\tzsh\n%5\t1\tnode\n")
    assert io.pane_current_command(session="%5") == "node"
    assert io.pane_current_command(session="%1") == "zsh"


def test_pane_field_session_target_picks_active_pane():
    # A SESSION-NAME target selects the active pane (pane_active == 1).
    io, _ = _io(stdout="%1\t0\tzsh\n%5\t1\tnode\n")
    assert io.pane_current_command(session="s") == "node"


def test_pane_field_pane_id_not_present_is_none():
    io, _ = _io(stdout="%1\t1\tnode\n")
    assert io.pane_current_command(session="%9") is None


def test_pane_field_empty_output_is_none():
    io, _ = _io(stdout="")
    assert io.pane_current_command(session="s") is None


def test_session_exists_is_exact_membership_not_prefix():
    # B1: session_exists uses EXACT list-sessions membership, not the prefix-prone
    # `has-session -t <name>` (which matches `foobar` for target `foo`).
    io, fake = _io(stdout="foo\nbar\n")
    assert io.session_exists(session="foo") is True
    assert fake.calls[0]["argv"] == ["tmux", "list-sessions", "-F", "#{session_name}"]
    # a longer session sharing the prefix must NOT satisfy the exact target
    io2, _ = _io(stdout="foobar\n")
    assert io2.session_exists(session="foo") is False
    io3, _ = _io(returncode=1)  # no server / error → not live
    assert io3.session_exists(session="foo") is False


def test_list_sessions_parses_lines():
    io, fake = _io(stdout="livespec:a\nother:b\n\n")
    assert io.list_sessions() == ["livespec:a", "other:b"]
    assert fake.calls[0]["argv"] == ["tmux", "list-sessions", "-F", "#{session_name}"]
    io2, _ = _io(returncode=1)
    assert io2.list_sessions() == []


def test_pane_pid_parses_int_and_fails_soft():
    # The pane PID is read through the same `list-panes` row as every other
    # per-pane field, then int-parsed; anything unparseable fails soft to None.
    io, fake = _io(stdout="%5\t1\t482913\n")
    assert io.pane_pid(session="s") == 482913
    assert fake.calls[0]["argv"] == [
        "tmux",
        "list-panes",
        "-t",
        "s",
        "-F",
        "#{pane_id}\t#{pane_active}\t#{pane_pid}",
    ]
    io2, _ = _io(stdout="%5\t1\tnot-a-pid\n")  # non-numeric value → None
    assert io2.pane_pid(session="s") is None
    io3, _ = _io(stdout="%5\t1\t   \n")  # unreadable/empty field → None
    assert io3.pane_pid(session="s") is None
    io4, _ = _io(returncode=1)  # session gone → None (fail-soft)
    assert io4.pane_pid(session="s") is None


def test_pane_pid_sessions_parses_every_pane_across_sessions():
    # The process-side of the registry→tmux join: EVERY pane, all sessions.
    io, fake = _io(stdout="482913\tlivespec:a\n482920\tlivespec:a\n99001\tother:b\n")
    assert io.pane_pid_sessions() == {
        482913: "livespec:a",
        482920: "livespec:a",
        99001: "other:b",
    }
    assert fake.calls[0]["argv"] == [
        "tmux",
        "list-panes",
        "-a",
        "-F",
        "#{pane_pid}\t#{session_name}",
    ]


def test_pane_pid_sessions_skips_malformed_rows():
    # A non-integer pid, a blank line, and a row with no session name are each
    # skipped fail-soft rather than crashing the whole enumeration.
    io, _ = _io(stdout="482913\tlivespec:a\nnot-a-pid\tlivespec:b\n\n7\t   \n99001\tother:b\n")
    assert io.pane_pid_sessions() == {482913: "livespec:a", 99001: "other:b"}


def test_pane_pid_sessions_empty_on_error():
    io, _ = _io(returncode=1, stdout="482913\tlivespec:a\n")
    assert io.pane_pid_sessions() == {}


# --------------------------------------------------------------------------- #
# Fail-soft: a missing tmux binary never crashes the caller.
# --------------------------------------------------------------------------- #


def test_missing_binary_is_fail_soft():
    io, _ = _io(raises=FileNotFoundError("tmux not found"))
    assert io.capture_pane(session="s") == ""
    assert io.session_exists(session="s") is False
    assert io.list_sessions() == []
    assert io.pane_exists(pane="%1") is False
    assert io.pane_current_command(session="s") is None
    assert io.bracketed_paste(session="s", text="x") is False
    assert io.respawn_pane(session="s", cwd="/tmp", command="claude") is False


def test_every_tmux_call_carries_a_timeout():
    """A hung tmux must not wedge the daemon FOREVER, which no catch can prevent.

    `check=False` and a fail-soft handler cover tmux EXITING badly. They do nothing
    about tmux never exiting at all: with no `timeout=`, `subprocess.run` blocks
    indefinitely, no exception is raised, so nothing is caught and the supervision
    loop simply stops. That is invisible to every other guard in this module — and
    the "let it crash, systemd restarts" doctrine cannot help either, because a hang
    never crashes.

    Asserted on EVERY read and write path rather than one, so a later method added
    without a timeout is caught here.
    """
    for invoke in (
        lambda io: io.capture_pane(session="s"),
        lambda io: io.session_exists(session="s"),
        lambda io: io.list_sessions(),
        lambda io: io.pane_exists(pane="%1"),
        lambda io: io.pane_current_command(session="s"),
        lambda io: io.bracketed_paste(session="s", text="x"),
        lambda io: io.respawn_pane(session="s", cwd="/tmp", command="claude"),
    ):
        io, fake = _io()
        invoke(io)
        assert fake.calls, "expected the fake run to be invoked"
        for call in fake.calls:
            timeout = call["timeout"]
            assert timeout is not None, f"no timeout passed for argv {call['argv']}"
            assert timeout > 0, f"non-positive timeout {timeout!r} for argv {call['argv']}"


def test_a_timing_out_tmux_is_fail_soft():
    """`TimeoutExpired` reaches the SAME sentinel as a missing binary.

    It subclasses `SubprocessError` — NOT `OSError` and NOT `ValueError` — so the
    handler's original `(OSError, ValueError)` tuple did not cover it. Adding a
    timeout without widening that tuple would have converted a silent hang into an
    uncaught exception, which under the crash-and-restart doctrine means systemd
    restarts the daemon into the same hung tmux.
    """
    io, _ = _io(raises=subprocess.TimeoutExpired(cmd=["tmux", "capture-pane"], timeout=5.0))
    assert io.capture_pane(session="s") == ""
    assert io.session_exists(session="s") is False
    assert io.list_sessions() == []
    assert io.pane_current_command(session="s") is None
    assert io.bracketed_paste(session="s", text="x") is False
    assert io.respawn_pane(session="s", cwd="/tmp", command="claude") is False
