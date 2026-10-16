"""Production acquisition worker composition across the two isolated agent roles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from _lpm_acquisition_flow import continue_after_research
from _lpm_acquisition_roles import (
    AcquisitionRoleInvocation,
    execution_invocation,
    research_invocation,
)
from _lpm_acquisition_service import AcquisitionService

__all__: list[str] = ["AcquisitionWorker", "RoleTranscript", "WorkerOutcome"]


@dataclass(frozen=True, kw_only=True)
class RoleTranscript:
    records: tuple[object, ...]
    exit_status: int


@dataclass(frozen=True, kw_only=True)
class WorkerOutcome:
    status: str
    failure_reason: str | None


class ResearchRunner(Protocol):
    def __call__(self, invocation: AcquisitionRoleInvocation) -> RoleTranscript: ...


class ExecutionRunner(Protocol):
    def __call__(self, invocation: AcquisitionRoleInvocation) -> dict[str, object]: ...


class Lifecycle(Protocol):
    def failed(self, *, reason: str) -> None: ...

    def succeeded(self, *, validation_attempts: int) -> None: ...

    def attention(self, *, reason: str, profile_ref: str, remaining_steps: int) -> None: ...


@dataclass(kw_only=True)
class AcquisitionWorker:
    """Run research, execution and publication without moving a secret between roles."""

    request: dict[str, object]
    record_id: str
    value_generation: int
    profile_ref: str
    role_directory: str
    claude_executable: str
    proxy_executable: str
    run_research: ResearchRunner
    run_execution: ExecutionRunner
    service: AcquisitionService
    lifecycle: Lifecycle

    def run(self) -> WorkerOutcome:
        research = self.run_research(
            research_invocation(
                claude_executable=self.claude_executable,
                role_directory=self.role_directory,
                request=dict(self.request),
            )
        )
        flow = continue_after_research(
            records=research.records,
            exit_status=research.exit_status,
            role_directory=self.role_directory,
            launch_execution=self._execute,
        )
        if flow.status != "executed" or flow.execution_result is None:
            return self._failed(reason="flow-unavailable")
        return self._finish(result=flow.execution_result)

    def _execute(self, *, brief: str) -> dict[str, object]:
        request = {
            **self.request,
            "record_id": self.record_id,
            "brief": brief,
            "profile_ref": self.profile_ref,
            "remaining_steps": self.service.remaining_steps,
        }
        invocation = execution_invocation(
            claude_executable=self.claude_executable,
            proxy_executable=self.proxy_executable,
            role_directory=self.role_directory,
            request=request,
        )
        return self.run_execution(invocation)

    def _finish(self, *, result: dict[str, object]) -> WorkerOutcome:
        if _is_capture(result=result):
            committed = self.service.commit(
                capture_handle=cast("str", result["capture_handle"]),
                account_id=cast("str", self.request["account_id"]),
                value_generation=self.value_generation,
            )
            if committed.status == "success":
                self.lifecycle.succeeded(validation_attempts=committed.validation_attempts)
                return WorkerOutcome(status="success", failure_reason=None)
            return self._failed(reason=committed.failure_reason or "flow-unavailable")
        if _is_attention(result=result):
            reason = cast("str", result["reason"])
            self.lifecycle.attention(
                reason=reason,
                profile_ref=self.profile_ref,
                remaining_steps=self.service.remaining_steps,
            )
            return WorkerOutcome(status="attention", failure_reason=None)
        return self._failed(reason="flow-unavailable")

    def _failed(self, *, reason: str) -> WorkerOutcome:
        self.service.destroy_captures()
        self.lifecycle.failed(reason=reason)
        return WorkerOutcome(status="failed", failure_reason=reason)


def _is_capture(*, result: dict[str, object]) -> bool:
    return (
        set(result) == {"version", "outcome", "capture_handle"}
        and result.get("version") == 1
        and result.get("outcome") == "captured"
        and isinstance(result.get("capture_handle"), str)
        and bool(result["capture_handle"])
    )


def _is_attention(*, result: dict[str, object]) -> bool:
    return (
        set(result) == {"version", "outcome", "reason"}
        and result.get("version") == 1
        and result.get("outcome") == "attention"
        and result.get("reason") in {"captcha", "two-factor"}
    )
