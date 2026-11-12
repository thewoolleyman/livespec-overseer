"""Push the role holder's current delivery to every listed host over ssh.

The role holder reaches each host; no host learns where the role holder is, so
moving the role changes nothing on the hosts. A host receives only the access
token and the account identity, never a refresh token. The delivery itself is
held in memory only: this module persists per-host push state, never a token.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import caam_delivery_service
import jsonio
import streams
from caam_delivery_apply_script import APPLY_SCRIPT

__all__: list[str] = [
    "APPLY_SCRIPT",
    "CONFIG_FILE",
    "HOSTS_FILE",
    "PUSH_STATE",
    "Host",
    "load_config",
    "load_hosts",
    "load_state",
    "push_due",
    "reissue_script",
    "run_ssh",
]

HOSTS_FILE = ".config/caam-delivery/hosts"
CONFIG_FILE = ".config/caam-delivery/config.json"
PUSH_STATE = ".local/state/caam-usage-rotate/delivery-push.json"
_HOST_FIELDS = 3
UNSUPPORTED_MACOS = "failed unsupported-platform: macos inbox lands with overseer-7m6wu6"

Runner = Callable[..., tuple[int, str]]

_DEFAULTS: dict[str, object] = {
    "ssh_key": "~/.ssh/id_ed25519",
    "push_timeout_s": 30.0,
    "retry_s": 30.0,
    "stale_after_s": 900.0,
    "reissue_timeout_s": 15.0,
}


@dataclass(frozen=True, kw_only=True)
class Host:
    label: str
    target: str
    platform: str


def load_config(*, home: Path) -> dict[str, object]:
    """Defaults overlaid by `~/.config/caam-delivery/config.json` when present."""
    body = _object(path=home / CONFIG_FILE) or {}
    return {key: body.get(key, value) for key, value in _DEFAULTS.items()}


def load_hosts(*, home: Path) -> list[Host]:
    """`<label> <ssh-target> <platform>` per line; a malformed line is reported and skipped."""
    path = home / HOSTS_FILE
    if not path.exists():
        return []
    hosts: list[Host] = []
    for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        fields = text.split("#", 1)[0].split()
        if not fields:
            continue
        valid = (
            len(fields) == _HOST_FIELDS
            and not any(field.startswith("-") for field in fields)
            and fields[2] in ("linux", "macos")
        )
        if not valid:
            streams.write_stderr(text=f"FAIL host list line {number} rejected\n")
            continue
        hosts.append(Host(label=fields[0], target=fields[1], platform=fields[2]))
    return hosts


def run_ssh(*, target: str, script: str, payload: str, key: str, timeout: float) -> tuple[int, str]:
    """Run `script` on `target` with `payload` on stdin; return (rc, one result line)."""
    argv = [
        "/usr/bin/ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        "-o",
        "StrictHostKeyChecking=yes",
        "-i",
        str(Path(key).expanduser()),
        "-o",
        "IdentitiesOnly=yes",
        "--",
        target,
        "python3 -c " + shlex.quote(script),
    ]
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv, target after --, script shell-quoted
            argv, input=payload, capture_output=True, text=True, timeout=timeout, check=False
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


def load_state(*, home: Path) -> dict[str, dict[str, object]]:
    body = _object(path=home / PUSH_STATE) or {}
    return {key: value for key, value in body.items() if isinstance(value, dict)}


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
    due = [
        host
        for host in hosts
        if _due(
            entry=state.get(host.label, {}), sequence=delivery.sequence, now=now, settings=settings
        )
    ]
    oauth = {key: value for key, value in delivery.oauth.items() if key != "refreshToken"}
    payload = json.dumps({**asdict(delivery), "oauth": oauth})
    token = str(oauth.get("accessToken", "")) or "\0"

    def push_one(*, host: Host) -> str:
        if host.platform == "macos":
            return UNSUPPORTED_MACOS
        reply = run(
            target=host.target,
            script=APPLY_SCRIPT,
            payload=payload,
            key=str(settings["ssh_key"]),
            timeout=_seconds(value=settings["push_timeout_s"]),
        )[1]
        changed = state.get(host.label, {}).get("account_id") != delivery.account_id
        if reply.startswith("applied") and changed:
            reply += "; remote-control " + _reissue(
                host=host, script=reissue, run=run, settings=settings
            )
        return reply.replace(token, "[redacted]")

    with ThreadPoolExecutor(max_workers=max(1, len(due))) as pool:
        futures = {host.label: pool.submit(push_one, host=host) for host in due}
        outcomes = {label: future.result() for label, future in futures.items()}
    for label, line in outcomes.items():
        _record(entry=state.setdefault(label, {}), line=line, delivery=delivery, now=now)
    caam_delivery_service.write_private_json(path=home / PUSH_STATE, value=dict(state))
    return outcomes


def reissue_script(*, path: Path) -> str | None:
    """The Remote Control re-issue script, when this checkout carries it."""
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _reissue(*, host: Host, script: str | None, run: Runner, settings: dict[str, object]) -> str:
    if script is None:
        return "re-issue unavailable"
    return run(
        target=host.target,
        script=script,
        payload="",
        key=str(settings["ssh_key"]),
        timeout=_seconds(value=settings["reissue_timeout_s"]),
    )[1]


def _record(
    *, entry: dict[str, object], line: str, delivery: caam_delivery_service.Delivery, now: float
) -> None:
    entry["last_attempt"] = now
    entry["attempt_sequence"] = delivery.sequence
    word = line.split(" ", 1)[0]
    if word in ("applied", "current"):
        entry.update(
            state="ok",
            sequence=delivery.sequence,
            account_id=delivery.account_id,
            expires_at=delivery.oauth.get("expiresAt"),
            last_success=now,
            last_error="",
        )
    elif word == "not-converted":
        entry.update(state="not-converted", last_error="not-converted")
    else:
        marked = line if line.startswith("failed") else "failed " + line
        entry.update(state="failed", last_error=marked)


def _due(
    *, entry: dict[str, object], sequence: int, now: float, settings: dict[str, object]
) -> bool:
    applied = entry.get("sequence")
    attempted = entry.get("last_attempt")
    if not isinstance(attempted, float):
        return True
    waited = now - attempted
    if entry.get("state") == "not-converted" or str(entry.get("last_error", "")).startswith(
        UNSUPPORTED_MACOS
    ):
        return waited >= _seconds(value=settings["stale_after_s"])
    if isinstance(applied, int) and applied >= sequence:
        return False
    return entry.get("attempt_sequence") != sequence or waited >= _seconds(
        value=settings["retry_s"]
    )


def _seconds(*, value: object) -> float:
    return float(value) if isinstance(value, int | float) else 30.0


def _object(*, path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    return None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()
