"""The acquisition proxy exposes one closed MCP tool surface over its private port."""

from __future__ import annotations

import importlib
from pathlib import Path

_TOOLS = (
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


class _Exchange:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def __call__(self, *, tool: str, arguments: dict[str, object]) -> dict[str, object]:
        self.calls.append((tool, arguments))
        return {"version": 1, "status": "ok"}


def test_private_proxy_executable_exposes_only_the_seventeen_registered_tools() -> None:
    root = Path(__file__).parents[1]
    module_path = root / "overseer" / "_lpm_acquisition_proxy.py"
    executable = root / ".claude-plugin" / "bin" / "lpm-acquisition-proxy"
    assert module_path.is_file(), "the private acquisition proxy service must exist"
    proxy = importlib.import_module("_lpm_acquisition_proxy")
    exchange = _Exchange()
    service = proxy.AcquisitionProxy(exchange=exchange)

    listed = service.handle(
        message={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    )
    assert tuple(tool["name"] for tool in listed["result"]["tools"]) == _TOOLS

    refused = service.handle(
        message={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "read-file", "arguments": {}},
        }
    )
    assert refused == {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [{"type": "text", "text": '{"status":"refused","version":1}'}],
            "isError": False,
        },
    }
    assert exchange.calls == []
    assert executable.is_file()
    assert executable.stat().st_mode & 0o111
