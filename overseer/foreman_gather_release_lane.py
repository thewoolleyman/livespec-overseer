"""Release-lane source for the foreman evidence document."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, cast

import jsonio
from foreman_gather_sources import fetch_release_lane_runs, parse_repo_config
from release_lane_watch import lane_state, notice_text

__all__: list[str] = ["attention_with_release_lane", "release_lane_payload"]

_CONFIG_SECTION = "livespec-overseer"
_CONFIG_KEY = "release_lane_watch"
_DEFAULT_WORKFLOW = "release-tag.yml"
_DEFAULT_LABEL = "release-tag"
_DEFAULT_CACHE = "tmp/overseer/release-lane-watch.json"
_UNKNOWN_REASON = "forge unreachable or unavailable"


class RunsFetcher(Protocol):
    def __call__(self) -> list[dict[str, str]] | None: ...


def release_lane_payload(
    *,
    repo: Path,
    options: Mapping[str, object],
    measured_at: str,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    config = release_lane_config(repo=repo)
    if not release_lane_enabled(config=config, options=options):
        return None, None
    workflow = string_option(
        options=options,
        config=config,
        key="workflow",
        option_key="release_lane_workflow",
        default=_DEFAULT_WORKFLOW,
    )
    label = string_option(
        options=options,
        config=config,
        key="label",
        option_key="release_lane_label",
        default=_DEFAULT_LABEL,
    )
    cache_path = release_lane_cache_path(repo=repo, config=config, options=options)
    runs = release_lane_runs(repo=repo, workflow=workflow, options=options)
    if runs is None:
        return unknown_item(label=label, cache_path=cache_path), unknown_source(
            workflow=label, cache_path=cache_path
        )
    state = lane_state(runs=runs)
    write_cache(path=cache_path, workflow=label, measured_at=measured_at, state=state)
    text = notice_text(workflow=label, state=state)
    source: dict[str, object] = {
        "status": "ok",
        "workflow": label,
        "runs_considered": state.get("runs_considered"),
        "mode": "provided-history" if "release_lane_runs" in options else "forge-query",
    }
    if not text:
        return None, source
    return {
        "id": f"release-lane:{label}",
        "kind": "release-lane",
        "title": text,
    }, source


def release_lane_config(*, repo: Path) -> dict[str, object]:
    parsed = parse_repo_config(repo=repo)
    root = jsonio.as_object(value=parsed.get(_CONFIG_SECTION)) if parsed is not None else None
    config = jsonio.as_object(value=root.get(_CONFIG_KEY)) if root is not None else None
    return config if config is not None else {}


def release_lane_enabled(*, config: Mapping[str, object], options: Mapping[str, object]) -> bool:
    explicit = options.get("release_lane_enabled")
    if isinstance(explicit, bool):
        return explicit
    return config.get("enabled") is True


def string_option(
    *,
    options: Mapping[str, object],
    config: Mapping[str, object],
    key: str,
    option_key: str,
    default: str,
) -> str:
    option = options.get(option_key)
    if isinstance(option, str) and option:
        return option
    configured = config.get(key)
    return configured if isinstance(configured, str) and configured else default


def release_lane_cache_path(
    *, repo: Path, config: Mapping[str, object], options: Mapping[str, object]
) -> Path:
    option = options.get("release_lane_cache_path")
    if isinstance(option, Path):
        return option
    if isinstance(option, str):
        return Path(option)
    configured = config.get("cache_path")
    path = configured if isinstance(configured, str) and configured else _DEFAULT_CACHE
    return repo / path


def release_lane_runs(
    *, repo: Path, workflow: str, options: Mapping[str, object]
) -> list[dict[str, str]] | None:
    supplied = options.get("release_lane_runs")
    if supplied is not None:
        return normalized_runs(value=supplied)
    fetcher = options.get("release_lane_fetcher")
    if fetcher is not None:
        return cast("RunsFetcher", fetcher)()
    return fetch_release_lane_runs(repo=repo, workflow=workflow)


def normalized_runs(*, value: object) -> list[dict[str, str]] | None:
    rows = jsonio.as_list(value=value)
    if rows is None:
        return None
    normalized: list[dict[str, str]] = []
    for row in (jsonio.as_object(value=raw) for raw in rows):
        if row is None:
            return None
        normalized.append(
            {
                "conclusion": str(row.get("conclusion") or ""),
                "created_at": str(row.get("created_at") or ""),
            }
        )
    return normalized


def attention_with_release_lane(
    *, attention: dict[str, object] | None, item: dict[str, object] | None
) -> dict[str, object] | None:
    if item is None:
        return attention
    merged = dict(attention) if attention is not None else {}
    items = jsonio.as_list(value=merged.get("items")) or []
    merged["items"] = [
        *[existing for existing in (jsonio.as_object(value=raw) for raw in items) if existing],
        item,
    ]
    return merged


def unknown_item(*, label: str, cache_path: Path) -> dict[str, object]:
    stale = last_successful_measurement(path=cache_path)
    tail = f"last successful measurement {stale}" if stale else "no successful measurement cached"
    return {
        "id": f"release-lane:{label}",
        "kind": "release-lane-unknown",
        "title": f"{label}: UNKNOWN — could not measure release lane; {tail}",
    }


def unknown_source(*, workflow: str, cache_path: Path) -> dict[str, object]:
    source: dict[str, object] = {
        "status": "unknown",
        "workflow": workflow,
        "reason": _UNKNOWN_REASON,
    }
    stale = last_successful_measurement(path=cache_path)
    if stale:
        source["last_successful_measurement_at"] = stale
    return source


def last_successful_measurement(*, path: Path) -> str | None:
    try:
        parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if jsonio.is_parse_failure(result=parsed):
        return None
    payload = parsed.unwrap()
    measured_at = payload.get("measured_at") if payload is not None else None
    return measured_at if isinstance(measured_at, str) and measured_at else None


def write_cache(*, path: Path, workflow: str, measured_at: str, state: dict[str, object]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(
            json.dumps(
                {"measured_at": measured_at, "state": state, "workflow": workflow},
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError:
        return
