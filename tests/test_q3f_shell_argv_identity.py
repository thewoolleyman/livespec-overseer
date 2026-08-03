"""Regression tests for relaunched launch-chain argv identity."""

from __future__ import annotations

import inspect

import claude_sessions

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
