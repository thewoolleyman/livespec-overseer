"""`caam-delivery-push`: the role holder's push service and its status command.

`caam-delivery-push run` follows the live credential and pushes each new
delivery to every listed host; `caam-delivery-push status` prints one
secret-free line per listed host.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from pathlib import Path

import caam_delivery_push
import caam_delivery_service
import streams
from caam_capacity_source import OAUTH_BETA_HEADER, PROFILE_URL
from caam_oauth_get import OAuthRequest, get_json

__all__: list[str] = ["POLL_INTERVAL_S", "confirm_live_account", "main", "run_once"]

POLL_INTERVAL_S = 5.0


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
    account_id = None if body is None else body.get("account_uuid")
    if isinstance(account_id, str):
        return account_id
    detail = reason if reason is not None else "no account identifier in the profile"
    streams.write_stderr(
        text=f"FAIL delivery account confirmation failed: {detail.replace(access_token, '')}\n"
    )
    return None


def run_once(
    *,
    home: Path,
    now: float,
    seen: tuple[str, str] | None,
    confirm: Callable[..., str | None] = confirm_live_account,
    run: caam_delivery_push.Runner = caam_delivery_push.run_ssh,
) -> tuple[str, str] | None:
    """One pass: issue a delivery when the live pair changed, then push to hosts behind it."""
    pair = caam_delivery_push.live_pair(home=home)
    if pair is not None and pair != seen:
        _ = caam_delivery_service.issue_delivery(home=home, now=now, confirm_account=confirm)
    delivery = caam_delivery_service.load_current_delivery(home=home)
    if delivery is not None:
        for host, outcome in caam_delivery_push.push_due(
            home=home, delivery=delivery, now=now, run=run
        ).items():
            streams.write_stdout(text=f"push {host} sequence {delivery.sequence}: {outcome}\n")
    return pair


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
        for line in caam_delivery_push.status_lines(home=home, now=time.time()):
            streams.write_stdout(text=line + "\n")
        return 0
    seen: tuple[str, str] | None = None
    done = 0
    while passes is None or done < passes:
        seen = run_once(home=home, now=time.time(), seen=seen)
        done += 1
        sleep(POLL_INTERVAL_S)
    return 0
