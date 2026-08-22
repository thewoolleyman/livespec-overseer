"""Read-only resolver for the foreman's human-valve disposition setting."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Final, Literal, TypeAlias

import jsonio
import streams
from foreman_gather_sources import parse_repo_config

__all__: list[str] = [
    "CONFIG_KEY",
    "CONSENSUS",
    "REPORT_ONLY",
    "ValveDisposition",
    "effective_valve_disposition",
    "main",
]

CONFIG_KEY: Final[str] = "foreman_valve_disposition"
FULL_AUTONOMY_KEY: Final[str] = "full_autonomy"
CONFIG_SECTION: Final[str] = "livespec-overseer"
REPORT_ONLY: Final[str] = "report-only"
CONSENSUS: Final[str] = "consensus"
UNANIMOUS: Final[str] = "unanimous"
MAJORITY: Final[str] = "majority"
ValveDisposition: TypeAlias = Literal["report-only", "consensus"]
DecisionRule: TypeAlias = Literal["unanimous", "majority"]
_VALUES: Final[frozenset[str]] = frozenset({REPORT_ONLY, CONSENSUS})
_CONFLICT_WARNING: Final[str] = "full_autonomy_conflicts_with_foreman_valve_disposition"


def _configured_value(*, config: dict[str, object] | None) -> object:
    if config is None:
        return None
    section = jsonio.as_object(value=config.get(CONFIG_SECTION))
    if section is not None and CONFIG_KEY in section:
        return section.get(CONFIG_KEY)
    return config.get(CONFIG_KEY)  # pragma: no cover


def _full_autonomy(*, config: dict[str, object] | None, source: Path) -> tuple[bool, str]:
    section = jsonio.as_object(value=config.get(CONFIG_SECTION)) if config is not None else None
    if section is not None and FULL_AUTONOMY_KEY in section:
        return section.get(FULL_AUTONOMY_KEY) is True, str(source)
    return False, "default"


def _with_full_autonomy_fields(
    *,
    result: dict[str, object],
    full_autonomy: bool,
    full_autonomy_source: str,
) -> dict[str, object]:
    conflict = full_autonomy and (
        result.get("configured") == REPORT_ONLY or result.get("recognized") is False
    )
    result["full_autonomy"] = full_autonomy
    result["full_autonomy_source"] = full_autonomy_source
    result["decision_rule"] = MAJORITY if full_autonomy else UNANIMOUS
    result["conflict"] = conflict
    if full_autonomy:
        result["effective"] = CONSENSUS
    if conflict:
        result["warning"] = _CONFLICT_WARNING
    return result


def effective_valve_disposition(*, repo: Path) -> dict[str, object]:
    source = repo / ".livespec.jsonc"
    config = parse_repo_config(repo=repo)
    full_autonomy, full_autonomy_source = _full_autonomy(config=config, source=source)
    configured = _configured_value(config=config)
    if configured == "":  # pragma: no cover
        configured = None
    if configured is None:
        return _with_full_autonomy_fields(
            result={
                "configured": None,
                "effective": REPORT_ONLY,
                "recognized": True,
                "source": "default",
            },
            full_autonomy=full_autonomy,
            full_autonomy_source=full_autonomy_source,
        )
    if not isinstance(configured, str):
        return _with_full_autonomy_fields(
            result={
                "configured": None,
                "effective": REPORT_ONLY,
                "recognized": True,
                "source": str(source),
            },
            full_autonomy=full_autonomy,
            full_autonomy_source=full_autonomy_source,
        )
    if configured in _VALUES:
        return _with_full_autonomy_fields(
            result={
                "configured": configured,
                "effective": configured,
                "recognized": True,
                "source": str(source),
            },
            full_autonomy=full_autonomy,
            full_autonomy_source=full_autonomy_source,
        )
    return _with_full_autonomy_fields(
        result={
            "configured": configured,
            "effective": REPORT_ONLY,
            "recognized": False,
            "source": str(source),
            "warning": "unrecognized_foreman_valve_disposition",
        },
        full_autonomy=full_autonomy,
        full_autonomy_source=full_autonomy_source,
    )


def main(*, argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="foreman-valve-disposition")
    _ = parser.add_argument("--repo", required=True)
    args = parser.parse_args(argv)
    result = effective_valve_disposition(repo=Path(args.repo).resolve())
    streams.write_stdout(text=json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
