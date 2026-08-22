#!/usr/bin/env python3
"""Fail when full_autonomy coexists with lower-autonomy sibling levers."""

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OVERSEER_DIR = _REPO_ROOT / "overseer"
if str(_OVERSEER_DIR) not in sys.path:
    sys.path.insert(0, str(_OVERSEER_DIR))

from foreman_gather_sources import parse_repo_config  # noqa: E402

__all__: list[str] = [
    "FULL_AUTONOMY_LEVERS",
    "Violation",
    "check_repo",
    "main",
]

_MISSING = object()
_CONFIG_SECTION = "livespec-overseer"
_FULL_AUTONOMY_KEY = "full_autonomy"


def _format_value(*, value: object) -> str:
    if value is _MISSING:
        return "absent"
    return json.dumps(value, sort_keys=True)


@dataclass(frozen=True, kw_only=True)
class Required:
    description: str
    predicate: Callable[[object], bool]


@dataclass(frozen=True, kw_only=True)
class Lever:
    dotted_path: str
    required: Required
    owning_plugin: str
    citation: str


@dataclass(frozen=True, kw_only=True)
class Violation:
    key: str
    found: str
    required: str
    owning_plugin: str
    citation: str


def _equals(*, value: object) -> Required:
    return Required(
        description=_format_value(value=value),
        predicate=lambda candidate: candidate == value,
    )


def _non_empty_string() -> Required:
    return Required(
        description="non-empty string",
        predicate=lambda candidate: isinstance(candidate, str) and bool(candidate),
    )


def _absent_or_consensus() -> Required:
    return Required(
        description='absent or "consensus"',
        predicate=lambda candidate: candidate is _MISSING or candidate == "consensus",
    )


FULL_AUTONOMY_LEVERS: tuple[Lever, ...] = (
    Lever(
        dotted_path="spec_governance.propose_change_mode",
        required=_equals(value="batch"),
        owning_plugin="livespec",
        citation="plan/foreman-full-autonomy-option/research/opening-research-2026-08-22.md D5",
    ),
    Lever(
        dotted_path="spec_governance.critique_mode",
        required=_equals(value="batch"),
        owning_plugin="livespec",
        citation="plan/foreman-full-autonomy-option/research/opening-research-2026-08-22.md D5",
    ),
    Lever(
        dotted_path="spec_governance.in_flight_alignment",
        required=_equals(value="default-align"),
        owning_plugin="livespec",
        citation="plan/foreman-full-autonomy-option/research/opening-research-2026-08-22.md D5",
    ),
    Lever(
        dotted_path="spec_governance.revise_decision_mode",
        required=_equals(value="delegated"),
        owning_plugin="livespec",
        citation=(
            "plan/foreman-full-autonomy-option/research/opening-research-2026-08-22.md "
            "D5; consensus inert until livespec core consensus tier exists"
        ),
    ),
    Lever(
        dotted_path="spec_governance.ratification_review",
        required=_equals(value="auto-spawn"),
        owning_plugin="livespec",
        citation="plan/foreman-full-autonomy-option/research/opening-research-2026-08-22.md D5",
    ),
    Lever(
        dotted_path="spec_governance.ratification_reviewer_model",
        required=_non_empty_string(),
        owning_plugin="livespec",
        citation="plan/foreman-full-autonomy-option/research/opening-research-2026-08-22.md D5",
    ),
    Lever(
        dotted_path="spec_governance.spec_pr_merge",
        required=_equals(value="auto-on-green"),
        owning_plugin="livespec",
        citation="plan/foreman-full-autonomy-option/research/opening-research-2026-08-22.md D5",
    ),
    Lever(
        dotted_path="spec_governance.drift_acceptance_mode",
        required=_equals(value="consensus"),
        owning_plugin="livespec",
        citation="plan/foreman-full-autonomy-option/research/opening-research-2026-08-22.md D5",
    ),
    Lever(
        dotted_path="livespec-orchestrator-beads-fabro.dispatcher.acceptance_mode",
        required=_equals(value="ai-only"),
        owning_plugin="livespec-orchestrator-beads-fabro",
        citation="plan/foreman-full-autonomy-option/research/opening-research-2026-08-22.md D5",
    ),
    Lever(
        dotted_path="livespec-orchestrator-beads-fabro.dispatcher.auto_approve_ready",
        required=_equals(value=True),
        owning_plugin="livespec-orchestrator-beads-fabro",
        citation="plan/foreman-full-autonomy-option/research/opening-research-2026-08-22.md D5",
    ),
    Lever(
        dotted_path="livespec-overseer.foreman_valve_disposition",
        required=_absent_or_consensus(),
        owning_plugin="livespec-overseer",
        citation="plan/foreman-full-autonomy-option/research/opening-research-2026-08-22.md D2/D5",
    ),
)


def _as_object(*, value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in value.items() if isinstance(key, str)}


def _value_at(*, config: dict[str, object], dotted_path: str) -> object:
    current: object = config
    for part in dotted_path.split("."):
        current_object = _as_object(value=current)
        if current_object is None or part not in current_object:
            return _MISSING
        current = current_object[part]
    return current


def _full_autonomy_enabled(*, config: dict[str, object] | None) -> bool:
    if config is None:
        return False
    section = _as_object(value=config.get(_CONFIG_SECTION))
    return section is not None and section.get(_FULL_AUTONOMY_KEY) is True


def check_repo(*, repo: Path) -> list[Violation]:
    config = parse_repo_config(repo=repo)
    if not _full_autonomy_enabled(config=config):
        return []
    if config is None:  # pragma: no cover
        return []
    violations: list[Violation] = []
    for lever in FULL_AUTONOMY_LEVERS:
        found = _value_at(config=config, dotted_path=lever.dotted_path)
        if not lever.required.predicate(found):
            violations.append(
                Violation(
                    key=lever.dotted_path,
                    found=_format_value(value=found),
                    required=lever.required.description,
                    owning_plugin=lever.owning_plugin,
                    citation=lever.citation,
                )
            )
    return violations


def _write_violations(*, violations: Sequence[Violation]) -> None:
    for violation in violations:
        _ = sys.stderr.write(
            "check-full-autonomy-config-conformance: "
            f"{violation.key} is {violation.found}; required {violation.required} "
            f"({violation.owning_plugin}; {violation.citation})\n"
        )


def main(*, argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check-full-autonomy-config-conformance")
    _ = parser.add_argument("--repo", default=".")
    args = parser.parse_args(argv)
    violations = check_repo(repo=Path(args.repo).resolve())
    if violations:
        _write_violations(violations=violations)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
