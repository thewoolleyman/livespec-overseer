"""Private framed acquisition service composed over an injected performer port."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from _lpm_browser_control import BrowserControl
from _lpm_observations import ObservationOutcome

__all__: list[str] = [
    "AcquisitionProxyService",
    "ServiceOutcome",
]


class ActionPerformer(Protocol):
    def __call__(
        self, *, tool: str, arguments: dict[str, object]
    ) -> dict[str, object] | ObservationOutcome:
        """Perform one already-validated acquisition action."""
        ...


class PrivateChannel(Protocol):
    def receive(self, *, deadline: float) -> bytes:
        """Receive one complete private-channel frame."""
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
class AcquisitionProxyService:
    """Own private request validation and cumulative invocation state."""

    step_limit: int
    allowed_origins: frozenset[str]
    tainted_values: frozenset[str]
    perform: ActionPerformer
    _control: BrowserControl = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._control = BrowserControl(
            step_limit=self.step_limit,
            allowed_origins=self.allowed_origins,
            tainted_values=self.tainted_values,
            perform=self.perform,
        )

    @property
    def consumed_steps(self) -> int:
        """Return the invocation-wide consumed-step count."""
        return self._control.consumed_steps

    def run(self, *, channel: PrivateChannel, deadline: float) -> ServiceOutcome:
        """Close a malformed private frame without emitting any result."""
        outcome = self._control.dispatch(frame=channel.receive(deadline=deadline))
        channel.close()
        return ServiceOutcome(status="failed", failure_reason=outcome.stop_reason)
