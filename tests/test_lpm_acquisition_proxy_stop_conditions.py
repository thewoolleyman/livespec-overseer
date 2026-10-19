"""The proxy stops on a closed channel or a spent worker deadline, leaving nothing running.

Whatever ends the loop — the channel delivering no further frame, the worker
deadline passing, a malformed frame, an imposed step-limit, a result outside the
closed set or a channel that refuses one — every performer process the proxy's
ports started is stopped before the outcome is returned.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

_STARTING_TOOLS = frozenset({"start-terminal"})


class _Channel:
    def __init__(self, *, inbound: bytes, accepts: bool = True) -> None:
        self.inbound = inbound
        self.offset = 0
        self.accepts = accepts
        self.sent: list[bytes] = []
        self.closed = False

    def receive(self, *, count: int, timeout_seconds: float) -> bytes | None:
        assert timeout_seconds > 0
        chunk = self.inbound[self.offset : self.offset + count]
        if len(chunk) != count:
            return None
        self.offset += count
        return chunk

    def send(self, *, frame: bytes) -> bool:
        self.sent.append(frame)
        return self.accepts

    def close(self) -> None:
        self.closed = True


class _Performers:
    """A performer port that starts a process the proxy is obliged to stop."""

    def __init__(self, *, result: dict[str, object] | None = None) -> None:
        self.result = result if result is not None else {"version": 1, "status": "ok"}
        self.running_processes = 0
        self.shutdowns = 0

    def perform(self, *, tool: str, arguments: dict[str, object]) -> dict[str, object]:
        assert isinstance(arguments, dict)
        if tool in _STARTING_TOOLS:
            self.running_processes += 1
        return self.result

    def shutdown(self) -> None:
        self.shutdowns += 1
        self.running_processes = 0


class _AdvancingClock:
    """A clock that reads before the deadline the given number of times, then past it."""

    def __init__(self, *, readings_before_deadline: int) -> None:
        self.remaining = readings_before_deadline
        self.readings = 0

    def __call__(self) -> float:
        self.readings += 1
        if self.remaining > 0:
            self.remaining -= 1
            return 0.0
        return 2_000.0


def _results(*, channel: _Channel) -> list[dict[str, object]]:
    decoded: list[dict[str, object]] = []
    for frame in channel.sent:
        parsed: dict[str, object] = json.loads(frame[4:].decode("utf-8"))
        decoded.append(parsed)
    return decoded


def _served(
    *,
    proxy_module: ModuleType,
    channel: _Channel,
    performers: _Performers,
    clock: object = None,
    step_limit: int = 8,
) -> object:
    return proxy_module.private_acquisition_proxy(
        channel=channel,
        performers=performers,
        bounds=proxy_module.ExecutionBounds(
            step_limit=step_limit,
            allowed_origins=frozenset({"https://claude.com"}),
            tainted_values=frozenset(),
        ),
        worker_deadline=1_000.0,
        clock=clock if clock is not None else (lambda: 0.0),
    ).serve()


def _stop_conditions(
    *, requests: ModuleType
) -> Iterator[tuple[str, _Channel, _Performers, object]]:
    started = requests.frame_for(tool="start-terminal", arguments={})
    waited = requests.frame_for(tool="wait-browser", arguments={"seconds": 1})
    yield (
        "the channel delivers no further frame",
        _Channel(inbound=started),
        _Performers(),
        None,
    )
    yield (
        "the worker deadline passes mid-stream",
        _Channel(inbound=started + waited),
        _Performers(),
        _AdvancingClock(readings_before_deadline=1),
    )
    yield (
        "a malformed frame arrives",
        _Channel(inbound=started + requests.frame_for(tool="evaluate-javascript", arguments={})),
        _Performers(),
        None,
    )
    yield (
        "the cumulative step bound is reached",
        _Channel(inbound=started + waited),
        _Performers(),
        None,
    )
    yield (
        "a result outside the closed set arrives",
        _Channel(inbound=started),
        _Performers(result={"version": 1, "status": "ok", "pid": 4}),
        None,
    )
    yield (
        "the channel refuses the result",
        _Channel(inbound=started, accepts=False),
        _Performers(),
        None,
    )


def _assert_a_closed_channel_stops_the_loop(
    *, proxy_module: ModuleType, requests: ModuleType
) -> None:
    channel = _Channel(inbound=requests.frame_for(tool="start-terminal", arguments={}))
    performers = _Performers()
    outcome = _served(proxy_module=proxy_module, channel=channel, performers=performers)

    assert _results(channel=channel) == [{"version": 1, "status": "ok"}]
    assert outcome.stop_reason == "flow-unavailable"
    assert channel.closed is True


def _assert_a_spent_worker_deadline_stops_the_loop(
    *, proxy_module: ModuleType, requests: ModuleType
) -> None:
    clock = _AdvancingClock(readings_before_deadline=2)
    channel = _Channel(
        inbound=requests.frame_for(tool="start-terminal", arguments={})
        + requests.frame_for(tool="wait-browser", arguments={"seconds": 1})
        + requests.frame_for(tool="wait-terminal", arguments={"seconds": 1})
    )
    performers = _Performers()
    outcome = _served(
        proxy_module=proxy_module, channel=channel, performers=performers, clock=clock
    )

    assert len(channel.sent) == 2, "the deadline stops the loop with inbound frames still unread"
    assert clock.readings == 3
    assert outcome.stop_reason == "flow-unavailable"
    assert channel.closed is True


def test_the_proxy_stops_and_leaves_no_performer_process_running() -> None:
    proxy_module = importlib.import_module("_lpm_acquisition_proxy")
    requests = importlib.import_module("_lpm_browser_requests")
    assert (
        Path(__file__).parents[1] / "overseer" / "_lpm_acquisition_proxy.py"
    ).is_file(), "the private acquisition proxy service loop must be implemented"

    _assert_a_closed_channel_stops_the_loop(proxy_module=proxy_module, requests=requests)
    _assert_a_spent_worker_deadline_stops_the_loop(proxy_module=proxy_module, requests=requests)

    for description, channel, performers, clock in _stop_conditions(requests=requests):
        outcome = _served(
            proxy_module=proxy_module,
            channel=channel,
            performers=performers,
            clock=clock,
            step_limit=1,
        )

        assert performers.shutdowns == 1, (
            f"when {description} the proxy must stop its performer ports exactly once, "
            f"but shutdown ran {performers.shutdowns} times"
        )
        assert (
            performers.running_processes == 0
        ), f"when {description} no performer process the proxy started may be left running"
        assert channel.closed is True, f"when {description} the private channel must be closed"
        assert outcome.stop_reason in {"flow-unavailable", "step-limit"}
