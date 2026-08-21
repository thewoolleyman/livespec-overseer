"""Convening step for the foreman cross-vendor consensus panel."""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Final

import jsonio
import streams
from foreman_consensus import consensus
from foreman_consensus_prompt import cache_key, reviewer_prompts
from foreman_consensus_types import DEFAULT_PANEL_LIMITS, DEFAULT_STATE_DIR
from foreman_panel_decision_kind import result_decision_kind
from foreman_panel_io import default_dossier_dir, load_request, write_json
from foreman_panel_refusal import refusal_for, refused_result
from foreman_panel_response import reviewer_response_object

__all__: list[str] = [
    "convene_panel",
    "main",
]

DEFAULT_REVIEWER_TIMEOUT_SECONDS: Final[float] = 600.0


def str_field(*, payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def default_reviewer_command(*, prompt: str, model: dict[str, object]) -> list[str]:
    vendor = str_field(payload=model, key="vendor")
    model_name = str_field(payload=model, key="model")
    if vendor == "anthropic":
        return ["claude", "--model", model_name, "-p", prompt]
    return ["codex", "exec", "--model", model_name, prompt]


def command_missing_response(*, prompt: dict[str, object]) -> dict[str, object] | None:
    model = jsonio.as_object(value=prompt.get("model")) or {}
    command = default_reviewer_command(prompt=str_field(payload=prompt, key="prompt"), model=model)
    if shutil.which(command[0]) is not None:
        return None
    return {
        "reviewer_id": str_field(payload=prompt, key="reviewer_id"),
        "verdict": "insufficient-information",
        "action": {"action_id": "human_valve", "params": {"reason": "reviewer_command_missing"}},
        "rationale": f"reviewer command not found: {command[0]}",
        "raw_stdout": "",
    }


def reviewer_argv(
    *,
    command: list[str] | None,
    prompt: dict[str, object],
    prompt_file: Path,
) -> list[str]:
    model = jsonio.as_object(value=prompt.get("model")) or {}
    if command is None:
        return default_reviewer_command(prompt=str_field(payload=prompt, key="prompt"), model=model)
    return [
        *command,
        "--reviewer-id",
        str_field(payload=prompt, key="reviewer_id"),
        "--vendor",
        str_field(payload=model, key="vendor"),
        "--model",
        str_field(payload=model, key="model"),
        "--prompt-file",
        str(prompt_file),
    ]


def reviewer_failure(
    *, prompt: dict[str, object], reason: str, raw_stdout: str = ""
) -> dict[str, object]:
    return {
        "reviewer_id": str_field(payload=prompt, key="reviewer_id"),
        "verdict": "insufficient-information",
        "action": {"action_id": "human_valve", "params": {"reason": reason}},
        "rationale": reason,
        "raw_stdout": raw_stdout,
    }


def pinned_model(*, prompt: dict[str, object]) -> dict[str, object]:
    return dict(jsonio.as_object(value=prompt.get("model")) or {})


def run_reviewer(
    *,
    prompt: dict[str, object],
    prompt_file: Path,
    reviewer_command: list[str] | None,
    reviewer_timeout_seconds: float = DEFAULT_REVIEWER_TIMEOUT_SECONDS,
) -> dict[str, object]:
    if reviewer_command is None:
        missing = command_missing_response(prompt=prompt)
        if missing is not None:
            return missing
    try:
        completed = subprocess.run(
            args=reviewer_argv(command=reviewer_command, prompt=prompt, prompt_file=prompt_file),
            check=False,
            capture_output=True,
            text=True,
            timeout=reviewer_timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return reviewer_failure(prompt=prompt, reason="reviewer_timeout")
    if completed.returncode != 0:
        return reviewer_failure(
            prompt=prompt, reason="reviewer_command_failed", raw_stdout=completed.stdout
        )
    response = reviewer_response_object(raw_stdout=completed.stdout)
    if response is None:
        return reviewer_failure(
            prompt=prompt, reason="reviewer_response_malformed", raw_stdout=completed.stdout
        )
    return {
        **response,
        "reviewer_id": str_field(payload=prompt, key="reviewer_id"),
        "model": pinned_model(prompt=prompt),
        "raw_stdout": completed.stdout,
    }


def reviewer_responses(
    *,
    request: dict[str, object],
    dossier_dir: Path,
    reviewer_command: list[str] | None,
    reviewer_timeout_seconds: float = DEFAULT_REVIEWER_TIMEOUT_SECONDS,
) -> dict[str, object]:
    prompts = reviewer_prompts(request=request)
    prompt_dir = dossier_dir / "prompts"
    response_dir = dossier_dir / "responses"
    reviewers: list[dict[str, object]] = []
    for prompt in prompts:
        reviewer_id = str_field(payload=prompt, key="reviewer_id")
        prompt_file = write_json(path=prompt_dir / f"{reviewer_id}.json", payload=prompt)
        response = run_reviewer(
            prompt=prompt,
            prompt_file=prompt_file,
            reviewer_command=reviewer_command,
            reviewer_timeout_seconds=reviewer_timeout_seconds,
        )
        reviewers.append(response)
        _ = write_json(path=response_dir / f"{reviewer_id}.json", payload=response)
    return {"reviewers": reviewers}


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
