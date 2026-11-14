"""Push the role holder's current delivery to every listed host over ssh.

The role holder reaches each host; no host learns where the role holder is, so
moving the role changes nothing on the hosts. A host receives only the access
token and the account identity, never a refresh token. The delivery itself is
held in memory only and travels on ssh's stdin; the push state that
`caam_delivery_push_state` keeps never holds a token. Each host's key is checked
against the role holder's own known-hosts record, never the user's or the
system's.
"""

from __future__ import annotations

import json
import subprocess
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

import caam_delivery_service
import streams
from caam_delivery_apply_script import APPLY_SCRIPT, apply_program
from caam_delivery_push_state import (
    CONFIG_FILE,
    HOSTS_FILE,
    KNOWN_HOSTS,
    PUSH_STATE,
    STATE_DIR,
    UNSUPPORTED_MACOS,
    Host,
    due,
    load_config,
    load_hosts,
    load_state,
    record_result,
    seconds,
)

__all__: list[str] = [
    "APPLY_SCRIPT",
    "CONFIG_FILE",
    "HOSTS_FILE",
    "KNOWN_HOSTS",
    "MAX_REFRESHES_PER_PASS",
    "PUSH_STATE",
    "STATE_DIR",
    "Host",
    "Starter",
    "apply_program",
    "load_config",
    "load_hosts",
    "load_state",
    "push_due",
    "reissue_script",
    "run_ssh",
    "start_in_background",
]

Runner = Callable[..., tuple[int, str]]
Starter = Callable[..., None]
_due = due
# Refreshes of a delivery a host already holds are spread over passes rather
# than fanned out to every host at once; a new delivery is never held back.
MAX_REFRESHES_PER_PASS = 2


def run_ssh(
    *, target: str, program: str, key: str, known_hosts: str, timeout: float
) -> tuple[int, str]:
    """Run `program` on `target` under `python3 -`, fed on stdin; return (rc, one result line)."""
    if not Path(known_hosts).is_file():
        return 255, "failed no-known-hosts-record"
    argv = [
        "/usr/bin/ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={known_hosts}",
        "-o",
        "GlobalKnownHostsFile=/dev/null",
        "-i",
        str(Path(key).expanduser()),
        "-o",
        "IdentitiesOnly=yes",
        "--",
        target,
        "python3 -",
    ]
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv, target after --, program on stdin
            argv, input=program, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return 124, "failed timeout"
    except OSError as error:
        return 255, f"failed ssh-unavailable {type(error).__name__}"
    if "Host key verification failed" in done.stderr:
        return 255, "failed host-key-verification"
    lines = done.stdout.strip().splitlines()
    if done.returncode != 0 and not lines:
        return done.returncode, f"failed ssh-exit {done.returncode}"
    return done.returncode, (lines[-1] if lines else "failed no-reply")[:200]


def start_in_background(*, task: Callable[[], None]) -> None:
    """Run `task` on a daemon thread and return at once."""
    threading.Thread(target=task, name="remote-control-reissue", daemon=True).start()


def push_due(  # noqa: PLR0913 - each argument is an independent seam
    *,
    home: Path,
    delivery: caam_delivery_service.Delivery,
    now: float,
    run: Runner = run_ssh,
    config: dict[str, object] | None = None,
    reissue: str | None = None,
    start: Starter = start_in_background,
) -> dict[str, str]:
    """Push `delivery` to every listed host still behind it; return label -> outcome.

    Every outcome is recorded before any Remote Control re-issue runs. Each host whose
    account changed has its re-issue handed to `start` afterwards, a daemon thread by
    default, because the re-issue re-scans for up to its whole window and must not hold
    this pass or the service's loop.
    """
    settings = config or load_config(home=home)
    state = load_state(home=home)
    hosts = load_hosts(home=home)
    behind = [
        host
        for host in hosts
        if due(
            entry=state.get(host.label, {}), sequence=delivery.sequence, now=now, settings=settings
        )
    ]
    behind = _bounded(hosts=behind, state=state, sequence=delivery.sequence)
    oauth = {key: value for key, value in delivery.oauth.items() if key != "refreshToken"}
    program = apply_program(payload=json.dumps({**asdict(delivery), "oauth": oauth}))
    token = str(oauth.get("accessToken", "")) or "\0"
    known_hosts = str(home / KNOWN_HOSTS)
    switched: list[Host] = []

    def push_one(*, host: Host) -> str:
        if host.platform == "macos":
            return UNSUPPORTED_MACOS
        reply = run(
            target=host.target,
            program=program,
            key=str(settings["ssh_key"]),
            known_hosts=known_hosts,
            timeout=seconds(settings=settings, key="push_timeout_s"),
        )[1]
        changed = state.get(host.label, {}).get("account_id") != delivery.account_id
        if reply.startswith("applied") and changed and reissue is not None:
            switched.append(host)
        return reply.replace(token, "[redacted]")

    with ThreadPoolExecutor(max_workers=max(1, len(behind))) as pool:
        futures = {host.label: pool.submit(push_one, host=host) for host in behind}
        outcomes = {label: future.result() for label, future in futures.items()}
    for label, line in outcomes.items():
        record_result(entry=state.setdefault(label, {}), line=line, delivery=delivery, now=now)
    try:
        caam_delivery_service.write_private_json(path=home / PUSH_STATE, value=dict(state))
    except OSError as error:
        streams.write_stderr(text=f"FAIL push state not written: {type(error).__name__}\n")
    for host in switched:
        start(
            task=_reissue_task(
                host=host, script=reissue, run=run, settings=settings, home=home, token=token
            )
        )
    return outcomes


def _reissue_task(
    *,
    host: Host,
    script: str | None,
    run: Runner,
    settings: dict[str, object],
    home: Path,
    token: str,
) -> Callable[[], None]:
    """The host's re-issue, printing its one result line, redacted, when it finishes."""

    def task() -> None:
        line = _reissue(host=host, script=script, run=run, settings=settings, home=home)
        streams.write_stdout(
            text=f"remote-control {host.label}: {line.replace(token, '[redacted]')}\n"
        )

    return task


def _bounded(
    *, hosts: list[Host], state: dict[str, dict[str, object]], sequence: int
) -> list[Host]:
    """Every host behind `sequence`, plus at most MAX_REFRESHES_PER_PASS refreshes, oldest first."""
    refreshes = sorted(
        (host for host in hosts if _holds(entry=state.get(host.label, {}), sequence=sequence)),
        key=lambda host: _last_success(entry=state.get(host.label, {})),
    )
    fresh = [
        host for host in hosts if not _holds(entry=state.get(host.label, {}), sequence=sequence)
    ]
    return fresh + refreshes[:MAX_REFRESHES_PER_PASS]


def _holds(*, entry: dict[str, object], sequence: int) -> bool:
    applied = entry.get("sequence")
    return isinstance(applied, int) and applied >= sequence


def _last_success(*, entry: dict[str, object]) -> float:
    success = entry.get("last_success")
    return success if isinstance(success, float) else float("-inf")


def reissue_script(*, path: Path) -> str | None:
    """The Remote Control re-issue script, when this checkout carries it."""
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _reissue(
    *, host: Host, script: str | None, run: Runner, settings: dict[str, object], home: Path
) -> str:
    if script is None:
        return "re-issue unavailable"
    return run(
        target=host.target,
        program=script,
        key=str(settings["ssh_key"]),
        known_hosts=str(home / KNOWN_HOSTS),
        timeout=seconds(settings=settings, key="reissue_timeout_s"),
    )[1]
