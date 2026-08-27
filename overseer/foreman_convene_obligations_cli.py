"""CLI entry point for the foreman convene-obligation record writers.

Split out of `foreman_convene_obligations` when publishing the foreman's own
wait states pushed that module past the hard LLOC ceiling. The seam is the
module's own cohesion boundary: everything here is argument parsing and
argument-to-writer routing, and everything left behind is the typed record
itself — its schema, its field validation, and its atomic write.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from foreman_convene_obligations import (
    write_convene_discharge,
    write_convene_escalation,
    write_convene_obligation,
)

__all__: list[str] = ["add_common_arguments", "main", "write_for_args"]


def main(*, argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    obligation = subparsers.add_parser("obligation")
    add_common_arguments(command=obligation)
    _ = obligation.add_argument("--action-id", required=True)
    _ = obligation.add_argument("--human-valve-category", required=True)
    for command in ("discharge", "escalation"):
        outcome = subparsers.add_parser(command)
        add_common_arguments(command=outcome)
        _ = outcome.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    _ = write_for_args(args=args)
    return 0


def add_common_arguments(*, command: argparse.ArgumentParser) -> None:
    _ = command.add_argument("--repo", required=True)
    _ = command.add_argument("--topic", required=True)
    _ = command.add_argument("--question-fingerprint", required=True)
    _ = command.add_argument("--observed-at-epoch", required=True, type=float)
    _ = command.add_argument("--request-json", required=True)


def write_for_args(*, args: argparse.Namespace) -> Path:
    request = json.loads(str(args.request_json))
    if not isinstance(request, dict):
        msg = "request-json must be a JSON object"
        raise TypeError(msg)
    typed_request = cast("dict[str, object]", request)
    if str(args.command) == "obligation":
        return write_convene_obligation(
            repo=str(args.repo),
            topic=str(args.topic),
            question_fingerprint=str(args.question_fingerprint),
            action_id=str(args.action_id),
            observed_at_epoch=float(args.observed_at_epoch),
            human_valve_category=str(args.human_valve_category),
            request=typed_request,
        )
    writer = (
        write_convene_discharge if str(args.command) == "discharge" else write_convene_escalation
    )
    return writer(
        repo=str(args.repo),
        topic=str(args.topic),
        question_fingerprint=str(args.question_fingerprint),
        reason=str(args.reason),
        observed_at_epoch=float(args.observed_at_epoch),
        request=typed_request,
    )
