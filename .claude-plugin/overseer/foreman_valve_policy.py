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
CONFIG_SECTION: Final[str] = "livespec-overseer"
REPORT_ONLY: Final[str] = "report-only"
CONSENSUS: Final[str] = "consensus"
ValveDisposition: TypeAlias = Literal["report-only", "consensus"]
_VALUES: Final[frozenset[str]] = frozenset({REPORT_ONLY, CONSENSUS})


def _configured_value(*, config: dict[str, object] | None) -> object:
    if config is None:
        return None
    section = jsonio.as_object(value=config.get(CONFIG_SECTION))
    if section is not None and CONFIG_KEY in section:
        return section.get(CONFIG_KEY)
    return config.get(CONFIG_KEY)  # pragma: no cover


def effective_valve_disposition(*, repo: Path) -> dict[str, object]:
    source = repo / ".livespec.jsonc"
    configured = _configured_value(config=parse_repo_config(repo=repo))
    if configured == "":  # pragma: no cover
        configured = None
    if configured is None:
        return {
            "configured": None,
            "effective": REPORT_ONLY,
            "recognized": True,
            "source": "default",
        }
    if not isinstance(configured, str):
        return {
            "configured": None,
            "effective": REPORT_ONLY,
            "recognized": True,
            "source": str(source),
        }
    if configured in _VALUES:
        return {
            "configured": configured,
            "effective": configured,
            "recognized": True,
            "source": str(source),
        }
    return {
        "configured": configured,
        "effective": REPORT_ONLY,
        "recognized": False,
        "source": str(source),
        "warning": "unrecognized_foreman_valve_disposition",
    }


def main(*, argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="foreman-valve-disposition")
    _ = parser.add_argument("--repo", required=True)
    args = parser.parse_args(argv)
    result = effective_valve_disposition(repo=Path(args.repo).resolve())
    streams.write_stdout(text=json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
