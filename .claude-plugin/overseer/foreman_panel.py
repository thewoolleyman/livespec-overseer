"""Convening step for the foreman cross-vendor consensus panel."""

from __future__ import annotations

import argparse
import json
import re
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

__all__: list[str] = [
    "convene_panel",
    "main",
]

HINT_REASONS: Final[tuple[tuple[str, str], ...]] = (
    ("unanimous", "verdict_hint_in_blocked_question"),
    ("unblock", "verdict_hint_in_blocked_question"),
    ("needs-human", "verdict_hint_in_blocked_question"),
    ("insufficient-information", "verdict_hint_in_blocked_question"),
    ("escalate", "verdict_hint_in_blocked_question"),
    ("human_valve", "verdict_hint_in_blocked_question"),
)
DEFAULT_REVIEWER_TIMEOUT_SECONDS: Final[float] = 600.0
TOOLING_FAILURE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "reviewer_command_missing",
        "reviewer_command_failed",
        "reviewer_response_malformed",
        "reviewer_timeout",
    }
)


def str_field(*, payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def refused_result(*, reason: str) -> dict[str, object]:
    return {"outcome": "refused", "reason": reason, "reviewers": []}


def hint_match(*, question: str, token: str) -> re.Match[str] | None:
    return re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", question)


def refusal_for(*, request: dict[str, object]) -> dict[str, object] | None:
    question = str_field(payload=request, key="blocked_question").lower()
    for token, reason in HINT_REASONS:
        match = hint_match(question=question, token=token)
        if match is not None:
            result = refused_result(reason=reason)
            result["hint"] = {"token": token, "offset": match.start()}
            return result
    return None


def default_dossier_dir(*, request: dict[str, object], key: str) -> Path:
    repo = Path(str_field(payload=request, key="repo"))
    if repo.is_absolute():
        return repo / DEFAULT_STATE_DIR / "panel" / key
    return DEFAULT_STATE_DIR / "panel" / key


def write_json(*, path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


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


def reviewer_failure(*, prompt: dict[str, object], reason: str) -> dict[str, object]:
    return {
        "reviewer_id": str_field(payload=prompt, key="reviewer_id"),
        "verdict": "insufficient-information",
        "action": {"action_id": "human_valve", "params": {"reason": reason}},
        "rationale": reason,
    }


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
        return reviewer_failure(prompt=prompt, reason="reviewer_command_failed")
    response = jsonio.parse_object(text=completed.stdout)
    if response is None:
        return reviewer_failure(prompt=prompt, reason="reviewer_response_malformed")
    return response


def reviewer_failure_reason(*, reviewer: dict[str, object]) -> str:
    action = jsonio.as_object(value=reviewer.get("action")) or {}
    params = jsonio.as_object(value=action.get("params")) or {}
    reason = params.get("reason")
    return reason if isinstance(reason, str) else ""


def result_decision_kind(*, reviewers: list[dict[str, object]]) -> str:
    if any(
        reviewer_failure_reason(reviewer=reviewer) in TOOLING_FAILURE_REASONS
        for reviewer in reviewers
    ):
        return "tooling_outage"
    return "substantive_non_decision"


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
        reviewers=[reviewer for reviewer in reviewers if isinstance(reviewer, dict)]
    )
    _ = write_json(path=panel_dir / "verdict.json", payload=verdict)
    _ = write_json(path=verdict_path, payload=verdict)
    return {
        **verdict,
        "dossier_dir": str(panel_dir),
        "reviewer_responses_path": str(panel_dir / "reviewer-responses.json"),
        "verdict_path": str(verdict_path),
    }


def load_request(*, path: Path) -> dict[str, object] | None:
    return jsonio.parse_object(text=path.read_text(encoding="utf-8"))


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
