"""Push the role holder's current delivery to every listed host over ssh.

The role holder reaches each host; no host learns where the role holder is, so
moving the role changes nothing on the hosts. A host receives only the access
token and the account identity, never a refresh token, and the apply script
refuses to overwrite a host credential file that still holds its own login.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

import caam_delivery_service
import jsonio
from caam_profile_state import live_creds_path

__all__: list[str] = [
    "APPLY_SCRIPT",
    "HOSTS_FILE",
    "PUSH_STATE",
    "live_pair",
    "load_hosts",
    "push_due",
    "run_ssh",
    "status_lines",
]

HOSTS_FILE = ".config/caam-delivery/hosts"
PUSH_STATE = ".local/state/caam-usage-rotate/delivery-push.json"

Runner = Callable[..., tuple[int, str]]

# Runs on the host under `python3 -c`; the delivery arrives on stdin.
APPLY_SCRIPT = r"""
import json, os, sys, tempfile
d = json.load(sys.stdin)
home = os.path.expanduser("~")
cp = os.path.join(home, ".claude", ".credentials.json")
sp = os.path.join(home, ".claude.json")
qp = os.path.join(home, ".claude", ".caam-delivery-sequence")
def rd(p):
    try:
        with open(p) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
def wr(p, v, mode):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    fd, t = tempfile.mkstemp(dir=os.path.dirname(p))
    with os.fdopen(fd, "w") as f:
        json.dump(v, f)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(t, mode)
    os.replace(t, p)
cred = rd(cp)
if (cred.get("claudeAiOauth") or {}).get("refreshToken"):
    print("not-converted")
    sys.exit(3)
try:
    with open(qp) as f:
        last = int(f.read().strip() or 0)
except (FileNotFoundError, ValueError):
    last = 0
if d["sequence"] <= last:
    print("current")
    sys.exit(0)
cred["claudeAiOauth"] = d["oauth"]
state = rd(sp)
state.update(d["identity"])
wr(cp, cred, 0o600)
wr(sp, state, os.stat(sp).st_mode & 0o777 if os.path.exists(sp) else 0o600)
with open(qp, "w") as f:
    f.write(str(d["sequence"]))
print("applied")
"""


def run_ssh(*, target: str, script: str, payload: str) -> tuple[int, str]:
    """Run `script` on `target` with `payload` on stdin; return (rc, last output line)."""
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv, script shell-quoted
            [
                "/usr/bin/ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                target,
                "python3 -c " + shlex.quote(script),
            ],
            input=payload,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    lines = (done.stdout.strip() or done.stderr.strip() or "no output").splitlines()
    return done.returncode, lines[-1][:200]


def load_hosts(*, home: Path) -> list[str]:
    path = home / HOSTS_FILE
    if not path.exists():
        return []
    lines = (
        line.split("#", 1)[0].strip() for line in path.read_text(encoding="utf-8").splitlines()
    )
    return [line for line in lines if line]


def live_pair(*, home: Path) -> tuple[str, str] | None:
    """A fingerprint of the live access token plus the account id, read locally."""
    cred = _object(path=live_creds_path(home=home))
    state = _object(path=home / ".claude.json")
    oauth = None if cred is None else jsonio.as_object(value=cred.get("claudeAiOauth"))
    account = None if state is None else jsonio.as_object(value=state.get("oauthAccount"))
    token = None if oauth is None else oauth.get("accessToken")
    account_id = None if account is None else account.get("accountUuid")
    if not isinstance(token, str) or not isinstance(account_id, str):
        return None
    return hashlib.sha256(token.encode()).hexdigest()[:12], account_id


def push_due(
    *,
    home: Path,
    delivery: caam_delivery_service.Delivery,
    now: float,
    run: Runner = run_ssh,
    retry_s: float = 30.0,
) -> dict[str, str]:
    """Push `delivery` to every listed host still behind it; return host -> outcome."""
    state = _load_state(home=home)
    due = [
        host
        for host in load_hosts(home=home)
        if _due(entry=state.get(host, {}), sequence=delivery.sequence, now=now, retry_s=retry_s)
    ]
    payload = json.dumps(asdict(delivery))

    with ThreadPoolExecutor(max_workers=max(1, len(due))) as pool:
        futures = {
            host: pool.submit(run, target=host, script=APPLY_SCRIPT, payload=payload)
            for host in due
        }
        results = {host: future.result() for host, future in futures.items()}
    outcomes: dict[str, str] = {}
    for host, (rc, line) in results.items():
        entry = state.setdefault(host, {})
        entry["last_attempt"] = now
        entry["attempt_sequence"] = delivery.sequence
        if rc == 0:
            entry.update(
                sequence=delivery.sequence,
                account_id=delivery.account_id,
                last_success=now,
                last_error="",
            )
        else:
            entry["last_error"] = line
        outcomes[host] = line
    _save_state(home=home, state=state)
    return outcomes


def status_lines(*, home: Path, now: float, stale_after: float = 900.0) -> list[str]:
    """One secret-free line per listed host."""
    state = _load_state(home=home)
    lines = ["host  account  last-push  state  last-error"]
    for host in load_hosts(home=home):
        entry = state.get(host, {})
        success = entry.get("last_success")
        when = (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(success))
            if isinstance(success, float)
            else "never"
        )
        fresh = isinstance(success, float) and now - success <= stale_after
        lines.append(
            f"{host}  {entry.get('account_id', '-')}  {when}  "
            f"{'current' if fresh else 'stale'}  {entry.get('last_error', '') or '-'}"
        )
    return lines


def _due(*, entry: dict[str, object], sequence: int, now: float, retry_s: float) -> bool:
    applied = entry.get("sequence")
    if isinstance(applied, int) and applied >= sequence:
        return False
    attempted = entry.get("last_attempt")
    if entry.get("attempt_sequence") != sequence or not isinstance(attempted, float):
        return True
    return now - attempted >= retry_s


def _load_state(*, home: Path) -> dict[str, dict[str, object]]:
    body = _object(path=home / PUSH_STATE) or {}
    return {key: value for key, value in body.items() if isinstance(value, dict)}


def _save_state(*, home: Path, state: dict[str, dict[str, object]]) -> None:
    caam_delivery_service.write_private_json(path=home / PUSH_STATE, value=dict(state))


def _object(*, path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    return None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()
