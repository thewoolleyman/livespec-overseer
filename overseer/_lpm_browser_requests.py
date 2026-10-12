"""Canonical browser-control request framing and value-level refusal checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, cast

from _lpm_canonical import canonical_json_bytes, parse_canonical_json

__all__: list[str] = [
    "BrowserRequest",
    "browser_request_allowed",
    "browser_request_from_frame",
    "frame_for",
]

_FRAME_PREFIX_BYTES: Final = 4
_MAX_FRAME: Final = 16_777_216
_MAX_SCROLL_PIXELS: Final = 10_000
_MAX_TEXT_BYTES: Final = 4096
_MAX_WAIT_SECONDS: Final = 30
_TOKEN: Final = re.compile(r"sk-ant-oat01-[A-Za-z0-9_-]+")
_HTTPS_URL: Final = re.compile(r"\A(https://([^/?#]+))(?:[/?#].*)?\Z")
_SOURCE_HANDLE: Final = re.compile(
    r"\A(?:browser|terminal):[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)
_SIGNATURES: Final[dict[str, dict[str, type[object]]]] = {
    "observe-browser": {},
    "navigate-browser": {"url": str},
    "click-browser": {"element_handle": str},
    "type-browser-text": {"text": str, "element_handle": str},
    "select-browser": {"value": str, "element_handle": str},
    "scroll-browser": {"direction": str, "pixels": int},
    "wait-browser": {"seconds": int},
    "start-terminal": {},
    "observe-terminal": {},
    "send-terminal-line": {"text": str},
    "send-terminal-handle": {"source_handle": str},
    "wait-terminal": {"seconds": int},
    "terminate-terminal": {},
    "type-login-material": {"field": str, "element_handle": str},
    "apply-mailbox-verification": {"element_handle": str},
    "capture-token": {"source_handle": str},
    "discard-capture": {"capture_handle": str},
}


@dataclass(frozen=True, kw_only=True)
class BrowserRequest:
    """One structurally closed tool request."""

    tool: str
    arguments: dict[str, object]


def frame_for(*, tool: str, arguments: dict[str, object]) -> bytes:
    """Encode one canonical request frame for the private proxy channel."""
    payload = canonical_json_bytes(
        value={"version": 1, "tool": tool, "arguments": arguments}
    ).unwrap()
    return len(payload).to_bytes(_FRAME_PREFIX_BYTES, "big") + payload


def browser_request_from_frame(*, frame: bytes) -> BrowserRequest | None:
    """Return a request only after the complete frame and canonical object validate."""
    declared = (
        int.from_bytes(frame[:_FRAME_PREFIX_BYTES], "big")
        if len(frame) >= _FRAME_PREFIX_BYTES
        else 0
    )
    payload = frame[_FRAME_PREFIX_BYTES:] if len(frame) >= _FRAME_PREFIX_BYTES else b""
    if not 1 <= declared <= _MAX_FRAME or declared != len(payload):
        return None
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return None
    parsed = parse_canonical_json(text=text).value_or(None)
    canonical = canonical_json_bytes(value=parsed).value_or(b"")
    canonical_values: dict[bool, object] = {True: parsed}
    value = canonical_values.get(payload == canonical, {})
    typed_objects: dict[type[object], object] = {dict: value}
    source = cast("dict[str, object]", typed_objects.get(type(value), {}))
    tool = source.get("tool")
    arguments = source.get("arguments")
    signature = _SIGNATURES.get(tool) if isinstance(tool, str) else None
    if signature is None or not isinstance(arguments, dict):
        return None
    typed = cast("dict[str, object]", arguments)
    if (
        set(source) != {"version", "tool", "arguments"}
        or source.get("version") != 1
        or set(typed) != set(signature)
        or any(type(typed[name]) is not expected for name, expected in signature.items())
    ):
        return None
    return BrowserRequest(tool=cast("str", tool), arguments=typed)


def browser_request_allowed(
    *, request: BrowserRequest, allowed_origins: frozenset[str], tainted_values: frozenset[str]
) -> bool:
    """Apply every closed value-level rule without performing an action."""
    values = request.arguments
    text = cast("str", values.get("text", values.get("value", "valid")))
    clean = (
        bool(text)
        and len(text.encode("utf-8")) <= _MAX_TEXT_BYTES
        and _TOKEN.search(text) is None
        and not any(value and value in text for value in tainted_values)
    )
    handle = cast("str", values.get("element_handle", "valid"))
    source_handle = cast(
        "str",
        values.get("source_handle", "browser:00000000-0000-4000-8000-000000000000"),
    )
    checks = {
        "navigate-browser": _allowed_url(
            url=cast("str", values.get("url", "")), allowed_origins=allowed_origins
        ),
        "click-browser": bool(handle),
        "type-browser-text": clean and bool(handle),
        "select-browser": clean and bool(handle),
        "scroll-browser": values.get("direction") in {"up", "down"}
        and 1 <= cast("int", values.get("pixels", 0)) <= _MAX_SCROLL_PIXELS,
        "wait-browser": 1 <= cast("int", values.get("seconds", 0)) <= _MAX_WAIT_SECONDS,
        "send-terminal-line": clean,
        "send-terminal-handle": _SOURCE_HANDLE.match(source_handle) is not None,
        "wait-terminal": 1 <= cast("int", values.get("seconds", 0)) <= _MAX_WAIT_SECONDS,
        "type-login-material": values.get("field") in {"login_identifier", "login_secret"}
        and bool(handle),
        "apply-mailbox-verification": bool(handle),
        "capture-token": _SOURCE_HANDLE.match(source_handle) is not None,
        "discard-capture": bool(cast("str", values.get("capture_handle", ""))),
    }
    return checks.get(request.tool, True)


def _allowed_url(*, url: str, allowed_origins: frozenset[str]) -> bool:
    matched = _HTTPS_URL.match(url)
    if matched is None or "@" in matched.group(2) or any(char.isspace() for char in url):
        return False
    return matched.group(1) in allowed_origins
