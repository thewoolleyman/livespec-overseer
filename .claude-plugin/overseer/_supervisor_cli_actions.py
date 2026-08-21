"""_supervisor_cli_actions — read-only/list style command bodies for the facade CLI."""

from __future__ import annotations

import argparse
import io
import json
from typing import TYPE_CHECKING, Protocol

import _supervisor_snapshot
import streams

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["adopt", "list_once"]


class SupervisorBuilder(Protocol):
    def __call__(self) -> Supervisor: ...


def list_once(*, args: argparse.Namespace, build_supervisor: SupervisorBuilder) -> int:
    sup = build_supervisor()
    if args.json:
        original_out = sup.out
        sup.out = io.StringIO()
        try:
            rows = sup.tick(act=False)  # read-only classify: no injection/restart
        finally:
            sup.out = original_out
        body = json.dumps(
            _supervisor_snapshot.document_payload(sup=sup, rows=rows),
            indent=2,
            sort_keys=True,
        )
        streams.write_stdout(text=f"{body}\n")
    else:
        _ = sup.tick(act=False)  # read-only render: no injection/restart
    return 0


def adopt(*, args: argparse.Namespace, build_supervisor: SupervisorBuilder) -> int:
    del args  # `adopt` takes no options; the dispatch shape supplies one anyway
    adopted = build_supervisor().adopt_sessions()
    for track in adopted:
        streams.write_stdout(text=f"adopted {track.tmux} → {track.repo}::{track.topic}\n")
    streams.write_stdout(text=f"adopted {len(adopted)} existing session(s)\n")
    return 0
