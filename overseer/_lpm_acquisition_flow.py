"""Closed research transcript validation before acquisition execution launch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from _lpm_canonical import canonical_json_text, parse_canonical_json

__all__: list[str] = [
    "AcquisitionFlowOutcome",
    "continue_after_research",
]

_RESEARCH_RECORDS = 2


@dataclass(frozen=True, kw_only=True)
class AcquisitionFlowOutcome:
    """Secret-free decision at the research-to-execution boundary."""

    status: str
    failure_reason: str | None
    execution_result: dict[str, object] | None


def continue_after_research(
    *,
    records: tuple[object, ...],
    exit_status: int,
    role_directory: str,
    launch_execution: Callable[..., dict[str, object]],
) -> AcquisitionFlowOutcome:
    """Launch execution only after one valid init and one valid ready result."""
    if exit_status != 0 or len(records) != _RESEARCH_RECORDS:
        return _failed()
    init = records[0]
    terminal = records[1]
    if not _valid_init(record=init, role_directory=role_directory) or not _valid_terminal(
        record=terminal
    ):
        return _failed()
    terminal_object = cast("dict[str, object]", terminal)
    result_text = cast("str", terminal_object["result"])
    parsed = parse_canonical_json(text=result_text).value_or(None)
    canonical = canonical_json_text(value=parsed).value_or("")
    source = cast("dict[str, object]", parsed) if isinstance(parsed, dict) else {}
    outcome = source.get("outcome")
    brief = source.get("brief")
    valid_result = (
        result_text == canonical
        and set(source) == {"version", "outcome", "brief"}
        and source.get("version") == 1
        and outcome in {"ready", "failed"}
        and isinstance(brief, str)
        and ((outcome == "ready" and brief != "") or (outcome == "failed" and brief == ""))
    )
    if not valid_result or outcome != "ready":
        return _failed()
    execution_result = launch_execution(brief=brief)
    return AcquisitionFlowOutcome(
        status="executed",
        failure_reason=None,
        execution_result=execution_result,
    )


def _valid_init(*, record: object, role_directory: str) -> bool:
    expected = {
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
    return record == expected


def _valid_terminal(*, record: object) -> bool:
    source = {
        False: {},
        True: cast("dict[str, object]", record),
    }[isinstance(record, dict)]
    return (
        set(source) == {"type", "subtype", "is_error", "result"}
        and source.get("type") == "result"
        and source.get("subtype") == "success"
        and source.get("is_error") is False
        and isinstance(source.get("result"), str)
    )


def _failed() -> AcquisitionFlowOutcome:
    return AcquisitionFlowOutcome(
        status="failed",
        failure_reason="flow-unavailable",
        execution_result=None,
    )
