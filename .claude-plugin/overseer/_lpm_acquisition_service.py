"""Worker-private browser control, observation sanitization and capture publication."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, cast

from _lpm_acquisition_commit import CaptureCommitOutcome, commit_validated_capture
from _lpm_browser_control import BrowserControl, ControlOutcome
from _lpm_observations import ObservationOutcome, ObservationSanitizer

__all__: list[str] = ["AcquisitionService"]


class LocalPerformer(Protocol):
    def __call__(
        self, *, tool: str, arguments: dict[str, object]
    ) -> dict[str, object] | ObservationOutcome: ...


@dataclass(kw_only=True)
class AcquisitionService:
    """The only component allowed to hold capture bytes or raw local observations."""

    step_limit: int
    allowed_origins: frozenset[str]
    sensitive_values: frozenset[str]
    perform_local: LocalPerformer
    inspect_identity: Callable[..., object]
    validate: Callable[..., object]
    acquisition_writer: Callable[..., object]
    publish_metadata: Callable[..., None]
    sleep: Callable[..., None]
    _captures: dict[str, bytearray] = field(default_factory=dict, init=False, repr=False)
    _control: BrowserControl = field(init=False, repr=False)
    _sanitizer: ObservationSanitizer = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._sanitizer = ObservationSanitizer(
            token_handles={},
            sensitive_values=self.sensitive_values,
            new_token_handle=self._capture_observed_token,
        )
        self._control = BrowserControl(
            step_limit=self.step_limit,
            allowed_origins=self.allowed_origins,
            tainted_values=self.sensitive_values,
            perform=self._perform,
        )

    @property
    def capture_count(self) -> int:
        return len(self._captures)

    @property
    def remaining_steps(self) -> int:
        return max(0, self.step_limit - self._control.consumed_steps)

    def store_capture(self, *, capture_handle: str, value: bytearray) -> None:
        previous = self._captures.pop(capture_handle, None)
        if previous is not None:
            previous.clear()
        self._captures[capture_handle] = value

    def dispatch(self, *, frame: bytes) -> ControlOutcome:
        return self._control.dispatch(frame=frame)

    def commit(
        self, *, capture_handle: str, account_id: str, value_generation: int
    ) -> CaptureCommitOutcome:
        capture = self._captures.pop(capture_handle, None)
        if capture is None:
            return CaptureCommitOutcome(
                status="failed", failure_reason="flow-unavailable", validation_attempts=0
            )
        return commit_validated_capture(
            capture=capture,
            capture_handle=capture_handle,
            account_id=account_id,
            value_generation=value_generation,
            inspect_identity=self.inspect_identity,
            validate=self.validate,
            acquisition_writer=self.acquisition_writer,
            publish_metadata=self.publish_metadata,
            sleep=self.sleep,
        )

    def destroy_captures(self) -> None:
        for capture in self._captures.values():
            capture.clear()
        self._captures.clear()

    def _capture_observed_token(self, *, value: str) -> str:
        handle = f"capture:{uuid.uuid4()}"
        self.store_capture(capture_handle=handle, value=bytearray(value.encode("utf-8")))
        return handle

    def _perform(
        self, *, tool: str, arguments: dict[str, object]
    ) -> dict[str, object] | ObservationOutcome:
        result = self.perform_local(tool=tool, arguments=arguments)
        if not isinstance(result, dict):
            foreign = result
            return ObservationOutcome(
                response=dict(foreign.response),
                fingerprint=foreign.fingerprint,
                stop_reason=foreign.stop_reason,
            )
        if tool == "observe-browser":
            return self._browser_observation(result=result)
        if tool == "observe-terminal":
            return self._terminal_observation(result=result)
        return result

    def _browser_observation(self, *, result: dict[str, object]) -> ObservationOutcome:
        expected = {
            "url",
            "title",
            "dom_text",
            "accessibility_tree",
            "masked_screenshot_png",
            "masking_established",
        }
        if set(result) != expected or not isinstance(result["masked_screenshot_png"], bytes):
            return _unavailable_observation()
        text_members = ("url", "title", "dom_text", "accessibility_tree")
        if any(not isinstance(result[name], str) for name in text_members):
            return _unavailable_observation()
        if type(result["masking_established"]) is not bool:
            return _unavailable_observation()
        return self._sanitizer.browser_observation(
            url=cast("str", result["url"]),
            title=cast("str", result["title"]),
            dom_text=cast("str", result["dom_text"]),
            accessibility_tree=cast("str", result["accessibility_tree"]),
            masked_screenshot_png=result["masked_screenshot_png"],
            masking_established=result["masking_established"],
        )

    def _terminal_observation(self, *, result: dict[str, object]) -> ObservationOutcome:
        if set(result) != {"running", "exit_status", "stdout", "stderr"}:
            return _unavailable_observation()
        if type(result["running"]) is not bool:
            return _unavailable_observation()
        if result["exit_status"] is not None and type(result["exit_status"]) is not int:
            return _unavailable_observation()
        if not isinstance(result["stdout"], str) or not isinstance(result["stderr"], str):
            return _unavailable_observation()
        return self._sanitizer.terminal_observation(
            running=result["running"],
            exit_status=result["exit_status"],
            stdout=result["stdout"],
            stderr=result["stderr"],
        )


def _unavailable_observation() -> ObservationOutcome:
    return ObservationOutcome(
        response={"version": 1, "status": "unavailable"},
        fingerprint=None,
        stop_reason="flow-unavailable",
    )
