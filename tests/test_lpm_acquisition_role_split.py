"""Acquisition research and execution have disjoint, closed capabilities."""

from __future__ import annotations

import importlib
from pathlib import Path


def test_acquisition_role_vectors_are_closed_and_secret_free():
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_acquisition_roles.py"
    assert module_path.is_file(), "the acquisition role boundary must be implemented"
    roles = importlib.import_module("_lpm_acquisition_roles")
    request = {
        "version": 1,
        "provider": "anthropic",
        "kind": "claude-code-oauth",
        "acquisition_terminal": "claude setup-token",
        "browser_origins": [
            "https://claude.ai",
            "https://claude.com",
            "https://platform.claude.com",
            "https://accounts.google.com",
        ],
    }

    research = roles.research_invocation(
        claude_executable="/opt/claude", role_directory="/state/research", request=request
    )
    execution = roles.execution_invocation(
        claude_executable="/opt/claude",
        proxy_executable="/opt/lpm-acquisition-proxy",
        role_directory="/state/execution",
        request={
            "version": 1,
            "record_id": "record-1",
            "provider": "anthropic",
            "account_id": "account-1",
            "kind": "claude-code-oauth",
            "purpose": "factory",
            "brief": {"steps": ["open the provider authorization page"]},
            "profile_ref": "profile-1",
            "remaining_steps": 50,
        },
    )

    assert research.argv[1:9] == (
        "--print",
        "--verbose",
        "--output-format",
        "stream-json",
        "--safe-mode",
        "--tools",
        "WebSearch",
        "--allowed-tools",
    )
    assert research.argv[9] == "WebSearch"
    assert "--no-chrome" in research.argv
    assert research.expected_tools == ("WebSearch",)
    assert research.input_object == request
    assert "mcpServers" not in "".join(research.argv)

    assert "--restricted" in execution.argv
    assert "--safe-mode" not in execution.argv
    assert "WebSearch" not in execution.argv
    assert execution.expected_tools == tuple(
        f"mcp__lpm_acquisition__{name}"
        for name in (
            "observe-browser",
            "navigate-browser",
            "click-browser",
            "type-browser-text",
            "select-browser",
            "scroll-browser",
            "wait-browser",
            "start-terminal",
            "observe-terminal",
            "send-terminal-line",
            "send-terminal-handle",
            "wait-terminal",
            "terminate-terminal",
            "type-login-material",
            "apply-mailbox-verification",
            "capture-token",
            "discard-capture",
        )
    )
    assert execution.argv[-18] == "--allowed-tools"
    assert execution.argv[-17:] == execution.expected_tools
    assert execution.mcp_config == (
        '{"mcpServers":{"lpm_acquisition":{"command":'
        '"/opt/lpm-acquisition-proxy","args":[],"env":{}}}}'
    )
    assert set(execution.input_object) == {
        "version",
        "record_id",
        "provider",
        "account_id",
        "kind",
        "purpose",
        "brief",
        "profile_ref",
        "remaining_steps",
    }
    assert all(
        forbidden not in repr((research, execution)).lower()
        for forbidden in ("login_secret", "mailbox_code", "credential_value", "token_value")
    )
