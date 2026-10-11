"""Acquisition refuses missing protected material before durable or child-process work."""

from __future__ import annotations

import importlib
import json

from overseer._vendor.returns.result import Failure, Success


def test_missing_acquisition_prerequisites_create_no_state_or_worker(tmp_path):
    runtime_module = importlib.import_module("_lpm_runtime")
    commands = importlib.import_module("_lpm_commands")
    results = importlib.import_module("_lpm_results")
    config = importlib.import_module("_lpm_config").default_config()
    calls: list[dict[str, object]] = []

    def unavailable(*, request):
        calls.append(request)
        return Failure(results.invalid_request(message="matching acquisition login is unavailable"))

    state = tmp_path / "manager-state"
    runtime = runtime_module.ConcreteManagerRuntime(
        state_dir=state,
        owner_uid=0,
        config=config,
        read_input=lambda: json.dumps(
            {
                "version": 1,
                "provider": "anthropic",
                "account_id": "acct-1",
                "kind": "claude-code-oauth",
                "purpose": "factory",
            }
        ),
    )
    object.__setattr__(runtime, "acquisition", unavailable)

    outcome = runtime.run(invocation=commands.ManagerInvocation(command="acquire", source="-"))

    assert outcome.exit_status == 2
    assert outcome.body["error_type"] == "invalid-request"
    assert calls == [
        {
            "version": 1,
            "provider": "anthropic",
            "account_id": "acct-1",
            "kind": "claude-code-oauth",
            "purpose": "factory",
        }
    ]
    assert not state.exists(), "preflight refusal precedes operation, worker and record creation"


def test_installed_acquisition_binds_preflight_before_state(tmp_path, monkeypatch):
    runtime_module = importlib.import_module("_lpm_runtime")
    backend = importlib.import_module("_lpm_runtime_backend")
    prerequisites = importlib.import_module("_lpm_prereq")
    runner = importlib.import_module("_lpm_role_runner")
    commands = importlib.import_module("_lpm_commands")
    config = importlib.import_module("_lpm_config").default_config()
    launches: list[dict[str, object]] = []

    def launch(**request):
        launches.append(request)
        return runner.RoleCompletion(
            stdout=b'{"status":"absent","version":1}\n',
            exit_status=0,
            timed_out=False,
        )

    monkeypatch.setattr(runtime_module, "account_database_home", lambda **_kwargs: tmp_path)
    monkeypatch.setattr(runtime_module, "load_manager_config", lambda **_kwargs: Success(config))
    monkeypatch.setattr(runtime_module, "subprocess_role_launch", launch)
    monkeypatch.setattr(
        backend,
        "runtime_prerequisites",
        lambda **_kwargs: Success(
            prerequisites.RuntimePrerequisites(
                machine_id_sha256="a" * 64,
                op_executable="/usr/bin/op",
            )
        ),
    )
    runtime = runtime_module.runtime_for_host().unwrap()
    object.__setattr__(
        runtime,
        "read_input",
        lambda: json.dumps(
            {
                "version": 1,
                "provider": "anthropic",
                "account_id": "acct-1",
                "kind": "claude-code-oauth",
                "purpose": "factory",
            }
        ),
    )

    assert runtime.acquisition is not None

    outcome = runtime.run(
        invocation=commands.ManagerInvocation(
            command="acquire",
            source="-",
        )
    )

    assert outcome.exit_status == 2
    assert outcome.body["error_type"] == "invalid-request"
    assert len(launches) == 1
    assert not runtime.state_dir.exists()
