"""The CAAM-HOLD alarm record: a session-window hold is never silent.

When no destination account clears the session-window floor, the rotation pass
HOLDS, and the live account then runs out its 5-hour window. A hold with nothing
written anywhere is invisible to the plan epic's ticks that watch for it
(overseer-yzbdlq), so every SCHEDULED pass records its verdict in a durable file
beside the operation's other state, `caam-hold.json`, and journals a
`CAAM-HOLD` line on a state change and once per pass while held.

The record carries account NAMES and percentages only -- no credential material.
This module reads the previous record solely to decide whether the state
CHANGED; it never treats the file as evidence about any account.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Final, cast

from caam_anthropic_finish import LineWriter
from caam_anthropic_flags import scheduled_pass
from caam_decide_context import DecisionContext
from caam_decision import ProfileUsage, UsageRecord, five_hour_remaining_floor
from caam_decision_protection import is_protected
from caam_extra_usage import spend_capped
from caam_pass_publish import pass_stamp

__all__: list[str] = [
    "HOLD_RECORD_REL",
    "build_hold_record",
    "hold_record_path",
    "observe_pass_hold",
    "record_pass_hold",
]

HOLD_RECORD_REL: Final = Path(".local/state/caam-usage-rotate/caam-hold.json")
_HELD: Final = "held"
_CLEARED: Final = "cleared"
_FAIL_WRITE: Final = "FAIL could not write the caam hold record"


def hold_record_path(*, home: Path) -> Path:
    return home / HOLD_RECORD_REL


def build_hold_record(
    *,
    active_name: str,
    final_name: str,
    current: UsageRecord,
    profiles: tuple[ProfileUsage, ...],
    protection_floors: Mapping[str, float],
    written_at: str,
) -> dict[str, object]:
    """The record for one pass.

    `held` means the session-window trigger fired on the account the pass
    started on, the pass did not move off it, and no UNPROTECTED destination is
    above the floor. A protected destination is named as the best one where it is
    the best, because that refused move is exactly what the reader needs to see.
    """
    floor = five_hour_remaining_floor()
    candidates = tuple(
        (profile, profile.usage.five_hour_remaining)
        for profile in profiles
        if profile.name != active_name and profile.source == "live" and profile.usage is not None
    )
    best = max(candidates, key=lambda pair: pair[1], default=None)
    held = (
        final_name == active_name
        and current.short_window_present
        and not spend_capped(usage=current)
        and current.five_hour_remaining <= floor
        and not any(
            headroom > floor
            for profile, headroom in candidates
            if not is_protected(profile=profile, protection_floors=protection_floors)
        )
    )
    return {
        "state": _HELD if held else _CLEARED,
        "active_account": final_name,
        "active_session_headroom_pct": _active_headroom(
            active_name=active_name, final_name=final_name, current=current, profiles=profiles
        ),
        "floor_pct": floor,
        "best_destination": (
            None if best is None else {"account": best[0].name, "headroom_pct": best[1]}
        ),
        "written_at": written_at,
    }


def _active_headroom(
    *,
    active_name: str,
    final_name: str,
    current: UsageRecord,
    profiles: tuple[ProfileUsage, ...],
) -> float | None:
    if final_name == active_name:
        return current.five_hour_remaining if current.short_window_present else None
    moved = next((p.usage for p in profiles if p.name == final_name and p.usage), None)
    return None if moved is None else moved.five_hour_remaining


def record_pass_hold(
    *,
    context: DecisionContext,
    active_name: str,
    final_name: str,
    current: UsageRecord,
    profiles: tuple[ProfileUsage, ...],
    protection_floors: Mapping[str, float],
) -> None:
    """Record this pass's verdict -- on scheduled passes only, as every manual
    invocation is an operator act with its own output."""
    if not scheduled_pass(flags=context.flags):
        return
    observe_pass_hold(
        home=context.home,
        record=build_hold_record(
            active_name=active_name,
            final_name=final_name,
            current=current,
            profiles=profiles,
            protection_floors=protection_floors,
            written_at=pass_stamp(now=context.now),
        ),
        dry_run=context.flags.dry_run,
        stdout=context.stdout,
    )


def observe_pass_hold(
    *,
    home: Path,
    record: Mapping[str, object],
    dry_run: bool,
    stdout: LineWriter,
) -> None:
    """Write the record atomically (mode 600), or print it under a dry run, and
    journal the line where the state changed or the hold persists."""
    path = hold_record_path(home=home)
    previous = _previous_state(path=path)
    body = json.dumps(record, indent=1, sort_keys=True)
    if dry_run:
        stdout(f"CAAM-HOLD would write {path}: {json.dumps(record, sort_keys=True)}")
    else:
        try:
            _write_atomic(path=path, body=body)
        except OSError as exc:
            stdout(f"{_FAIL_WRITE}: {exc}")
    state = record["state"]
    if state == _HELD or state != previous:
        stdout(_journal_line(record=record))


def _write_atomic(*, path: Path, body: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    _ = tmp_path.write_text(body, encoding="utf-8")
    tmp_path.chmod(0o600)
    _ = tmp_path.replace(path)


def _previous_state(*, path: Path) -> str:
    """The recorded state, with absent, unreadable and malformed all read as cleared."""
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _CLEARED
    held = isinstance(parsed, dict) and cast(Mapping[str, object], parsed).get("state") == _HELD
    return _HELD if held else _CLEARED


def _journal_line(*, record: Mapping[str, object]) -> str:
    headroom = cast(float | None, record["active_session_headroom_pct"])
    best = cast(Mapping[str, object] | None, record["best_destination"])
    return (
        f"CAAM-HOLD {record['state']} active={record['active_account']} "
        f"headroom={'unknown' if headroom is None else format(headroom, 'g')} "
        f"floor={format(cast(float, record['floor_pct']), 'g')} "
        f"best={'none' if best is None else best['account']}"
    )
