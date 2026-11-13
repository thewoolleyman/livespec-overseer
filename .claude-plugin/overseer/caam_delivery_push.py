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
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

import caam_delivery_service
import streams
from caam_delivery_apply_script import APPLY_SCRIPT, apply_program
from caam_delivery_macos import inbox_program
from caam_delivery_push_state import (
    CONFIG_FILE,
    HOSTS_FILE,
    KNOWN_HOSTS,
    PUSH_STATE,
    STATE_DIR,
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
    "PUSH_STATE",
    "STATE_DIR",
    "Host",
    "apply_program",
    "load_config",
    "load_hosts",
    "load_state",
    "push_due",
    "reissue_script",
    "run_ssh",
]

Runner = Callable[..., tuple[int, str]]
_due = due


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


def push_due(
    *,
    home: Path,
    delivery: caam_delivery_service.Delivery,
    now: float,
    run: Runner = run_ssh,
    config: dict[str, object] | None = None,
    reissue: str | None = None,
) -> dict[str, str]:
    """Push `delivery` to every listed host still behind it; return label -> outcome."""
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
    oauth = {key: value for key, value in delivery.oauth.items() if key != "refreshToken"}
    payload = json.dumps({**asdict(delivery), "oauth": oauth})
    programs = {"linux": apply_program(payload=payload), "macos": inbox_program(payload=payload)}
    token = str(oauth.get("accessToken", "")) or "\0"
    known_hosts = str(home / KNOWN_HOSTS)

    def push_one(*, host: Host) -> str:
        reply = run(
            target=host.target,
            program=programs[host.platform],
            key=str(settings["ssh_key"]),
            known_hosts=known_hosts,
            timeout=seconds(settings=settings, key="push_timeout_s"),
        )[1]
        changed = state.get(host.label, {}).get("account_id") != delivery.account_id
        if reply.startswith("applied") and changed and reissue is not None:
            reply += "; remote-control " + _reissue(
                host=host, script=reissue, run=run, settings=settings, home=home
            )
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
    return outcomes


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
