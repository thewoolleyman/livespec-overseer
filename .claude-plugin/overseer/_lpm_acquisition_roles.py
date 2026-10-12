"""Closed Claude CLI capability vectors for acquisition research and execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final

__all__: list[str] = [
    "ACQUISITION_TOOLS",
    "AcquisitionRoleInvocation",
    "execution_invocation",
    "research_invocation",
]

_RESEARCH_PROMPT: Final = (
    "You are the read-only acquisition researcher. Use only WebSearch. "
    "Return exactly the required JSON object and no other text."
)
_EXECUTION_PROMPT: Final = (
    "You are the credential-acquisition browser operator. Use only the provided "
    "lpm_acquisition tools. Never request, repeat, or infer secret values. Return "
    "exactly the required JSON object and no other text."
)
_TOOL_NAMES: Final = (
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
ACQUISITION_TOOLS: Final = tuple(f"mcp__lpm_acquisition__{name}" for name in _TOOL_NAMES)


@dataclass(frozen=True, kw_only=True)
class AcquisitionRoleInvocation:
    """One immutable, secret-free role launch description."""

    argv: tuple[str, ...]
    role_directory: str
    input_object: dict[str, object]
    expected_tools: tuple[str, ...]
    mcp_config: str | None


def research_invocation(
    *, claude_executable: str, role_directory: str, request: dict[str, object]
) -> AcquisitionRoleInvocation:
    """Build the web-search-only research invocation."""
    return AcquisitionRoleInvocation(
        argv=(
            claude_executable,
            "--print",
            "--verbose",
            "--output-format",
            "stream-json",
            "--safe-mode",
            "--tools",
            "WebSearch",
            "--allowed-tools",
            "WebSearch",
            "--setting-sources",
            "",
            "--managed-settings",
            "{}",
            "--disable-slash-commands",
            "--strict-mcp-config",
            "--permission-prompts",
            "none",
            "--no-session-persistence",
            "--no-chrome",
            "--system-prompt",
            _RESEARCH_PROMPT,
        ),
        role_directory=role_directory,
        input_object=request,
        expected_tools=("WebSearch",),
        mcp_config=None,
    )


def execution_invocation(
    *,
    claude_executable: str,
    proxy_executable: str,
    role_directory: str,
    request: dict[str, object],
) -> AcquisitionRoleInvocation:
    """Build the private-MCP-only browser execution invocation."""
    config = json.dumps(
        {"mcpServers": {"lpm_acquisition": {"command": proxy_executable, "args": [], "env": {}}}},
        separators=(",", ":"),
    )
    return AcquisitionRoleInvocation(
        argv=(
            claude_executable,
            "--print",
            "--verbose",
            "--output-format",
            "stream-json",
            "--restricted",
            "--tools",
            "",
            "--setting-sources",
            "",
            "--managed-settings",
            "{}",
            "--disable-slash-commands",
            "--strict-mcp-config",
            "--mcp-config",
            config,
            "--system-prompt",
            _EXECUTION_PROMPT,
            "--permission-prompts",
            "none",
            "--no-session-persistence",
            "--no-chrome",
            "--allowed-tools",
            *ACQUISITION_TOOLS,
        ),
        role_directory=role_directory,
        input_object=request,
        expected_tools=ACQUISITION_TOOLS,
        mcp_config=config,
    )
