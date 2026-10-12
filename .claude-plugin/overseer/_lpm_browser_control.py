"""Canonical private browser-control framing, semantic refusals and call budgets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Protocol, cast

from _lpm_browser_requests import (
    browser_request_allowed,
    browser_request_from_frame,
    frame_for,
)
from _lpm_canonical import canonical_json_text
from _lpm_observations import ObservationOutcome

__all__: list[str] = [
    "BrowserControl",
    "ControlOutcome",
    "frame_for",
]

_MAX_REPETITION: Final = 3
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


class ActionPerformer(Protocol):
    def __call__(
        self, *, tool: str, arguments: dict[str, object]
    ) -> dict[str, object] | ObservationOutcome:
        """Perform one already-validated private action."""
        ...


@dataclass(frozen=True, kw_only=True)
class ControlOutcome:
    """One secret-free response decision and terminal execution signal."""

    response: dict[str, object] | None
    close_channel: bool
    stop_reason: str | None


@dataclass(kw_only=True)
class BrowserControl:
    """Invocation-scoped cumulative and repeated-action accounting."""

    step_limit: int
    allowed_origins: frozenset[str]
    tainted_values: frozenset[str]
    perform: ActionPerformer
    consumed_steps: int = field(default=0, init=False)
    browser_fingerprint: str | None = field(default=None, init=False)
    terminal_fingerprint: str | None = field(default=None, init=False)
    _repeat_key: tuple[str, str | None, str | None] | None = field(
        default=None, init=False, repr=False
    )
    _repeat_count: int = field(default=0, init=False, repr=False)

    def dispatch(self, *, frame: bytes) -> ControlOutcome:
        """Validate a whole frame before exposing its request to action code."""
        request = browser_request_from_frame(frame=frame)
        if request is None:
            return ControlOutcome(response=None, close_channel=True, stop_reason="flow-unavailable")
        if self.consumed_steps >= self.step_limit:
            return _stopped_refusal()
        self.consumed_steps += 1
        if not browser_request_allowed(
            request=request,
            allowed_origins=self.allowed_origins,
            tainted_values=self.tainted_values,
        ):
            return _ordinary_refusal()
        identity = canonical_json_text(
            value={"tool": request.tool, "arguments": request.arguments}
        ).unwrap()
        candidate = (identity, self.browser_fingerprint, self.terminal_fingerprint)
        next_count = self._repeat_count + 1 if candidate == self._repeat_key else 1
        if request.tool in _MUTATIONS and next_count > _MAX_REPETITION:
            return _stopped_refusal()
        performed = self.perform(tool=request.tool, arguments=request.arguments)
        if isinstance(performed, ObservationOutcome):
            response = performed.response
            observed_fingerprint = performed.fingerprint
        else:
            response = performed
            observed_fingerprint = None
        if response.get("status") == "refused":
            return ControlOutcome(response=response, close_channel=False, stop_reason=None)
        if request.tool in _MUTATIONS:
            self._repeat_key = candidate
            self._repeat_count = next_count
        self._accept_observed_state(
            tool=request.tool,
            response=response,
            observed_fingerprint=observed_fingerprint,
        )
        return ControlOutcome(
            response=response,
            close_channel=False,
            stop_reason={"unavailable": "flow-unavailable"}.get(
                cast("str", response.get("status"))
            ),
        )

    def _accept_observed_state(
        self, *, tool: str, response: dict[str, object], observed_fingerprint: str | None
    ) -> None:
        before = (self.browser_fingerprint, self.terminal_fingerprint)
        browser = response.get("state_fingerprint")
        if tool == "observe-browser" and isinstance(browser, str) and browser:
            self.browser_fingerprint = browser
        if tool == "observe-terminal" and observed_fingerprint:
            self.terminal_fingerprint = observed_fingerprint
        if before != (self.browser_fingerprint, self.terminal_fingerprint):
            self._repeat_key = None
            self._repeat_count = 0


def _ordinary_refusal() -> ControlOutcome:
    return ControlOutcome(
        response={"version": 1, "status": "refused"},
        close_channel=False,
        stop_reason=None,
    )


def _stopped_refusal() -> ControlOutcome:
    return ControlOutcome(
        response={"version": 1, "status": "refused"},
        close_channel=False,
        stop_reason="step-limit",
    )
