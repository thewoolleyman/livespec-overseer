"""Role-holder core for safe enrolled-host credential deliveries.

A delivery is held IN MEMORY by its caller; only the sequence counter is
persisted, so no access token is written to disk by delivery.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import caam_delivery_registry
import jsonio
from caam_profile_state import live_creds_path

__all__: list[str] = ["Delivery", "issue_delivery", "write_private_json"]

_STATE = ".local/state/caam-usage-rotate"


@dataclass(frozen=True, kw_only=True)
class Delivery:
    sequence: int
    account_id: str
    identity: dict[str, object]
    oauth: dict[str, object]


def issue_delivery(
    *,
    home: Path,
    now: float,
    confirm_account: Callable[..., str | None],
    last: Delivery | None = None,
) -> Delivery | None:
    """Persist a greater sequence, then return a refresh-token-free delivery held in memory."""
    _path(home=home, name="current-delivery.json").unlink(missing_ok=True)
    credential = _object(path=live_creds_path(home=home))
    state = _object(path=home / ".claude.json")
    if credential is None or state is None:
        return None
    oauth = jsonio.as_object(value=credential.get("claudeAiOauth"))
    identity = _identity(state=state)
    account = None if identity is None else jsonio.as_object(value=identity.get("oauthAccount"))
    account_id = None if account is None else account.get("accountUuid")
    if (
        oauth is None
        or identity is None
        or not _live(oauth=oauth, now=now)
        or not isinstance(account_id, str)
    ):
        return None
    token = oauth["accessToken"]
    if last is not None and last.oauth.get("accessToken") == token:
        return None
    if not isinstance(token, str) or confirm_account(access_token=token) != account_id:
        return None
    with caam_delivery_registry.registry_lock(home=home):
        sequence = _sequence(home=home) + 1
        delivery = Delivery(
            sequence=sequence,
            account_id=account_id,
            identity=identity,
            oauth={key: value for key, value in oauth.items() if key != "refreshToken"},
        )
        write_private_json(
            path=_path(home=home, name="delivery-sequence.json"), value={"sequence": sequence}
        )
    return delivery


def _identity(*, state: dict[str, object]) -> dict[str, object] | None:
    if "oauthAccount" not in state or "userID" not in state:
        return None
    return {key: state[key] for key in ("oauthAccount", "userID")}


def _live(*, oauth: dict[str, object], now: float) -> bool:
    token = oauth.get("accessToken")
    expiry = jsonio.as_float(value=oauth.get("expiresAt"))
    return isinstance(token, str) and token != "" and (expiry is None or expiry / 1000 > now)


def _sequence(*, home: Path) -> int:
    saved = _object(path=_path(home=home, name="delivery-sequence.json"))
    value = None if saved is None else saved.get("sequence")
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _object(*, path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    return None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()


def write_private_json(*, path: Path, value: dict[str, object]) -> None:
    """Atomically write `value` as JSON readable only by the owner."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        _ = handle.write(json.dumps(value, sort_keys=True))
        handle.flush()
        os.fsync(handle.fileno())
    _ = temporary.replace(path)


def _path(*, home: Path, name: str) -> Path:
    return home / _STATE / name
