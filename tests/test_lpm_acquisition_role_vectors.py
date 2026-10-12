"""Acquisition research and execution have disjoint, closed capabilities."""

from __future__ import annotations

import importlib
from pathlib import Path

__all__: list[str] = []


def test_acquisition_role_vectors_are_closed_and_secret_free() -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_acquisition_roles.py"
    assert module_path.is_file(), "the acquisition role boundary must be implemented"
    roles = importlib.import_module("_lpm_acquisition_roles")
    research_request = {
        "version": 1,
        "provider": "anthropic",
        "kind": "claude-code-oauth",
        "acquisition_terminal": "claude setup-token",
        "browser_origins": ["https://claude.ai", "https://accounts.google.com"],
    }
    execution_request = {
        "version": 1,
        "record_id": "record-1",
        "provider": "anthropic",
        "account_id": "account-1",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "brief": "open the provider authorization page",
        "profile_ref": "profile-1",
        "remaining_steps": 50,
    }

    research = roles.research_invocation(
        claude_executable="/opt/claude",
        role_directory="/state/research",
        request=research_request,
    )
    execution = roles.execution_invocation(
        claude_executable="/opt/claude",
        proxy_executable="/opt/lpm-acquisition-proxy",
        role_directory="/state/execution",
        request=execution_request,
    )

    assert research.expected_tools == ("WebSearch",)
    assert "--safe-mode" in research.argv
    assert "--no-chrome" in research.argv
    assert "WebSearch" not in execution.argv
    assert "--restricted" in execution.argv
    assert "--safe-mode" not in execution.argv
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
    assert research.input_object == research_request
    assert execution.input_object == execution_request
    assert all(
        forbidden not in repr((research, execution)).lower()
        for forbidden in ("login_secret", "mailbox_code", "credential_value", "token_value")
    )
