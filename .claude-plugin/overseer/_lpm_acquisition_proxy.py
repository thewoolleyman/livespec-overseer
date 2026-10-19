"""Private acquisition proxy service loop over its inherited browser-control channel.

The proxy owns no CDP, terminal, vault, keyring, capture or taint state. It reads
one canonical request frame at a time from its private channel, hands the whole
frame to the browser-control boundary that owns every semantic, cumulative-step and
repetition bound, and returns only that boundary's closed secret-free result.

Both the private channel and the browser and terminal performers are INJECTED
ports. No module in this family may import a transport at all, so the AF_UNIX
stream endpoint the worker installs as descriptor 3 is adapted outside it and
handed in; this loop can therefore reach nothing it was not given.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from _lpm_browser_control import BrowserControl
from _lpm_browser_requests import (
    FRAME_PREFIX_BYTES,
    MAX_FRAME_PAYLOAD_BYTES,
    PRIVATE_EXECUTION_TOOLS,
    response_frame_for,
)
from _lpm_observations import ObservationOutcome
from _lpm_proxy_results import closed_result

__all__: list[str] = [
    "PRIVATE_EXECUTION_TOOLS",
    "AcquisitionProxy",
    "ExecutionBounds",
    "ProxyOutcome",
    "private_acquisition_proxy",
]


class PrivateChannel(Protocol):
    def receive(self, *, count: int, timeout_seconds: float) -> bytes | None:
        """Return exactly count bytes in time, or nothing when the channel cannot."""
        ...

    def send(self, *, frame: bytes) -> bool:
        """Write one whole frame, reporting whether the channel accepted it."""
        ...

    def close(self) -> None:
        """Close this endpoint of the private channel."""
        ...


class ExecutionPerformers(Protocol):
    def perform(
        self, *, tool: str, arguments: dict[str, object]
    ) -> dict[str, object] | ObservationOutcome:
        """Perform one already-validated private execution action."""
        ...

    def shutdown(self) -> None:
        """Stop and reap every performer process these ports started."""
        ...


class Clock(Protocol):
    def __call__(self) -> float:
        """Return the current absolute time the worker deadline is measured against."""
        ...


@dataclass(frozen=True, kw_only=True)
class ExecutionBounds:
    """The browser-control bounds one execution invocation is admitted under."""

    step_limit: int
    allowed_origins: frozenset[str]
    tainted_values: frozenset[str]


@dataclass(frozen=True, kw_only=True)
class ProxyOutcome:
    """One terminal private-proxy service outcome and its closed stop reason."""

    stop_reason: str
    consumed_steps: int


@dataclass(kw_only=True)
class AcquisitionProxy:
    """Serve exactly the seventeen private execution tools over one private channel."""

    channel: PrivateChannel
    performers: ExecutionPerformers
    control: BrowserControl
    worker_deadline: float
    clock: Clock

    def serve(self) -> ProxyOutcome:
        """Serve requests until a stop condition ends the loop, leaving nothing running."""
        try:
            return self._serve_frames()
        finally:
            self.performers.shutdown()
            self.channel.close()

    def _serve_frames(self) -> ProxyOutcome:
        while True:
            remaining = self.worker_deadline - self.clock()
            if remaining <= 0:
                return self._stopped(reason="flow-unavailable")
            frame = self._next_frame(timeout_seconds=remaining)
            if frame is None:
                return self._stopped(reason="flow-unavailable")
            outcome = self.control.dispatch(frame=frame)
            if outcome.response is None:
                return self._stopped(reason="flow-unavailable")
            result = closed_result(response=outcome.response)
            if result is None:
                return self._stopped(reason="flow-unavailable")
            if not self.channel.send(frame=response_frame_for(response=result)):
                return self._stopped(reason="flow-unavailable")
            if outcome.stop_reason is not None:
                return self._stopped(reason=outcome.stop_reason)

    def _next_frame(self, *, timeout_seconds: float) -> bytes | None:
        prefix = self.channel.receive(count=FRAME_PREFIX_BYTES, timeout_seconds=timeout_seconds)
        if prefix is None:
            return None
        declared = int.from_bytes(prefix, "big")
        if not 1 <= declared <= MAX_FRAME_PAYLOAD_BYTES:
            return None
        payload = self.channel.receive(count=declared, timeout_seconds=timeout_seconds)
        return None if payload is None else prefix + payload

    def _stopped(self, *, reason: str) -> ProxyOutcome:
        return ProxyOutcome(stop_reason=reason, consumed_steps=self.control.consumed_steps)


def private_acquisition_proxy(
    *,
    channel: PrivateChannel,
    performers: ExecutionPerformers,
    bounds: ExecutionBounds,
    worker_deadline: float,
    clock: Clock,
) -> AcquisitionProxy:
    """Compose one proxy over its private channel and its injected performer ports."""
    return AcquisitionProxy(
        channel=channel,
        performers=performers,
        control=BrowserControl(
            step_limit=bounds.step_limit,
            allowed_origins=bounds.allowed_origins,
            tainted_values=bounds.tainted_values,
            perform=performers.perform,
        ),
        worker_deadline=worker_deadline,
        clock=clock,
    )
