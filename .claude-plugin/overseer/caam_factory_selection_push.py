"""Identity-only factory-selection transport for enrolled hosts."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import caam_delivery_service
import caam_factory_selection_delivery
import streams
from caam_delivery_push_state import (
    KNOWN_HOSTS,
    PUSH_STATE,
    Host,
    load_config,
    load_hosts,
    load_state,
    scrubbed,
    seconds,
)

__all__: list[str] = [
    "factory_selection_accepted",
    "factory_selection_bytes",
    "factory_selection_pending",
    "push_factory_selection",
]

Runner = Callable[..., tuple[int, str]]
_FACTORY_REPLY_WORDS = 3


def push_factory_selection(
    *,
    home: Path,
    run: Runner,
    now: float = 0.0,
    record_bytes: bytes | None = None,
) -> dict[str, str]:
    """Push the role holder's identity-only factory record to every listed host."""
    record = record_bytes if record_bytes is not None else factory_selection_bytes(home=home)
    if record is None:
        return {}
    settings = load_config(home=home)
    program = caam_factory_selection_delivery.apply_program(record_bytes=record)
    known_hosts = str(home / KNOWN_HOSTS)
    hosts = load_hosts(home=home)

    def push_one(*, host: Host) -> str:
        return run(
            target=host.target,
            program=program,
            key=str(settings["ssh_key"]),
            known_hosts=known_hosts,
            timeout=seconds(settings=settings, key="push_timeout_s"),
        )[1]

    with ThreadPoolExecutor(max_workers=max(1, len(hosts))) as pool:
        futures = {host.label: pool.submit(push_one, host=host) for host in hosts}
        outcomes = {label: future.result() for label, future in futures.items()}
    state = load_state(home=home)
    for label, line in outcomes.items():
        _record_result(entry=state.setdefault(label, {}), line=line, now=now)
    try:
        caam_delivery_service.write_private_json(path=home / PUSH_STATE, value=dict(state))
    except OSError as error:
        streams.write_stderr(text=f"FAIL factory push state not written: {type(error).__name__}\n")
    return outcomes


def factory_selection_bytes(*, home: Path) -> bytes | None:
    """Read the current published factory record without interpreting credentials."""
    try:
        return (home / caam_factory_selection_delivery.FACTORY_SELECTION_REL).read_bytes()
    except OSError:
        return None


def factory_selection_accepted(*, line: str) -> bool:
    """Whether a host's reply says it now holds this record or one at least as new."""
    words = line.split()
    return len(words) == _FACTORY_REPLY_WORDS and words[:2] in (
        ["factory-selection", "applied"],
        ["factory-selection", "not-newer"],
    )


def _record_result(*, entry: dict[str, object], line: str, now: float) -> None:
    if factory_selection_accepted(line=line):
        words = line.split()
        entry["factory_record_written_at"] = words[2]
        entry["factory_last_success"] = now
        return
    entry["factory_last_error"] = scrubbed(text=line)
    entry["factory_last_error_at"] = now


def factory_selection_pending(
    *, home: Path, now: float, run: Runner, record: bytes | None, due: bool
) -> bool:
    """Push the factory selection when due; whether some listed host still lacks it."""
    if record is None or not due:
        return False
    outcomes = push_factory_selection(home=home, now=now, run=run, record_bytes=record)
    for label, outcome in outcomes.items():
        streams.write_stdout(text=f"factory selection {label}: {outcome}\n")
    return not all(factory_selection_accepted(line=outcome) for outcome in outcomes.values())
