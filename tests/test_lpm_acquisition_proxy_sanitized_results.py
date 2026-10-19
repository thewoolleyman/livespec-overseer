"""Proxy responses carry only sanitized observation output and opaque handles.

Observations reach the channel only as the observation sanitizer built them, so a
registered secret appears solely as its marker; a local-tool result outside the
closed secret-free set produces no proxy result at all; and an observation whose
masking cannot be established returns exactly unavailable.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType

_TOKEN = "sk-ant-oat01-registered"
_SECRET = "concealed-login-identifier"
_TOKEN_HANDLE = "browser:123e4567-e89b-12d3-a456-426614174000"
_SENSITIVE_MARKER = "[[redacted-sensitive]]"
_UNAVAILABLE = {"version": 1, "status": "unavailable"}
_CAPTURE_HANDLE = "capture:9f2b"
_NOT_CLOSED_RESULTS: tuple[tuple[str, dict[str, object]], ...] = (
    ("an unregistered status", {"version": 1, "status": "done"}),
    ("a wrong version", {"version": 2, "status": "ok"}),
    ("a boolean version", {"version": True, "status": "ok"}),
    ("a missing version", {"status": "ok"}),
    ("a non-string status", {"version": 1, "status": 1}),
    ("an extra member beside ok", {"version": 1, "status": "ok", "detail": "fine"}),
    ("a raw token smuggled beside ok", {"version": 1, "status": "ok", "token": _TOKEN}),
    ("a capture with no handle", {"version": 1, "status": "captured"}),
    ("a capture with an empty handle", {"version": 1, "status": "captured", "capture_handle": ""}),
    (
        "a capture handing back the sensitive marker",
        {"version": 1, "status": "captured", "capture_handle": _SENSITIVE_MARKER},
    ),
    (
        "a capture with a non-string handle",
        {"version": 1, "status": "captured", "capture_handle": 7},
    ),
    (
        "a browser observation missing its fingerprint",
        {
            "version": 1,
            "status": "ok",
            "url": "https://claude.com/",
            "title": "t",
            "dom_text": "d",
            "accessibility_tree": "a",
            "screenshot_png": "cG5n",
        },
    ),
    (
        "a browser observation with a non-string field",
        {
            "version": 1,
            "status": "ok",
            "url": "https://claude.com/",
            "title": "t",
            "dom_text": "d",
            "accessibility_tree": "a",
            "screenshot_png": "cG5n",
            "state_fingerprint": 1,
        },
    ),
    (
        "a terminal observation with a non-boolean running",
        {
            "version": 1,
            "status": "ok",
            "running": "yes",
            "exit_status": None,
            "stdout": "",
            "stderr": "",
        },
    ),
    (
        "a terminal observation with a non-integer exit status",
        {
            "version": 1,
            "status": "ok",
            "running": False,
            "exit_status": "0",
            "stdout": "",
            "stderr": "",
        },
    ),
    (
        "a terminal observation with non-string streams",
        {
            "version": 1,
            "status": "ok",
            "running": False,
            "exit_status": 0,
            "stdout": 0,
            "stderr": "",
        },
    ),
)
_CLOSED_RESULTS: tuple[dict[str, object], ...] = (
    {"version": 1, "status": "ok"},
    {"version": 1, "status": "applied"},
    {"version": 1, "status": "not-found"},
    {"version": 1, "status": "unavailable"},
    {"version": 1, "status": "captured", "capture_handle": _CAPTURE_HANDLE},
)


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


class _FixedPerformers:
    def __init__(self, *, result: object) -> None:
        self.result = result
        self.calls = 0

    def perform(self, *, tool: str, arguments: dict[str, object]) -> object:
        self.calls += 1
        assert tool
        assert isinstance(arguments, dict)
        return self.result

    def shutdown(self) -> None:
        return None


class _ObservingPerformers:
    def __init__(self, *, observations: ModuleType, masking_established: bool) -> None:
        self.masking_established = masking_established
        self.sanitizer = observations.ObservationSanitizer(
            token_handles={_TOKEN_HANDLE: _TOKEN},
            sensitive_values=frozenset({_SECRET}),
            new_token_handle=lambda *, value: _TOKEN_HANDLE,
        )

    def perform(self, *, tool: str, arguments: dict[str, object]) -> object:
        assert isinstance(arguments, dict)
        if tool == "observe-terminal":
            return self.sanitizer.terminal_observation(
                running=False,
                exit_status=0,
                stdout=f"logged in as {_SECRET}\n",
                stderr=f"token {_TOKEN}\n",
            )
        return self.sanitizer.browser_observation(
            url=f"https://claude.com/?who={_SECRET}",
            title=f"console for {_SECRET}",
            dom_text=f"value {_TOKEN} shown",
            accessibility_tree=f"field {_SECRET}",
            masked_screenshot_png=b"masked-png",
            masking_established=self.masking_established,
        )

    def shutdown(self) -> None:
        return None


def _results(*, channel: _Channel) -> list[dict[str, object]]:
    decoded: list[dict[str, object]] = []
    for frame in channel.sent:
        parsed: dict[str, object] = json.loads(frame[4:].decode("utf-8"))
        decoded.append(parsed)
    return decoded


def _served(*, proxy_module: ModuleType, channel: _Channel, performers: object) -> object:
    return proxy_module.private_acquisition_proxy(
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


def _assert_observations_reach_the_channel_only_as_the_sanitizer_built_them(
    *, proxy_module: ModuleType, requests: ModuleType, observations: ModuleType
) -> None:
    channel = _Channel(
        inbound=requests.frame_for(tool="observe-browser", arguments={})
        + requests.frame_for(tool="observe-terminal", arguments={})
    )
    outcome = _served(
        proxy_module=proxy_module,
        channel=channel,
        performers=_ObservingPerformers(observations=observations, masking_established=True),
    )

    browser, terminal = _results(channel=channel)
    serialized = json.dumps([browser, terminal])
    assert _SECRET not in serialized, "a registered sensitive value must never reach the channel"
    assert _TOKEN not in serialized, "a provider token must never reach the channel"
    assert browser["url"] == f"https://claude.com/?who={_SENSITIVE_MARKER}"
    assert browser["title"] == f"console for {_SENSITIVE_MARKER}"
    assert browser["dom_text"] == f"value [[redacted-token:{_TOKEN_HANDLE}]] shown"
    assert browser["accessibility_tree"] == f"field {_SENSITIVE_MARKER}"
    assert set(browser) == {
        "version",
        "status",
        "url",
        "title",
        "dom_text",
        "accessibility_tree",
        "screenshot_png",
        "state_fingerprint",
    }
    assert terminal["stdout"] == f"logged in as {_SENSITIVE_MARKER}\n"
    assert terminal["stderr"] == f"token [[redacted-token:{_TOKEN_HANDLE}]]\n"
    assert outcome.stop_reason == "flow-unavailable"


def _assert_unprovable_masking_returns_only_unavailable(
    *, proxy_module: ModuleType, requests: ModuleType, observations: ModuleType
) -> None:
    channel = _Channel(inbound=requests.frame_for(tool="observe-browser", arguments={}))
    outcome = _served(
        proxy_module=proxy_module,
        channel=channel,
        performers=_ObservingPerformers(observations=observations, masking_established=False),
    )

    assert _results(channel=channel) == [_UNAVAILABLE], (
        "an observation whose masking cannot be established returns only unavailable, "
        "with no observation fields at all"
    )
    assert outcome.stop_reason == "flow-unavailable"
    assert outcome.consumed_steps == 1


def _assert_a_result_outside_the_closed_set_produces_no_proxy_result(
    *, proxy_module: ModuleType, requests: ModuleType
) -> None:
    for description, result in _NOT_CLOSED_RESULTS:
        channel = _Channel(
            inbound=requests.frame_for(
                tool="click-browser", arguments={"element_handle": "element:1"}
            )
        )
        performers = _FixedPerformers(result=result)
        outcome = _served(proxy_module=proxy_module, channel=channel, performers=performers)

        assert performers.calls == 1, f"{description} must still have been performed"
        assert channel.sent == [], f"{description} must produce no proxy result"
        assert channel.closed is True, f"{description} must close the private channel"
        assert (
            outcome.stop_reason == "flow-unavailable"
        ), f"{description} must fail flow-unavailable"


def _assert_every_closed_result_passes_through(
    *, proxy_module: ModuleType, requests: ModuleType
) -> None:
    for result in _CLOSED_RESULTS:
        channel = _Channel(
            inbound=requests.frame_for(
                tool="capture-token",
                arguments={"source_handle": _TOKEN_HANDLE},
            )
        )
        outcome = _served(
            proxy_module=proxy_module,
            channel=channel,
            performers=_FixedPerformers(result=result),
        )

        assert _results(channel=channel) == [result]
        assert outcome.consumed_steps == 1


def _assert_a_channel_that_refuses_the_result_ends_the_invocation(
    *, proxy_module: ModuleType, requests: ModuleType
) -> None:
    channel = _Channel(
        inbound=requests.frame_for(tool="wait-browser", arguments={"seconds": 1}) * 2,
        accepts=False,
    )
    outcome = _served(
        proxy_module=proxy_module,
        channel=channel,
        performers=_FixedPerformers(result={"version": 1, "status": "ok"}),
    )

    assert len(channel.sent) == 1, "a channel that refuses a result is not written to again"
    assert channel.closed is True
    assert outcome.stop_reason == "flow-unavailable"


def test_proxy_responses_carry_only_sanitized_output_and_opaque_handles() -> None:
    proxy_module = importlib.import_module("_lpm_acquisition_proxy")
    requests = importlib.import_module("_lpm_browser_requests")
    observations = importlib.import_module("_lpm_observations")
    assert (
        Path(__file__).parents[1] / "overseer" / "_lpm_proxy_results.py"
    ).is_file(), "the closed secret-free proxy result shapes must be implemented"

    _assert_observations_reach_the_channel_only_as_the_sanitizer_built_them(
        proxy_module=proxy_module, requests=requests, observations=observations
    )
    _assert_unprovable_masking_returns_only_unavailable(
        proxy_module=proxy_module, requests=requests, observations=observations
    )
    _assert_a_result_outside_the_closed_set_produces_no_proxy_result(
        proxy_module=proxy_module, requests=requests
    )
    _assert_every_closed_result_passes_through(proxy_module=proxy_module, requests=requests)
    _assert_a_channel_that_refuses_the_result_ends_the_invocation(
        proxy_module=proxy_module, requests=requests
    )
