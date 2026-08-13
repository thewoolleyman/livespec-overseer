"""Regression tests for relaunched launch-chain argv identity."""

from __future__ import annotations

import inspect

import claude_sessions
from _claude_sessions_subshell import has_active_subshell as direct_has_active_subshell

__all__: list[str] = []

_WRAPPER_ARGV = (
    b"bash\x00/usr/local/bin/with-homelab-env.sh\x00bash\x00-lc\x00" b"exec npx -y mcp-remote\x00"
)
_MCP_ARGV = b"sh\x00-c\x00mcp-remote\x00https://mcp.cloudflare.com/mcp\x00"


def _has_active_subshell(*, cmdlines: dict[int, bytes]) -> bool:
    kwargs = {
        "root_pid": 100,
        "children_of": lambda *, pid: {
            100: [200],
            200: [300, 700],
            300: [400],
            400: [500],
            500: [600],
            700: [800],
            800: [900],
            900: [1000],
        }.get(pid, []),
        "comm_of": lambda *, pid: {
            200: "codex",
            300: "bash",
            400: "op",
            500: "sh",
            600: "node",
            700: "bash",
            800: "op",
            900: "sh",
            1000: "node",
        }.get(pid),
        "starttime_of": lambda *, pid: {
            200: "1000",
            300: "1001",
            400: "1002",
            500: "1003",
            600: "1004",
            700: "2600",
            800: "2601",
            900: "2602",
            1000: "2603",
        }.get(pid),
    }
    if "cmdline_of" in inspect.signature(claude_sessions.has_active_subshell).parameters:
        kwargs["cmdline_of"] = lambda *, pid: cmdlines.get(pid)
    return claude_sessions.has_active_subshell(**kwargs)


def test_relaunched_launch_chain_with_identical_startup_argv_twin_is_not_busy():
    assert (
        _has_active_subshell(
            cmdlines={
                300: _WRAPPER_ARGV,
                500: _MCP_ARGV,
                700: _WRAPPER_ARGV,
                900: _MCP_ARGV,
            }
        )
        is False
    )


def test_deep_late_shell_under_twinned_late_wrapper_is_not_busy():
    assert (
        _has_active_subshell(
            cmdlines={
                300: _WRAPPER_ARGV,
                700: _WRAPPER_ARGV,
                900: _MCP_ARGV,
            }
        )
        is False
    )


def test_deep_late_shell_without_twinned_late_ancestor_stays_busy():
    assert (
        _has_active_subshell(
            cmdlines={
                300: _WRAPPER_ARGV,
                700: b"bash\x00-lc\x00exec something-else\x00",
                900: _MCP_ARGV,
            }
        )
        is True
    )


def test_late_credential_wrapper_shell_is_excluded_before_timestamp_classification():
    assert (
        direct_has_active_subshell(
            root_pid=100,
            children_of=lambda *, pid: {
                100: [200],
                200: [300],
                300: [400],
                400: [500],
            }.get(pid, []),
            comm_of=lambda *, pid: {200: "codex", 300: "bash", 400: "op", 500: "sh"}.get(pid),
            starttime_of=lambda *, pid: {200: "1000", 300: "2600", 400: "2601", 500: "2602"}.get(
                pid
            ),
            cmdline_of=lambda *, pid: {300: _WRAPPER_ARGV}.get(pid),
        )
        is False
    )


def test_non_wrapper_task_shell_with_op_descendant_stays_busy():
    assert (
        direct_has_active_subshell(
            root_pid=100,
            children_of=lambda *, pid: {100: [200], 200: [300], 300: [400]}.get(pid, []),
            comm_of=lambda *, pid: {200: "codex", 300: "bash", 400: "op"}.get(pid),
            starttime_of=lambda *, pid: {200: "1000", 300: "2600", 400: "2601"}.get(pid),
            cmdline_of=lambda *, pid: {300: b"bash\x00-lc\x00op run-real-task"}.get(pid),
        )
        is True
    )


def test_late_shell_under_a_twinned_late_shell_is_startup_plumbing():
    assert (
        direct_has_active_subshell(
            root_pid=100,
            children_of=lambda *, pid: {
                100: [200],
                200: [300, 700],
                700: [900],
            }.get(pid, []),
            comm_of=lambda *, pid: {200: "codex", 300: "bash", 700: "bash", 900: "sh"}.get(pid),
            starttime_of=lambda *, pid: {200: "1000", 300: "1001", 700: "2600", 900: "2601"}.get(
                pid
            ),
            cmdline_of=lambda *, pid: {300: b"startup", 700: b"startup", 900: b"child"}.get(pid),
        )
        is False
    )


def test_wrapper_descendant_walk_ignores_a_seen_cycle():
    assert (
        direct_has_active_subshell(
            root_pid=100,
            children_of=lambda *, pid: {
                100: [200],
                200: [300],
                300: [400, 300],
            }.get(pid, []),
            comm_of=lambda *, pid: {200: "codex", 300: "bash", 400: "op"}.get(pid),
            starttime_of=lambda *, pid: {200: "1000", 300: "2600", 400: "2601"}.get(pid),
            cmdline_of=lambda *, pid: {300: _WRAPPER_ARGV}.get(pid),
        )
        is False
    )


def test_wrapper_ancestor_walk_terminates_on_a_parent_cycle():
    assert (
        direct_has_active_subshell(
            root_pid=100,
            children_of=lambda *, pid: {
                100: [200, 100],
                200: [300],
                300: [400],
            }.get(pid, []),
            comm_of=lambda *, pid: {200: "codex", 300: "bash", 400: "op"}.get(pid),
            starttime_of=lambda *, pid: {200: "1000", 300: "2600", 400: "2601"}.get(pid),
            cmdline_of=lambda *, pid: {300: _WRAPPER_ARGV}.get(pid),
        )
        is False
    )
