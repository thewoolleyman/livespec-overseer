"""Reviewer command execution for the foreman consensus panel."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Final

import jsonio
from foreman_consensus_prompt import reviewer_prompts
from foreman_panel_io import write_json
from foreman_panel_response import reviewer_response_object

__all__: list[str] = [
    "default_reviewer_command",
    "reviewer_argv",
    "reviewer_responses",
    "run_reviewer",
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
            stdin=subprocess.DEVNULL,
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
