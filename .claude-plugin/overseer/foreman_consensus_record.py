"""Durable panel records for evaluated foreman consensus results."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from foreman_act_record import append_journal
from foreman_consensus_prompt import canonical_json, str_field
from foreman_consensus_types import DEFAULT_STATE_DIR, PANEL_SCHEMA_VERSION

__all__: list[str] = [
    "record_consensus_evaluation",
]


def record_consensus_evaluation(
    *,
    request: dict[str, object],
    responses: dict[str, object],
    verdict: dict[str, object],
    cache_key: str,
) -> dict[str, object]:
    location = panel_location(request=request, cache_key=cache_key)
    if location is None:
        return {"outcome": "skipped", "reason": validation_skip_reason(request=request)}
    try:
        artifact = write_panel_artifact(
            path=location,
            request=request,
            responses=responses,
            verdict=verdict,
            cache_key=cache_key,
        )
        append_journal(
            repo=location.parents[5],
            record=journal_record(request=request, verdict=verdict, path=artifact),
        )
    except OSError:
        return {"outcome": "skipped", "reason": "panel_record_write_failed"}
    return {"outcome": "written", "artifact": str(artifact)}


def panel_location(*, request: dict[str, object], cache_key: str) -> Path | None:
    repo = repo_path(request=request)
    topic = topic_path(request=request)
    if repo is None or topic is None:
        return None
    return repo / DEFAULT_STATE_DIR / "panels" / topic / f"panel-{cache_key}.json"


def validation_skip_reason(*, request: dict[str, object]) -> str:
    if repo_path(request=request) is None:
        return "invalid_repo"
    return "invalid_topic"


def repo_path(*, request: dict[str, object]) -> Path | None:
    repo = Path(str_field(payload=request, key="repo"))
    return repo if repo.is_absolute() and repo.is_dir() else None


def topic_path(*, request: dict[str, object]) -> Path | None:
    topic = str_field(payload=request, key="topic")
    path = Path(topic)
    if topic == "" or path.is_absolute() or ".." in path.parts:
        return None
    return path


def panel_payload(
    *,
    request: dict[str, object],
    responses: dict[str, object],
    verdict: dict[str, object],
    cache_key: str,
) -> dict[str, object]:
    return {
        "schema_version": PANEL_SCHEMA_VERSION,
        "kind": "foreman-consensus-panel",
        "cache_key": cache_key,
        "canonical_request": canonical_json(value=request),
        "request": request,
        "responses": responses,
        "reviewers": verdict.get("reviewers"),
        "outcome": verdict.get("outcome"),
        "reason": verdict.get("reason"),
        "decision_rule": verdict.get("decision_rule"),
        "verdict": verdict,
    }


def write_panel_artifact(
    *,
    path: Path,
    request: dict[str, object],
    responses: dict[str, object],
    verdict: dict[str, object],
    cache_key: str,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            payload = panel_payload(
                request=request, responses=responses, verdict=verdict, cache_key=cache_key
            )
            _ = handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _ = temp_path.replace(target=path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise
    return path


def journal_record(
    *, request: dict[str, object], verdict: dict[str, object], path: Path
) -> dict[str, object]:
    return {
        "stage": "foreman-consensus",
        "repo": str(path.parents[5]),
        "topic": str_field(payload=request, key="topic"),
        "panel_outcome": verdict.get("outcome"),
        "panel_reason": verdict.get("reason"),
        "decision_rule": verdict.get("decision_rule"),
        "panel_cache_key": verdict.get("cache_key"),
        "reviewers": verdict.get("reviewers"),
        "models": verdict.get("models"),
        "artifact": str(path),
    }
