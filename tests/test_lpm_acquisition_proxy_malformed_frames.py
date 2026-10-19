"""A malformed private-channel frame closes the channel and fails flow-unavailable.

Every framing, encoding, structural and tool-identity defect belongs to one class:
the proxy returns no result, reaches no performer, consumes no step, closes its
endpoint and ends the acquisition as flow-unavailable.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

_OVERSIZED_PAYLOAD_LENGTH = 16_777_217


class _Channel:
    def __init__(self, *, inbound: bytes) -> None:
        self.inbound = inbound
        self.offset = 0
        self.sent: list[bytes] = []
        self.reads: list[int] = []
        self.closed = False

    def receive(self, *, count: int, timeout_seconds: float) -> bytes | None:
        self.reads.append(count)
        assert timeout_seconds > 0
        chunk = self.inbound[self.offset : self.offset + count]
        if len(chunk) != count:
            return None
        self.offset += count
        return chunk

    def send(self, *, frame: bytes) -> bool:
        self.sent.append(frame)
        return True

    def close(self) -> None:
        self.closed = True


class _Performers:
    def __init__(self) -> None:
        self.actions: list[tuple[str, dict[str, object]]] = []

    def perform(self, *, tool: str, arguments: dict[str, object]) -> dict[str, object]:
        self.actions.append((tool, arguments))
        return {"version": 1, "status": "ok"}

    def shutdown(self) -> None:
        return None


def _framed(*, payload: bytes) -> bytes:
    return len(payload).to_bytes(4, "big") + payload


def _malformed_frames(*, requests: ModuleType) -> tuple[tuple[str, bytes], ...]:
    return (
        ("the channel delivered nothing at all", b""),
        ("a truncated length prefix", b"\x00\x00\x00"),
        ("a zero payload length", b"\x00\x00\x00\x00"),
        (
            "an oversized payload length",
            _OVERSIZED_PAYLOAD_LENGTH.to_bytes(4, "big") + b"{}",
        ),
        (
            "a truncated payload",
            requests.frame_for(tool="wait-browser", arguments={"seconds": 1})[:-1],
        ),
        ("invalid UTF-8", _framed(payload=b"\xff")),
        ("a non-object payload", _framed(payload=b"[]")),
        (
            "noncanonical member order",
            _framed(payload=b'{"tool":"wait-browser","version":1,"arguments":{"seconds":1}}'),
        ),
        (
            "insignificant whitespace",
            _framed(payload=b'{"arguments": {"seconds": 1}, "tool": "wait-browser", "version": 1}'),
        ),
        (
            "a duplicate member name",
            _framed(
                payload=b'{"arguments":{"seconds":1},"tool":"wait-browser",'
                b'"tool":"wait-browser","version":1}'
            ),
        ),
        (
            "a missing version member",
            _framed(payload=b'{"arguments":{"seconds":1},"tool":"wait-browser"}'),
        ),
        ("an unregistered tool name", requests.frame_for(tool="evaluate-javascript", arguments={})),
        (
            "a wrongly typed argument",
            requests.frame_for(tool="wait-browser", arguments={"seconds": True}),
        ),
        (
            "an extra argument member",
            requests.frame_for(tool="wait-browser", arguments={"seconds": 1, "extra": 2}),
        ),
        (
            "a missing argument member",
            requests.frame_for(tool="wait-browser", arguments={}),
        ),
    )


def _served(*, proxy_module: ModuleType, inbound: bytes) -> tuple[object, _Channel, _Performers]:
    channel = _Channel(inbound=inbound)
    performers = _Performers()
    outcome = proxy_module.private_acquisition_proxy(
        channel=channel,
        performers=performers,
        bounds=proxy_module.ExecutionBounds(
            step_limit=8,
            allowed_origins=frozenset({"https://claude.com"}),
            tainted_values=frozenset(),
        ),
        worker_deadline=1_000.0,
        clock=lambda: 0.0,
    ).serve()
    return outcome, channel, performers


def _assert_no_oversized_payload_is_ever_requested(*, proxy_module: ModuleType) -> None:
    for inbound in (
        b"\x00\x00\x00\x00",
        _OVERSIZED_PAYLOAD_LENGTH.to_bytes(4, "big") + b"{}",
    ):
        _, channel, _ = _served(proxy_module=proxy_module, inbound=inbound)
        assert channel.reads == [4], (
            "an out-of-bound payload length must be refused from the prefix alone, "
            f"but the proxy went on to request {channel.reads[1:]}"
        )


def _assert_a_valid_frame_still_closes_the_channel_when_the_loop_stops(
    *, proxy_module: ModuleType, requests: ModuleType
) -> None:
    outcome, channel, performers = _served(
        proxy_module=proxy_module,
        inbound=requests.frame_for(tool="wait-browser", arguments={"seconds": 1}),
    )

    assert performers.actions == [("wait-browser", {"seconds": 1})]
    assert len(channel.sent) == 1
    assert channel.closed is True
    assert outcome.consumed_steps == 1


def test_a_malformed_frame_closes_the_channel_without_a_result_action_or_step() -> None:
    proxy_module = importlib.import_module("_lpm_acquisition_proxy")
    requests = importlib.import_module("_lpm_browser_requests")
    assert (
        Path(__file__).parents[1] / "overseer" / "_lpm_acquisition_proxy.py"
    ).is_file(), "the private acquisition proxy service loop must be implemented"

    for description, inbound in _malformed_frames(requests=requests):
        outcome, channel, performers = _served(proxy_module=proxy_module, inbound=inbound)

        assert channel.sent == [], f"{description} must return no result"
        assert performers.actions == [], f"{description} must reach no performer"
        assert outcome.consumed_steps == 0, f"{description} must consume no step"
        assert channel.closed is True, f"{description} must close the private channel"
        assert (
            outcome.stop_reason == "flow-unavailable"
        ), f"{description} must fail flow-unavailable"

    _assert_no_oversized_payload_is_ever_requested(proxy_module=proxy_module)
    _assert_a_valid_frame_still_closes_the_channel_when_the_loop_stops(
        proxy_module=proxy_module, requests=requests
    )
