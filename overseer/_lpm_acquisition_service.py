"""Private framed acquisition service composed over an injected performer port."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol, cast

from _lpm_browser_control import BrowserControl
from _lpm_canonical import canonical_json_bytes
from _lpm_observations import ObservationOutcome, ObservationSanitizer

__all__: list[str] = [
    "AcquisitionProxyService",
    "ServiceOutcome",
]


class ActionPerformer(Protocol):
    def __call__(self, *, tool: str, arguments: dict[str, object]) -> dict[str, object]:
        """Perform one already-validated acquisition action."""
        ...


class PrivateChannel(Protocol):
    def receive(self, *, deadline: float) -> bytes | None:
        """Receive one complete private-channel frame."""
        ...

    def send(self, *, frame: bytes, deadline: float) -> None:
        """Send one complete private-channel frame."""
        ...

    def close(self) -> None:
        """Close the private channel."""
        ...


@dataclass(frozen=True, kw_only=True)
class ServiceOutcome:
    """Terminal outcome of one private-channel service run."""

    status: str
    failure_reason: str | None


@dataclass(kw_only=True)
class _TokenVault:
    values: dict[str, str]
    source: str

    def __call__(self, *, value: str) -> str:
        handle = f"{self.source}:{uuid.uuid4()}"
        self.values[handle] = value
        return handle


@dataclass(kw_only=True)
class AcquisitionProxyService:
    """Own private request validation and cumulative invocation state."""

    step_limit: int
    allowed_origins: frozenset[str]
    tainted_values: frozenset[str]
    perform: ActionPerformer
    _control: BrowserControl = field(init=False, repr=False)
    _browser_sanitizer: ObservationSanitizer = field(init=False, repr=False)
    _terminal_sanitizer: ObservationSanitizer = field(init=False, repr=False)

    def __post_init__(self) -> None:
        token_values: dict[str, str] = {}
        self._browser_sanitizer = ObservationSanitizer(
            token_handles=token_values,
            sensitive_values=self.tainted_values,
            new_token_handle=_TokenVault(values=token_values, source="browser"),
        )
        self._terminal_sanitizer = ObservationSanitizer(
            token_handles=token_values,
            sensitive_values=self.tainted_values,
            new_token_handle=_TokenVault(values=token_values, source="terminal"),
        )
        self._control = BrowserControl(
            step_limit=self.step_limit,
            allowed_origins=self.allowed_origins,
            tainted_values=self.tainted_values,
            perform=self._perform_safely,
        )

    @property
    def consumed_steps(self) -> int:
        """Return the invocation-wide consumed-step count."""
        return self._control.consumed_steps

    def run(self, *, channel: PrivateChannel, deadline: float) -> ServiceOutcome:
        """Serve private frames until channel or browser-control termination."""
        result = self._serve(channel=channel, deadline=deadline)
        channel.close()
        return result

    def _serve(self, *, channel: PrivateChannel, deadline: float) -> ServiceOutcome:
        while True:
            frame = channel.receive(deadline=deadline)
            if frame is None:
                return ServiceOutcome(status="stopped", failure_reason=None)
            outcome = self._control.dispatch(frame=frame)
            if outcome.close_channel:
                return ServiceOutcome(status="failed", failure_reason=outcome.stop_reason)
            response = cast("dict[str, object]", outcome.response)
            channel.send(frame=_response_frame(response=response), deadline=deadline)
            if outcome.stop_reason is not None:
                return ServiceOutcome(status="failed", failure_reason=outcome.stop_reason)

    def _perform_safely(
        self, *, tool: str, arguments: dict[str, object]
    ) -> dict[str, object] | ObservationOutcome:
        result = self.perform(tool=tool, arguments=arguments)
        if tool == "observe-browser":
            return self._browser_sanitizer.browser_observation(
                url=cast("str", result["url"]),
                title=cast("str", result["title"]),
                dom_text=cast("str", result["dom_text"]),
                accessibility_tree=cast("str", result["accessibility_tree"]),
                masked_screenshot_png=cast("bytes", result["masked_screenshot_png"]),
                masking_established=cast("bool", result["masking_established"]),
            )
        if tool == "observe-terminal":
            return self._terminal_sanitizer.terminal_observation(
                running=cast("bool", result["running"]),
                exit_status=cast("int | None", result["exit_status"]),
                stdout=cast("str", result["stdout"]),
                stderr=cast("str", result["stderr"]),
            )
        return result


def _response_frame(*, response: dict[str, object]) -> bytes:
    payload = canonical_json_bytes(value=response).unwrap()
    return len(payload).to_bytes(4, "big") + payload
