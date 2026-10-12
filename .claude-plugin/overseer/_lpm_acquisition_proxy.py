"""Closed MCP surface for the acquisition execution role."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Protocol, cast

from _lpm_canonical import canonical_json_text

__all__: list[str] = [
    "REGISTERED_TOOLS",
    "AcquisitionProxy",
]

_SIGNATURES: Final[dict[str, dict[str, str]]] = {
    "observe-browser": {},
    "navigate-browser": {"url": "string"},
    "click-browser": {"element_handle": "string"},
    "type-browser-text": {"text": "string", "element_handle": "string"},
    "select-browser": {"value": "string", "element_handle": "string"},
    "scroll-browser": {"direction": "string", "pixels": "integer"},
    "wait-browser": {"seconds": "integer"},
    "start-terminal": {},
    "observe-terminal": {},
    "send-terminal-line": {"text": "string"},
    "send-terminal-handle": {"source_handle": "string"},
    "wait-terminal": {"seconds": "integer"},
    "terminate-terminal": {},
    "type-login-material": {"field": "string", "element_handle": "string"},
    "apply-mailbox-verification": {"element_handle": "string"},
    "capture-token": {"source_handle": "string"},
    "discard-capture": {"capture_handle": "string"},
}
REGISTERED_TOOLS: Final = tuple(_SIGNATURES)


class Exchange(Protocol):
    def __call__(self, *, tool: str, arguments: dict[str, object]) -> dict[str, object]: ...


def _tool_definition(*, name: str) -> dict[str, object]:
    signature = _SIGNATURES[name]
    return {
        "name": name,
        "description": f"Private acquisition operation: {name}.",
        "inputSchema": {
            "type": "object",
            "properties": {
                member: {"type": value_type} for member, value_type in signature.items()
            },
            "required": list(signature),
            "additionalProperties": False,
        },
    }


def _refused(*, request_id: object) -> dict[str, object]:
    result: dict[str, object] = {"version": 1, "status": "refused"}
    return _tool_result(request_id=request_id, result=result)


def _tool_result(*, request_id: object, result: dict[str, object]) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": canonical_json_text(value=result).unwrap()}],
            "isError": False,
        },
    }


@dataclass(kw_only=True)
class AcquisitionProxy:
    """One MCP server whose only effects cross the framed private channel."""

    exchange: Exchange

    def handle(self, *, message: dict[str, object]) -> dict[str, object]:
        """List the closed surface or refuse a call before any performer is reached."""
        if message.get("method") == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {"tools": [_tool_definition(name=name) for name in REGISTERED_TOOLS]},
            }
        params = cast("dict[str, object]", message.get("params", {}))
        name = cast("str", params.get("name", ""))
        if message.get("method") == "tools/call" and name in REGISTERED_TOOLS:
            arguments = cast("dict[str, object]", params.get("arguments", {}))
            result = self.exchange(tool=name, arguments=arguments)
            return _tool_result(request_id=message.get("id"), result=result)
        return _refused(request_id=message.get("id"))
