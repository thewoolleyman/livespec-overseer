"""Private canonical browser-control framing, semantic refusal and call budgets."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final, cast

from _lpm_canonical import canonical_json_bytes, canonical_json_text, parse_canonical_json

__all__: list[str] = [
    "BrowserControl",
    "ControlOutcome",
    "frame_for",
]

_MAX_FRAME: Final = 16_777_216
_FRAME_PREFIX_BYTES: Final = 4
_MAX_REPETITION: Final = 3
_MAX_TEXT_BYTES: Final = 4096
_MAX_SCROLL_PIXELS: Final = 10_000
_MAX_WAIT_SECONDS: Final = 30
_HTTPS_ORIGIN: Final = re.compile(r"\Ahttps://[^/?#]+")
_REFUSED: Final = {"version": 1, "status": "refused"}
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
_MUTATIONS: Final = frozenset(
    {
        "navigate-browser",
        "click-browser",
        "type-browser-text",
        "select-browser",
        "scroll-browser",
        "start-terminal",
        "send-terminal-line",
        "send-terminal-handle",
        "terminate-terminal",
        "type-login-material",
        "apply-mailbox-verification",
        "capture-token",
        "discard-capture",
    }
)


@dataclass(frozen=True, kw_only=True)
class _Request:
    tool: str
    arguments: dict[str, object]


@dataclass(frozen=True, kw_only=True)
class ControlOutcome:
    """One secret-free response decision and any terminal execution signal."""

    response: dict[str, object] | None
    close_channel: bool
    stop_reason: str | None


@dataclass(kw_only=True)
class BrowserControl:
    """Invocation-scoped step and repetition accounting around private tool actions."""

    remaining_steps: int
    allowed_origins: frozenset[str]
    tainted_values: frozenset[str]
    perform: Callable[..., dict[str, object]]
    consumed_steps: int = field(default=0, init=False)
    browser_fingerprint: str | None = None
    terminal_digest: str | None = None
    _repetition_key: tuple[str, str | None, str | None] | None = field(
        default=None, init=False, repr=False
    )
    _repetition_count: int = field(default=0, init=False, repr=False)

    def dispatch(self, *, frame: bytes) -> ControlOutcome:
        """Validate and execute one frame without exposing an invalid request to action code."""
        request = _request_from_frame(frame=frame)
        if request is None:
            return ControlOutcome(response=None, close_channel=True, stop_reason="flow-unavailable")
        if self.consumed_steps >= self.remaining_steps:
            return _stopped_refusal()
        self.consumed_steps += 1
        if not _semantically_valid(
            request=request,
            allowed_origins=self.allowed_origins,
            tainted_values=self.tainted_values,
        ):
            return _ordinary_refusal()
        identity = canonical_json_text(
            value={"tool": request.tool, "arguments": request.arguments}
        ).unwrap()
        self._record_repetition(request=request, identity=identity)
        if self._repetition_count > _MAX_REPETITION:
            return _stopped_refusal()
        response = self.perform(tool=request.tool, arguments=request.arguments)
        return ControlOutcome(
            response=response,
            close_channel=False,
            stop_reason={"unavailable": "flow-unavailable"}.get(
                cast("str", response.get("status"))
            ),
        )

    def _record_repetition(self, *, request: _Request, identity: str) -> None:
        candidate = (identity, self.browser_fingerprint, self.terminal_digest)
        mutation = request.tool in _MUTATIONS
        same = candidate == self._repetition_key
        self._repetition_count = {
            (False, False): self._repetition_count,
            (False, True): self._repetition_count,
            (True, False): 1,
            (True, True): self._repetition_count + 1,
        }[(mutation, same)]
        self._repetition_key = {False: self._repetition_key, True: candidate}[mutation]


def frame_for(*, tool: str, arguments: dict[str, object]) -> bytes:
    """Encode one canonical request frame for the private proxy channel."""
    payload = canonical_json_bytes(
        value={"version": 1, "tool": tool, "arguments": arguments}
    ).unwrap()
    return len(payload).to_bytes(4, "big") + payload


def _request_from_frame(*, frame: bytes) -> _Request | None:
    declared = int.from_bytes(frame[:4], "big")
    payload = frame[_FRAME_PREFIX_BYTES:]
    text = payload.decode("utf-8", errors="surrogateescape")
    parsed = parse_canonical_json(text=text).value_or(None)
    canonical = canonical_json_bytes(value=parsed).value_or(b"")
    source = cast("dict[str, object]", parsed) if isinstance(parsed, dict) else {}
    tool = source.get("tool")
    arguments = source.get("arguments")
    signature = _SIGNATURES.get(tool) if isinstance(tool, str) else None
    typed_arguments = cast("dict[str, object]", arguments) if isinstance(arguments, dict) else {}
    if (
        len(frame) < _FRAME_PREFIX_BYTES
        or not 1 <= declared <= _MAX_FRAME
        or declared != len(payload)
        or payload != canonical
        or not isinstance(parsed, dict)
        or set(source) != {"version", "tool", "arguments"}
        or source.get("version") != 1
        or signature is None
        or not isinstance(arguments, dict)
        or set(typed_arguments) != set(signature)
        or not all(type(typed_arguments[name]) is expected for name, expected in signature.items())
    ):
        return None
    return _Request(tool=cast("str", tool), arguments=typed_arguments)


def _semantically_valid(
    *, request: _Request, allowed_origins: frozenset[str], tainted_values: frozenset[str]
) -> bool:
    arguments = request.arguments
    url = cast("str", arguments.get("url", ""))
    origin_match = _HTTPS_ORIGIN.match(url)
    origin = origin_match.group(0) if origin_match is not None else ""
    text = cast("str", arguments.get("text", arguments.get("value", "valid")))
    direction = cast("str", arguments.get("direction", "down"))
    pixels = cast("int", arguments.get("pixels", 1))
    seconds = cast("int", arguments.get("seconds", 1))
    field_name = cast("str", arguments.get("field", "login_identifier"))
    clean_text = (
        bool(text) and len(text.encode("utf-8")) <= _MAX_TEXT_BYTES and text not in tainted_values
    )
    checks = {
        "navigate-browser": origin in allowed_origins,
        "type-browser-text": clean_text,
        "select-browser": clean_text,
        "scroll-browser": direction in {"up", "down"} and 1 <= pixels <= _MAX_SCROLL_PIXELS,
        "wait-browser": 1 <= seconds <= _MAX_WAIT_SECONDS,
        "send-terminal-line": clean_text,
        "wait-terminal": 1 <= seconds <= _MAX_WAIT_SECONDS,
        "type-login-material": field_name in {"login_identifier", "login_secret"},
    }
    return checks.get(request.tool, True)


def _ordinary_refusal() -> ControlOutcome:
    return ControlOutcome(response=dict(_REFUSED), close_channel=False, stop_reason=None)


def _stopped_refusal() -> ControlOutcome:
    return ControlOutcome(response=dict(_REFUSED), close_channel=False, stop_reason="step-limit")
