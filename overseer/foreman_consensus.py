"""CLI facade for the report-only Phase C consensus panel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

import jsonio
import streams
from foreman_consensus_cache import budget_result, read_cached_verdict, record_panel_result
from foreman_consensus_eval import escalation, evaluate_verdicts
from foreman_consensus_prompt import cache_key, reviewer_prompts
from foreman_consensus_record import record_consensus_evaluation
from foreman_consensus_types import (
    DEFAULT_PANEL_LIMITS,
    DEFAULT_STATE_DIR,
    PANEL_SCHEMA_VERSION,
    DecisionRule,
    PanelLimits,
)
from foreman_valve_policy import MAJORITY, UNANIMOUS, effective_valve_disposition

__all__: list[str] = [
    "DEFAULT_PANEL_LIMITS",
    "DEFAULT_STATE_DIR",
    "PANEL_SCHEMA_VERSION",
    "PanelLimits",
    "consensus",
    "decision_rule_for_request",
    "main",
]


def decision_rule_for_request(*, request: dict[str, object]) -> DecisionRule:
    repo = request.get("repo")
    if not isinstance(repo, str) or repo == "":
        return cast(DecisionRule, UNANIMOUS)
    rule = effective_valve_disposition(repo=Path(repo)).get("decision_rule")
    if rule == MAJORITY:
        return cast(DecisionRule, MAJORITY)
    return cast(DecisionRule, UNANIMOUS)


def consensus(
    *,
    request: dict[str, object],
    responses: dict[str, object],
    state_dir: Path = DEFAULT_STATE_DIR,
    limits: PanelLimits = DEFAULT_PANEL_LIMITS,
    emit_prompts: bool = False,
    decision_rule: DecisionRule | None = None,
) -> dict[str, object]:
    effective_decision_rule = (
        decision_rule if decision_rule is not None else decision_rule_for_request(request=request)
    )
    key = cache_key(request=request, decision_rule=effective_decision_rule)
    cached = read_cached_verdict(state_dir=state_dir, key=key)
    if cached is not None:
        result = {**cached, "cache": "hit"}
    elif limits.concurrency_cap <= 0:
        result = budget_result(reason="concurrency_cap_exceeded", cache_key=key)
        result["decision_rule"] = effective_decision_rule
    elif limits.per_tick_panel_budget <= 0:
        result = budget_result(reason="per_tick_panel_budget_exceeded", cache_key=key)
        result["decision_rule"] = effective_decision_rule
    elif not record_panel_result(state_dir=state_dir, daily_panel_budget=limits.daily_panel_budget):
        result = budget_result(reason="daily_panel_budget_exceeded", cache_key=key)
        result["decision_rule"] = effective_decision_rule
    else:
        result = {
            **evaluate_verdicts(
                request=request,
                responses=responses,
                decision_rule=effective_decision_rule,
            ),
            "cache": "miss",
        }
        result["panel_record"] = record_consensus_evaluation(
            request=request, responses=responses, verdict=result, cache_key=key
        )
        _ = record_panel_result(state_dir=state_dir, cache_key=key, verdict=result)
    if emit_prompts:
        result["prompts"] = reviewer_prompts(request=request)
    return result


def load_object(*, path: Path) -> dict[str, object] | None:
    parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    return None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()


def main(*, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="foreman-consensus")
    _ = parser.add_argument("--request", required=True)
    _ = parser.add_argument("--reviewer-responses", required=True)
    _ = parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    _ = parser.add_argument(
        "--per-tick-panel-budget", type=int, default=DEFAULT_PANEL_LIMITS.per_tick_panel_budget
    )
    _ = parser.add_argument(
        "--daily-panel-budget", type=int, default=DEFAULT_PANEL_LIMITS.daily_panel_budget
    )
    _ = parser.add_argument(
        "--concurrency-cap", type=int, default=DEFAULT_PANEL_LIMITS.concurrency_cap
    )
    _ = parser.add_argument("--emit-prompts", action="store_true")
    args = parser.parse_args(argv)
    request = load_object(path=Path(args.request))
    responses = load_object(path=Path(args.reviewer_responses))
    result = (
        escalation(
            reason="malformed_input",
            request={},
            reviewers=[],
            decision_rule=cast(DecisionRule, UNANIMOUS),
        )
        if request is None or responses is None
        else consensus(
            request=request,
            responses=responses,
            state_dir=Path(args.state_dir),
            limits=PanelLimits(
                per_tick_panel_budget=args.per_tick_panel_budget,
                daily_panel_budget=args.daily_panel_budget,
                concurrency_cap=args.concurrency_cap,
            ),
            emit_prompts=args.emit_prompts,
        )
    )
    streams.write_stdout(text=json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
