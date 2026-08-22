"""Daemon release-runtime rollback state.

The self-update path replaces the daemon process image at a clean tick boundary.
That is only safe if the newly adopted runtime can prove it completed its first
acting tick. Until then this module keeps a tiny daemon-owned state file naming
the previous executable, the pending executable, and executables rejected for
crashing before that first successful tick.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import jsonio

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "begin_adoption",
    "complete_startup_if_pending",
    "default_runtime_state_path",
    "is_rejected",
    "rollback_after_startup_failure",
]


def default_runtime_state_path() -> Path:
    return (
        Path.home() / ".local" / "share" / "livespec-overseer" / "runtime" / "rollback-state.json"
    )


def is_rejected(*, sup: Supervisor, target: Path) -> bool:
    state = _read_state(sup=sup)
    return str(target) in _rejected(value=state.get("rejected"))


def begin_adoption(*, sup: Supervisor, target: Path, previous: Path) -> None:
    state = _read_state(sup=sup)
    state["pending"] = str(target)
    state["previous"] = str(previous)
    state["rejected"] = _rejected(value=state.get("rejected"))
    _write_state(sup=sup, state=state)


def complete_startup_if_pending(*, sup: Supervisor) -> None:
    current = _current_executable(sup=sup)
    state = _read_state(sup=sup)
    if state.get("pending") != current:
        return
    state["pending"] = None
    state["previous"] = current
    state["last_good"] = current
    state["rejected"] = _rejected(value=state.get("rejected"))
    _write_state(sup=sup, state=state)


def rollback_after_startup_failure(*, sup: Supervisor, exc: BaseException) -> None:
    current = _current_executable(sup=sup)
    state = _read_state(sup=sup)
    pending = state.get("pending")
    if pending != current:
        return
    previous = state.get("previous")
    rejected = _with_rejected(rejected=_rejected(value=state.get("rejected")), target=current)
    state["pending"] = None
    state["previous"] = previous
    state["last_good"] = previous
    state["rejected"] = rejected
    _write_state(sup=sup, state=state)
    if not isinstance(previous, str) or not previous:
        _surface_no_rollback_target(sup=sup, current=current, exc=exc)
        return
    target = Path(previous)
    if not target.is_file() or str(target) == current:
        _surface_no_rollback_target(sup=sup, current=current, exc=exc, previous=previous)
        return
    argv = [str(target), *sup.argv()[1:]]
    sup.surface(
        message=(
            "rolling back release runtime after startup failure before first successful "
            f"tick: {current} raised {type(exc).__name__}: {exc}; re-execing {target}"
        ),
        event="daemon-runtime-rollback",
        fields={"failed_runtime": current, "previous_runtime": str(target)},
    )
    sup.execv(path=str(target), argv=argv)


def _current_executable(*, sup: Supervisor) -> str:
    argv = sup.argv()
    return argv[0] if argv else ""


def _state_path(*, sup: Supervisor) -> Path:
    return Path(sup.runtime_state_path)


def _read_state(*, sup: Supervisor) -> dict[str, object]:
    path = _state_path(sup=sup)
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"pending": None, "previous": None, "rejected": []}
    data = jsonio.as_object(value=parsed)
    if data is None:
        return {"pending": None, "previous": None, "rejected": []}
    return dict(data)


def _write_state(*, sup: Supervisor, state: dict[str, object]) -> None:
    path = _state_path(sup=sup)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    _ = tmp.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")
    _ = tmp.replace(path)


def _rejected(*, value: object) -> list[str]:
    values = jsonio.as_list(value=value)
    if values is None:
        return []
    return [item for item in values if isinstance(item, str) and item]


def _with_rejected(*, rejected: list[str], target: str) -> list[str]:
    if target in rejected:
        return rejected
    return [*rejected, target]


def _surface_no_rollback_target(
    *,
    sup: Supervisor,
    current: str,
    exc: BaseException,
    previous: str | None = None,
) -> None:
    prior = "<absent>" if previous is None else previous
    sup.surface(
        message=(
            "cannot roll back release runtime after startup failure before first successful "
            f"tick: {current} raised {type(exc).__name__}: {exc}; prior runtime {prior} "
            "is not executable"
        ),
        event="daemon-runtime-rollback-failed",
        fields={"failed_runtime": current, "previous_runtime": prior},
    )
