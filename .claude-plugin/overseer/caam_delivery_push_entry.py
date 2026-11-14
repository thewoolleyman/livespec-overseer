"""`caam-delivery-push`: the role holder's push service and its status command.

`caam-delivery-push run` follows the live credential and pushes each new
delivery to every listed host; the delivery lives only in this process's
memory. `caam-delivery-push status` prints one secret-free line per host.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import caam_delivery_push
import caam_delivery_push_state
import caam_delivery_push_status
import caam_delivery_service
import jsonio
import streams
from caam_capacity_source import OAUTH_BETA_HEADER, PROFILE_URL
from caam_oauth_get import OAuthRequest, get_json
from caam_profile_state import live_creds_path
from caam_profiles import account_uuid

__all__: list[str] = [
    "POLL_INTERVAL_S",
    "PushLoop",
    "confirm_live_account",
    "main",
    "run_local",
    "run_once",
    "start_local",
]

POLL_INTERVAL_S = 5.0
_REISSUE_PATH = Path(__file__).with_name("remote_control_reissue.py")


@dataclass(kw_only=True)
class PushLoop:
    """What one run of the service remembers between passes, in memory only."""

    seen: tuple[str, str] | None = None
    last: caam_delivery_service.Delivery | None = None
    retry_at: float | None = None
    reissued_for: str | None = None


def confirm_live_account(*, access_token: str) -> str | None:
    """Read the account identity through the one permitted provider GET."""
    body, reason = get_json(
        request=OAuthRequest(
            url=PROFILE_URL,
            headers={
                "Authorization": "Bearer " + access_token,
                "anthropic-beta": OAUTH_BETA_HEADER,
            },
        )
    )
    account = None if body is None else jsonio.as_object(value=body.get("account"))
    account_id = None if account is None else account.get("uuid")
    if isinstance(account_id, str):
        return account_id
    detail = reason if reason is not None else "no account identifier in the profile"
    streams.write_stderr(
        text="FAIL delivery account confirmation failed: "
        + detail.replace(access_token, "[redacted]")
        + "\n"
    )
    return None


def run_local(*, script: str, timeout: float = caam_delivery_push_state.REISSUE_TIMEOUT_S) -> str:
    """Run the re-issue script on this host's own panes, fed on stdin; return its last line."""
    try:
        done = subprocess.run(  # noqa: S603 - fixed interpreter, repo-shipped script
            [sys.executable, "-"],
            input=script,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as error:
        return f"failed {type(error).__name__}"
    lines = done.stdout.strip().splitlines()
    return (
        caam_delivery_push_state.scrubbed(text=lines[-1])
        if lines
        else f"failed exit {done.returncode}"
    )


def start_local(*, script: str) -> str:
    """Start the role holder's re-issue on a daemon thread; its result line follows when done.

    The script re-scans for its whole window, and the role holder fires it before
    the switch's delivery is issued, so waiting for it would hold every listed
    host's delivery back by as long.
    """

    def report() -> None:
        streams.write_stdout(text=f"remote-control role holder: {run_local(script=script)}\n")

    threading.Thread(target=report, name="remote-control-reissue", daemon=True).start()
    return "started"


def run_once(  # noqa: PLR0913 - each argument is an independent seam
    *,
    home: Path,
    now: float,
    loop: PushLoop,
    confirm: Callable[..., str | None] = confirm_live_account,
    run: caam_delivery_push.Runner = caam_delivery_push.run_ssh,
    reissue: str | None = None,
    local: Callable[..., str] = start_local,
    start: caam_delivery_push.Starter = caam_delivery_push.start_in_background,
) -> None:
    """One pass: issue a delivery when the live file changed, then push to hosts behind it."""
    marker = _live_pair(home=home)
    if marker is not None:
        _reissue_on_switch(loop=loop, account=marker[1], reissue=reissue, local=local)
    retry_due = loop.retry_at is not None and now >= loop.retry_at
    if marker is not None and (marker != loop.seen or retry_due):
        loop.seen = marker
        loop.retry_at = None
        answers: list[str | None] = []

        def confirming(**kwargs: object) -> str | None:
            answers.append(confirm(**kwargs))
            return answers[-1]

        issued = caam_delivery_service.issue_delivery(
            home=home, now=now, confirm_account=confirming, last=loop.last
        )
        if issued is None and None in answers:
            # A failed request is not an answer: ask again after the retry
            # interval. A different account IS one, and waits for a change.
            settings = caam_delivery_push.load_config(home=home)
            loop.retry_at = now + caam_delivery_push_state.seconds(settings=settings, key="retry_s")
        if issued is not None:
            _reissue_on_switch(loop=loop, account=issued.account_id, reissue=reissue, local=local)
            loop.last = issued
    if loop.last is not None:
        outcomes = caam_delivery_push.push_due(
            home=home, delivery=loop.last, now=now, run=run, reissue=reissue, start=start
        )
        for label, outcome in outcomes.items():
            streams.write_stdout(text=f"push {label} sequence {loop.last.sequence}: {outcome}\n")


def _reissue_on_switch(
    *, loop: PushLoop, account: str, reissue: str | None, local: Callable[..., str]
) -> None:
    """Re-issue Remote Control on the role holder once per switch of its account.

    Spec v103 fires it after the rotation switches the live login AND after a
    delivery names a different account; the coordinator's grade of #2990 has it
    fire on whichever is seen first, once. A switch whose confirmation fails
    issues no delivery, so waiting for the delivery alone missed it. The first
    account seen in a run is only recorded: what preceded it is unknown.
    """
    previous, loop.reissued_for = loop.reissued_for, account
    if previous is None or previous == account:
        return
    line = "re-issue unavailable" if reissue is None else local(script=reissue)
    streams.write_stdout(text=f"remote-control role holder: {line}\n")


def _live_pair(*, home: Path) -> tuple[str, str] | None:
    """A fingerprint of the live access token plus the live account id, read locally."""
    try:
        cred = json.loads(live_creds_path(home=home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    oauth = jsonio.as_object(value=jsonio.as_object(value=cred) and cred.get("claudeAiOauth"))
    token = None if oauth is None else oauth.get("accessToken")
    account = account_uuid(claude_json_path=home / ".claude.json")
    if not isinstance(token, str) or account is None:
        return None
    return hashlib.sha256(token.encode()).hexdigest()[:12], account


def main(
    *,
    argv: list[str] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    passes: int | None = None,
) -> int:
    """`run` (default) loops forever under systemd; `status` prints and exits."""
    home = Path.home()
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["status"]:
        lines = caam_delivery_push_status.status_lines(
            home=home, now=time.time(), reissue_available=_REISSUE_PATH.is_file()
        )
        for line in lines:
            streams.write_stdout(text=line + "\n")
        return 0
    loop = PushLoop()
    done = 0
    while passes is None or done < passes:
        script = caam_delivery_push.reissue_script(path=_REISSUE_PATH)
        run_once(home=home, now=time.time(), loop=loop, reissue=script)
        done += 1
        sleep(POLL_INTERVAL_S)
    return 0
