"""Acquisition refuses missing protected material before durable or child-process work."""

from __future__ import annotations

import importlib
import json

from overseer._vendor.returns.result import Failure


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
