"""The supervised role-holder process for enrolled-host credential delivery."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import caam_delivery_runner
import streams
from caam_capacity_source import OAUTH_BETA_HEADER, PROFILE_URL
from caam_oauth_get import OAuthRequest, get_json

__all__: list[str] = ["POLL_INTERVAL_S", "confirm_live_account", "main", "run_forever"]

POLL_INTERVAL_S = 1.0


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


def run_forever(
    *, service: caam_delivery_runner.DeliveryService, wait: Callable[[float], None]
) -> None:
    """Poll the two live stores; systemd restarts this process if it stops."""
    while True:
        _ = service.refresh()
        wait(POLL_INTERVAL_S)


def main(
    *,
    argv: list[str] | None = None,
    runner: Callable[..., None] = run_forever,
) -> int:
    """Start the service; its process manager owns its lifecycle."""
    del argv
    service = caam_delivery_runner.DeliveryService(
        home=Path.home(),
        now=time.time,
        confirm_account=confirm_live_account,
    )
    runner(service=service, wait=time.sleep)
    return 0
