"""Convening step for the foreman cross-vendor consensus panel."""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Final

import foreman_panel_reviewers
import jsonio
import streams
from foreman_consensus import consensus
from foreman_consensus_prompt import cache_key
from foreman_consensus_types import DEFAULT_PANEL_LIMITS, DEFAULT_STATE_DIR
from foreman_panel_decision_kind import result_decision_kind
from foreman_panel_io import default_dossier_dir, load_request, write_json
from foreman_panel_refusal import refusal_for, refused_result

__all__: list[str] = [
    "convene_panel",
    "main",
]

DEFAULT_REVIEWER_TIMEOUT_SECONDS: Final[float] = 600.0

default_reviewer_command = foreman_panel_reviewers.default_reviewer_command
reviewer_argv = foreman_panel_reviewers.reviewer_argv
reviewer_responses = foreman_panel_reviewers.reviewer_responses
run_reviewer = foreman_panel_reviewers.run_reviewer
str_field = foreman_panel_reviewers.str_field


def convene_panel(
    *,
    request: dict[str, object],
    state_dir: Path = DEFAULT_STATE_DIR,
    verdict_path: Path,
    reviewer_command: list[str] | None = None,
    reviewer_timeout_seconds: float = DEFAULT_REVIEWER_TIMEOUT_SECONDS,
    dossier_dir: Path | None = None,
) -> dict[str, object]:
    refusal = refusal_for(request=request)
    if refusal is not None:
        return refusal
    key = cache_key(request=request)
    panel_dir = (
        dossier_dir if dossier_dir is not None else default_dossier_dir(request=request, key=key)
    )
    _ = write_json(path=panel_dir / "dossier.json", payload={"request": request})
    responses = reviewer_responses(
        request=request,
        dossier_dir=panel_dir,
        reviewer_command=reviewer_command,
        reviewer_timeout_seconds=reviewer_timeout_seconds,
    )
    _ = write_json(path=panel_dir / "reviewer-responses.json", payload=responses)
    verdict = consensus(
        request=request,
        responses=responses,
        state_dir=state_dir,
        limits=DEFAULT_PANEL_LIMITS,
    )
    reviewers = jsonio.as_list(value=responses.get("reviewers")) or []
    verdict["decision_kind"] = result_decision_kind(
        reviewers=[reviewer for reviewer in reviewers if isinstance(reviewer, dict)],
        verdict_reason=str_field(payload=verdict, key="reason"),
    )
    _ = write_json(path=panel_dir / "verdict.json", payload=verdict)
    _ = write_json(path=verdict_path, payload=verdict)
    return {
        **verdict,
        "dossier_dir": str(panel_dir),
        "reviewer_responses_path": str(panel_dir / "reviewer-responses.json"),
        "verdict_path": str(verdict_path),
    }


def main(*, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="foreman-panel")
    _ = parser.add_argument("--request", required=True)
    _ = parser.add_argument("--verdict-output", required=True)
    _ = parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    _ = parser.add_argument("--dossier-dir", default=None)
    _ = parser.add_argument("--reviewer-command", default=None)
    _ = parser.add_argument(
        "--reviewer-timeout-seconds",
        type=float,
        default=DEFAULT_REVIEWER_TIMEOUT_SECONDS,
    )
    args = parser.parse_args(argv)
    request = load_request(path=Path(args.request))
    command = shlex.split(args.reviewer_command) if args.reviewer_command else None
    result: dict[str, object] = (
        refused_result(reason="malformed_request")
        if request is None
        else convene_panel(
            request=request,
            state_dir=Path(args.state_dir),
            verdict_path=Path(args.verdict_output),
            dossier_dir=Path(args.dossier_dir) if args.dossier_dir else None,
            reviewer_command=command,
            reviewer_timeout_seconds=args.reviewer_timeout_seconds,
        )
    )
    streams.write_stdout(text=json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 2 if result.get("outcome") == "refused" else 0


if __name__ == "__main__":
    raise SystemExit(main())
