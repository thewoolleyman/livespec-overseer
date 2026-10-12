"""Execution cannot launch unless isolated research is valid and ready."""

from __future__ import annotations

import importlib
from pathlib import Path

__all__: list[str] = []


def _init(*, cwd: str = "/state/research", tools: list[str] | None = None) -> dict[str, object]:
    return {
        "type": "system",
        "subtype": "init",
        "cwd": cwd,
        "output_style": "default",
        "slash_commands": [],
        "skills": [],
        "plugins": [],
        "tools": ["WebSearch"] if tools is None else tools,
        "mcp_servers": [],
        "memory_paths": [],
    }


def _result(*, value: str) -> dict[str, object]:
    return {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": value,
    }


def test_failed_or_malformed_research_never_launches_execution() -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_acquisition_flow.py"
    assert module_path.is_file(), "the research-to-execution gate must be implemented"
    flow = importlib.import_module("_lpm_acquisition_flow")
    execution_calls: list[str] = []

    def execute(*, brief: str) -> dict[str, object]:
        execution_calls.append(brief)
        return {"version": 1, "outcome": "complete"}

    malformed = (
        (1, (_init(), _result(value='{"brief":"","outcome":"failed","version":1}'))),
        (0, (_result(value='{"brief":"ready","outcome":"ready","version":1}'),)),
        (0, (_init(tools=[]), _result(value='{"brief":"ready","outcome":"ready","version":1}'))),
        (0, (_init(), _result(value=' {"brief":"ready","outcome":"ready","version":1}'))),
        (0, (_init(), _result(value='{"brief":"","outcome":"ready","version":1}'))),
        (0, (_init(), _result(value='{"brief":"no","outcome":"failed","version":1}'))),
        (
            0,
            (
                _init(),
                _result(value='{"brief":"ready","outcome":"ready","version":1}'),
                _result(value="{}"),
            ),
        ),
    )
    for exit_status, records in malformed:
        outcome = flow.continue_after_research(
            records=records,
            exit_status=exit_status,
            role_directory="/state/research",
            launch_execution=execute,
        )
        assert outcome.status == "failed"
        assert outcome.failure_reason == "flow-unavailable"
        assert outcome.execution_result is None
    assert execution_calls == []

    ready = flow.continue_after_research(
        records=(
            _init(),
            _result(value='{"brief":"open provider settings","outcome":"ready","version":1}'),
        ),
        exit_status=0,
        role_directory="/state/research",
        launch_execution=execute,
    )
    assert ready.status == "executed"
    assert ready.failure_reason is None
    assert ready.execution_result == {"version": 1, "outcome": "complete"}
    assert execution_calls == ["open provider settings"]
