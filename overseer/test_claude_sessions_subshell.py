"""Tests for descendant shell activity detection."""

import inspect

import claude_sessions

__all__: list[str] = []


# --------------------------------------------------------------------------- #
# has_active_subshell: a DESCENDANT shell ⇒ active background work ⇒ not idle.
# --------------------------------------------------------------------------- #


def _tree(*, children, comms):
    """A pair of fake /proc readers over a static process tree."""
    return (lambda *, pid: children.get(pid, [])), (lambda *, pid: comms.get(pid))


def _has_active_subshell(*, children, comms, starttimes, cmdlines=None, root_pid=100):
    """Drive the detector through the current signature during the Red half."""
    children_of, comm_of = _tree(children=children, comms=comms)
    kwargs = {"root_pid": root_pid, "children_of": children_of, "comm_of": comm_of}
    if "starttime_of" in inspect.signature(claude_sessions.has_active_subshell).parameters:
        kwargs["starttime_of"] = lambda *, pid: starttimes.get(pid)
    if "cmdline_of" in inspect.signature(claude_sessions.has_active_subshell).parameters:
        kwargs["cmdline_of"] = lambda *, pid: (cmdlines or {}).get(pid)
    return claude_sessions.has_active_subshell(**kwargs)


def test_has_active_subshell_exposes_starttime_reader_seam():
    assert "starttime_of" in inspect.signature(claude_sessions.has_active_subshell).parameters


def test_has_active_subshell_true_when_direct_child_is_shell():
    # root 100 → node runtime (200) + a background-command shell (300, zsh).
    children_of, comm_of = _tree(children={100: [200, 300]}, comms={200: "node", 300: "zsh"})
    assert (
        claude_sessions.has_active_subshell(root_pid=100, children_of=children_of, comm_of=comm_of)
        is True
    )


def test_has_active_subshell_false_when_descendants_are_only_non_shells():
    # root 100 → node runtime (200) → an MCP server (300, node). No shell anywhere.
    children_of, comm_of = _tree(
        children={100: [200], 200: [300]}, comms={200: "node", 300: "node"}
    )
    assert (
        claude_sessions.has_active_subshell(root_pid=100, children_of=children_of, comm_of=comm_of)
        is False
    )


def test_has_active_subshell_true_for_deep_shell():
    # A shell nested two levels down: 100 → 200 (node) → 300 (bash).
    children_of, comm_of = _tree(
        children={100: [200], 200: [300]}, comms={200: "node", 300: "bash"}
    )
    assert (
        claude_sessions.has_active_subshell(root_pid=100, children_of=children_of, comm_of=comm_of)
        is True
    )


def test_has_active_subshell_ignores_session_start_mcp_launch_chain():
    # pane shell 100 -> runtime 200 -> sudo/wrapper shell 300 -> op 400 -> shell 500
    # -> long-lived MCP node 600. Both shells are part of the runtime's launch chain,
    # born within the deterministic startup margin, so the session is not busy.
    assert (
        _has_active_subshell(
            children={100: [200], 200: [300], 300: [400], 400: [500], 500: [600]},
            comms={200: "codex", 300: "sh", 400: "op", 500: "bash", 600: "node"},
            starttimes={200: "1000", 300: "1001", 400: "1002", 500: "1003", 600: "1004"},
        )
        is False
    )


def test_has_active_subshell_keeps_later_task_shell_busy():
    assert (
        _has_active_subshell(
            children={100: [200], 200: [300]},
            comms={200: "codex", 300: "bash"},
            starttimes={200: "1000", 300: "2600"},
        )
        is True
    )


def test_has_active_subshell_missing_shell_starttime_fails_busy():
    assert (
        _has_active_subshell(
            children={100: [200], 200: [300]},
            comms={200: "codex", 300: "bash"},
            starttimes={200: "1000"},
        )
        is True
    )
    assert (
        _has_active_subshell(
            children={100: [200], 200: [300]},
            comms={200: "codex", 300: "bash"},
            starttimes={200: "1000", 300: "not-ticks"},
        )
        is True
    )


def test_has_active_subshell_missing_runtime_baseline_fails_busy():
    assert (
        _has_active_subshell(
            children={100: [200], 200: [300]},
            comms={200: "codex", 300: "bash"},
            starttimes={300: "1001"},
        )
        is True
    )
    assert (
        _has_active_subshell(
            children={100: [200], 200: [300]},
            comms={300: "bash"},
            starttimes={200: "1000", 300: "1001"},
        )
        is True
    )


def test_has_active_subshell_relaunched_launch_chain_fails_busy_without_argv_proof():
    # Topology alone is ambiguous: a task can invoke `op`, so without the wrapper
    # argv this must remain busy.
    assert (
        _has_active_subshell(
            children={100: [200], 200: [300], 300: [400], 400: [500], 500: [600]},
            comms={200: "codex", 300: "sh", 400: "op", 500: "bash", 600: "node"},
            starttimes={200: "1000", 300: "2600", 400: "2601", 500: "2602", 600: "2603"},
        )
        is True
    )


def test_has_active_subshell_ignores_late_credential_wrapper_chain():
    assert (
        _has_active_subshell(
            children={100: [200], 200: [300], 300: [400], 400: [500], 500: [600]},
            comms={200: "codex", 300: "bash", 400: "op", 500: "sh", 600: "node"},
            starttimes={200: "1000", 300: "2600", 400: "2601", 500: "2602", 600: "2603"},
            cmdlines={300: b"bash\x00/usr/local/bin/with-livespec-env.sh\x00"},
        )
        is False
    )


def test_has_active_subshell_keeps_non_wrapper_op_task_busy():
    assert (
        _has_active_subshell(
            children={100: [200], 200: [300], 300: [400]},
            comms={200: "codex", 300: "bash", 400: "op"},
            starttimes={200: "1000", 300: "2600", 400: "2601"},
            cmdlines={300: b"bash\x00-lc\x00op run-real-task"},
        )
        is True
    )


def test_has_active_subshell_false_when_no_children():
    assert (
        claude_sessions.has_active_subshell(
            root_pid=100, children_of=lambda *, pid: [], comm_of=lambda *, pid: None
        )
        is False
    )


def test_has_active_subshell_root_itself_is_not_counted():
    # root_pid (the login shell) is itself a shell but has NO descendants → False:
    # only DESCENDANTS count, never root itself.
    children_of, comm_of = _tree(children={}, comms={100: "zsh"})
    assert (
        claude_sessions.has_active_subshell(root_pid=100, children_of=children_of, comm_of=comm_of)
        is False
    )


def test_has_active_subshell_cycle_is_fail_soft():
    # A cycle among non-shells must TERMINATE (visited-set) and return False, no hang.
    children_of, comm_of = _tree(
        children={100: [200], 200: [100]}, comms={100: "node", 200: "node"}
    )
    assert (
        claude_sessions.has_active_subshell(root_pid=100, children_of=children_of, comm_of=comm_of)
        is False
    )
