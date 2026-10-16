"""The acquire entrypoint reaches one worker-owned, secret-free production flow."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, cast

import pytest

import overseer._lpm_runtime_backend as backend
from overseer._lpm_browser_control import ControlOutcome
from overseer._lpm_config import default_config
from overseer._lpm_prereq import RuntimePrerequisites
from overseer._lpm_role_runner import RoleCompletion
from overseer._lpm_runtime_backend import RolePorts
from overseer._vendor.returns.result import Success

__all__: list[str] = []


class _WorkerOutcome(Protocol):
    status: str
    failure_reason: str | None


class _WorkerService(Protocol):
    capture_count: int


class _Worker(Protocol):
    service: _WorkerService

    def run(self) -> _WorkerOutcome: ...


def _role_launch(*, request: dict[str, object]) -> object:
    def launch(
        *,
        argv: tuple[str, ...],
        environ: Mapping[str, str],
        request_bytes: bytes,
        timeout_seconds: float,
        inherited_fds: tuple[int, ...],
    ) -> RoleCompletion:
        _ = (environ, timeout_seconds, inherited_fds)
        assert argv[-1] == "acquisition-prerequisite"
        assert json.loads(request_bytes) == {**request, "op_executable": "/usr/bin/op"}
        return RoleCompletion(
            stdout=b'{"status":"present","version":1}',
            exit_status=0,
            timed_out=False,
        )

    return launch


def test_present_prerequisites_start_the_bound_production_worker(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        backend,
        "runtime_prerequisites",
        lambda **_kwargs: Success(
            RuntimePrerequisites(machine_id_sha256="a" * 64, op_executable="/usr/bin/op")
        ),
    )
    request: dict[str, object] = {
        "version": 1,
        "provider": "anthropic",
        "account_id": "account-1",
        "kind": "claude-code-oauth",
        "purpose": "factory",
    }
    starts: list[dict[str, object]] = []

    def start(**members: object) -> Success[dict[str, object]]:
        starts.append(dict(members))
        return Success(
            {
                "version": 1,
                "status": "ok",
                "operation": "acquire",
                "record_id": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
                "credential_status": "acquiring",
            }
        )

    ports = cast("object", RolePorts)(
        config=default_config(),
        owner_uid=os.getuid(),
        state_dir=tmp_path / "state",
        environ={"PATH": "/usr/bin:/bin"},
        launch=cast("object", _role_launch(request=request)),
        python_executable=sys.executable,
        packaged_companion=str(tmp_path / "_lpm_companion.py"),
        start_acquisition=start,
    )

    outcome = ports.acquire(request=request)

    assert outcome.unwrap()["credential_status"] == "acquiring"
    assert len(starts) == 1
    assert starts[0]["request"] == request
    assert starts[0]["state_dir"] == tmp_path / "state"
    assert starts[0]["config"] == default_config()
    assert not (tmp_path / "state").exists(), "the worker boundary owns first mutation"


def _research_init(*, role_directory: str) -> dict[str, object]:
    return {
        "type": "system",
        "subtype": "init",
        "cwd": role_directory,
        "output_style": "default",
        "slash_commands": [],
        "skills": [],
        "plugins": [],
        "tools": ["WebSearch"],
        "mcp_servers": [],
        "memory_paths": [],
    }


def _research_result(*, value: str) -> dict[str, object]:
    return {"type": "result", "subtype": "success", "is_error": False, "result": value}


class _Lifecycle:
    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    def failed(self, *, reason: str) -> None:
        self.events.append(("failed", reason))

    def succeeded(self, *, validation_attempts: int) -> None:
        self.events.append(("succeeded", validation_attempts))

    def attention(self, *, reason: str, profile_ref: str, remaining_steps: int) -> None:
        self.events.append(("attention", (reason, profile_ref, remaining_steps)))


def _service(*, module: object, events: list[object]) -> object:
    service = module.AcquisitionService(
        step_limit=6,
        allowed_origins=frozenset({"https://claude.com"}),
        sensitive_values=frozenset({"account@example.test"}),
        perform_local=lambda **members: events.append(("tool", members))
        or {"version": 1, "status": "ok"},
        inspect_identity=lambda *, account_id: events.append(("identity", account_id)) or "matched",
        validate=lambda *, capture_handle: events.append(("validate", capture_handle)) or "success",
        acquisition_writer=lambda *, descriptor: events.append(
            ("writer", os.read(descriptor, 4096))
        )
        or "committed",
        publish_metadata=lambda *, value_generation: events.append(("publish", value_generation)),
        sleep=lambda seconds: events.append(("sleep", seconds)),
    )
    service.store_capture(
        capture_handle="capture:opaque",
        value=bytearray(b"synthetic-provider-token"),
    )
    return service


def test_worker_connects_research_execution_service_commit_and_lifecycle() -> None:
    import overseer._lpm_acquisition_service as service_module
    from overseer._lpm_acquisition_worker import AcquisitionWorker, RoleTranscript

    role_directory = "/state/research"
    service_events: list[object] = []
    service = _service(module=service_module, events=service_events)
    lifecycle = _Lifecycle()
    execution_invocations: list[object] = []
    worker = AcquisitionWorker(
        request={
            "version": 1,
            "provider": "anthropic",
            "account_id": "account-1",
            "kind": "claude-code-oauth",
            "purpose": "factory",
        },
        record_id="3f2504e0-4f89-41d3-9a0c-0305e82c3301",
        value_generation=7,
        profile_ref="profile:opaque",
        role_directory=role_directory,
        claude_executable="/opt/claude",
        proxy_executable="/opt/lpm-acquisition-proxy",
        run_research=lambda _invocation: RoleTranscript(
            records=(
                _research_init(role_directory=role_directory),
                _research_result(
                    value=('{"brief":"open provider settings","outcome":"ready","version":1}')
                ),
            ),
            exit_status=0,
        ),
        run_execution=lambda invocation: execution_invocations.append(invocation)
        or {
            "version": 1,
            "outcome": "captured",
            "capture_handle": "capture:opaque",
        },
        service=service,
        lifecycle=lifecycle,
    )

    outcome = worker.run()

    assert outcome.status == "success"
    assert lifecycle.events == [("succeeded", 1)]
    assert len(execution_invocations) == 1
    assert execution_invocations[0].expected_tools
    assert service_events == [
        ("identity", "account-1"),
        ("validate", "capture:opaque"),
        ("writer", b"synthetic-provider-token"),
        ("publish", 7),
    ]
    assert service.capture_count == 0


def test_worker_persists_failed_research_without_launching_execution() -> None:
    import overseer._lpm_acquisition_service as service_module
    from overseer._lpm_acquisition_worker import AcquisitionWorker, RoleTranscript

    service_events: list[object] = []
    lifecycle = _Lifecycle()
    executions: list[object] = []
    worker = AcquisitionWorker(
        request={
            "version": 1,
            "provider": "anthropic",
            "account_id": "account-1",
            "kind": "claude-code-oauth",
            "purpose": "factory",
        },
        record_id="3f2504e0-4f89-41d3-9a0c-0305e82c3301",
        value_generation=7,
        profile_ref="profile:opaque",
        role_directory="/state/research",
        claude_executable="/opt/claude",
        proxy_executable="/opt/lpm-acquisition-proxy",
        run_research=lambda _invocation: RoleTranscript(records=(), exit_status=1),
        run_execution=lambda invocation: executions.append(invocation) or {},
        service=_service(module=service_module, events=service_events),
        lifecycle=lifecycle,
    )

    outcome = worker.run()

    assert outcome.status == "failed"
    assert outcome.failure_reason == "flow-unavailable"
    assert lifecycle.events == [("failed", "flow-unavailable")]
    assert executions == []
    assert worker.service.capture_count == 0


def test_packaged_proxy_forwards_only_closed_framed_tool_requests() -> None:
    from overseer._lpm_acquisition_proxy import proxy_call
    from overseer._lpm_browser_control import BrowserControl

    actions: list[tuple[str, dict[str, object]]] = []
    control = BrowserControl(
        step_limit=2,
        allowed_origins=frozenset({"https://claude.com"}),
        tainted_values=frozenset(),
        perform=lambda *, tool, arguments: actions.append((tool, arguments))
        or {"version": 1, "status": "ok"},
    )
    response = proxy_call(
        tool="navigate-browser",
        arguments={"url": "https://claude.com/settings"},
        exchange=lambda *, frame: control.dispatch(frame=frame),
    )

    assert response == {"version": 1, "status": "ok"}
    assert actions == [("navigate-browser", {"url": "https://claude.com/settings"})]
    executable = Path(__file__).parents[1] / ".claude-plugin" / "bin" / "lpm-acquisition-proxy"
    assert executable.is_file()
    assert os.access(executable, os.X_OK)


def test_service_fails_closed_while_sanitizing_private_observations() -> None:
    import overseer._lpm_acquisition_service as service_module
    from overseer._lpm_browser_control import frame_for
    from overseer._lpm_observations import ObservationOutcome

    events: list[object] = []
    service = _service(module=service_module, events=events)
    prior = bytearray(b"old")
    replacement = bytearray(b"new")
    service.store_capture(capture_handle="capture:replace", value=prior)
    service.store_capture(capture_handle="capture:replace", value=replacement)
    assert prior == bytearray()

    browser = {
        "url": "https://claude.com/settings",
        "title": "account@example.test settings",
        "dom_text": "token sk-ant-oat01-synthetic",
        "accessibility_tree": "account@example.test",
        "masked_screenshot_png": b"masked",
        "masking_established": True,
    }
    terminal = {"running": False, "exit_status": 0, "stdout": "ok", "stderr": ""}
    direct = ObservationOutcome(
        response={"version": 1, "status": "ok"}, fingerprint="f", stop_reason=None
    )
    replies: list[object] = [browser, terminal, direct, {"version": 1, "status": "ok"}]
    service.perform_local = lambda **_members: cast("object", replies.pop(0))

    observed_browser = service.dispatch(frame=frame_for(tool="observe-browser", arguments={}))
    observed_terminal = service.dispatch(frame=frame_for(tool="observe-terminal", arguments={}))
    observed_direct = service.dispatch(frame=frame_for(tool="observe-browser", arguments={}))
    ordinary = service.dispatch(
        frame=frame_for(tool="navigate-browser", arguments={"url": "https://claude.com/settings"})
    )

    assert observed_browser.response is not None
    assert "account@example.test" not in repr(observed_browser.response)
    assert "sk-ant-oat01-synthetic" not in repr(observed_browser.response)
    assert observed_terminal.response == {
        "version": 1,
        "status": "ok",
        "running": False,
        "exit_status": 0,
        "stdout": "ok",
        "stderr": "",
    }
    assert observed_direct.response == {"version": 1, "status": "ok"}
    assert ordinary.response == {"version": 1, "status": "ok"}
    assert service.capture_count == 3
    service.destroy_captures()
    assert replacement == bytearray()
    assert service.capture_count == 0


@pytest.mark.parametrize(
    ("tool", "raw"),
    [
        ("observe-browser", {}),
        (
            "observe-browser",
            {
                "url": 1,
                "title": "title",
                "dom_text": "dom",
                "accessibility_tree": "tree",
                "masked_screenshot_png": b"masked",
                "masking_established": True,
            },
        ),
        (
            "observe-browser",
            {
                "url": "https://claude.com",
                "title": "title",
                "dom_text": "dom",
                "accessibility_tree": "tree",
                "masked_screenshot_png": "raw",
                "masking_established": True,
            },
        ),
        (
            "observe-browser",
            {
                "url": "https://claude.com",
                "title": "title",
                "dom_text": "dom",
                "accessibility_tree": "tree",
                "masked_screenshot_png": b"masked",
                "masking_established": 1,
            },
        ),
        ("observe-terminal", {}),
        ("observe-terminal", {"running": 1, "exit_status": 0, "stdout": "", "stderr": ""}),
        (
            "observe-terminal",
            {"running": False, "exit_status": "0", "stdout": "", "stderr": ""},
        ),
        (
            "observe-terminal",
            {"running": False, "exit_status": 0, "stdout": b"raw", "stderr": ""},
        ),
    ],
)
def test_service_releases_no_fields_for_malformed_local_observations(
    *, tool: str, raw: object
) -> None:
    import overseer._lpm_acquisition_service as service_module
    from overseer._lpm_browser_control import frame_for

    service = _service(module=service_module, events=[])
    service.perform_local = lambda **_members: cast("object", raw)

    outcome = service.dispatch(frame=frame_for(tool=tool, arguments={}))

    assert outcome.response == {"version": 1, "status": "unavailable"}
    assert outcome.stop_reason == "flow-unavailable"


def _worker_for_result(*, result: dict[str, object], lifecycle: _Lifecycle) -> _Worker:
    import overseer._lpm_acquisition_service as service_module
    from overseer._lpm_acquisition_worker import AcquisitionWorker, RoleTranscript

    return cast(
        "_Worker",
        AcquisitionWorker(
            request={
                "version": 1,
                "provider": "anthropic",
                "account_id": "account-1",
                "kind": "claude-code-oauth",
                "purpose": "factory",
            },
            record_id="3f2504e0-4f89-41d3-9a0c-0305e82c3301",
            value_generation=7,
            profile_ref="profile:opaque",
            role_directory="/state/research",
            claude_executable="/opt/claude",
            proxy_executable="/opt/lpm-acquisition-proxy",
            run_research=lambda _invocation: RoleTranscript(
                records=(
                    _research_init(role_directory="/state/research"),
                    _research_result(
                        value=('{"brief":"open provider settings","outcome":"ready","version":1}')
                    ),
                ),
                exit_status=0,
            ),
            run_execution=lambda _invocation: result,
            service=_service(module=service_module, events=[]),
            lifecycle=lifecycle,
        ),
    )


def test_worker_closes_unknown_capture_attention_and_malformed_results() -> None:
    attention = _Lifecycle()
    attention_worker = _worker_for_result(
        result={"version": 1, "outcome": "attention", "reason": "captcha"},
        lifecycle=attention,
    )
    assert attention_worker.run().status == "attention"
    assert attention.events == [("attention", ("captcha", "profile:opaque", 6))]
    assert attention_worker.service.capture_count == 1

    missing = _Lifecycle()
    missing_worker = _worker_for_result(
        result={"version": 1, "outcome": "captured", "capture_handle": "capture:missing"},
        lifecycle=missing,
    )
    assert missing_worker.run().failure_reason == "flow-unavailable"
    assert missing.events == [("failed", "flow-unavailable")]

    malformed_results = (
        {},
        {"version": 2, "outcome": "captured", "capture_handle": "capture:opaque"},
        {"version": 1, "outcome": "other", "capture_handle": "capture:opaque"},
        {"version": 1, "outcome": "captured", "capture_handle": 1},
        {"version": 1, "outcome": "captured", "capture_handle": ""},
        {"version": 2, "outcome": "attention", "reason": "captcha"},
        {"version": 1, "outcome": "other", "reason": "captcha"},
        {"version": 1, "outcome": "attention", "reason": "other"},
    )
    for result in malformed_results:
        lifecycle = _Lifecycle()
        worker = _worker_for_result(result=result, lifecycle=lifecycle)
        assert worker.run().failure_reason == "flow-unavailable"
        assert lifecycle.events == [("failed", "flow-unavailable")]


@pytest.mark.parametrize(
    "control",
    [
        ControlOutcome(response=None, close_channel=True, stop_reason="flow-unavailable"),
        ControlOutcome(response=None, close_channel=False, stop_reason="flow-unavailable"),
    ],
)
def test_proxy_fails_closed_without_a_response(*, control: object) -> None:
    from overseer._lpm_acquisition_proxy import proxy_call

    response = proxy_call(
        tool="observe-browser",
        arguments={},
        exchange=lambda **_members: cast("object", control),
    )

    assert response == {"version": 1, "status": "unavailable"}
