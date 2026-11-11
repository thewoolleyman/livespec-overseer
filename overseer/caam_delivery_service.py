"""Role-holder core for safe enrolled-host credential deliveries."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import caam_delivery_registry
import jsonio
from caam_profile_state import live_creds_path

__all__: list[str] = ["Delivery", "issue_delivery", "load_current_delivery"]

_STATE = ".local/state/caam-usage-rotate"


@dataclass(frozen=True, kw_only=True)
class Delivery:
    sequence: int
    account_id: str
    identity: dict[str, object]
    oauth: dict[str, object]


def issue_delivery(
    *, home: Path, now: float, confirm_account: Callable[..., str | None]
) -> Delivery | None:
    """Persist a greater sequence before making a refresh-token-free delivery current."""
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
    if not isinstance(token, str) or confirm_account(access_token=token) != account_id:
        return None
    current = load_current_delivery(home=home)
    if (
        current is not None
        and current.oauth.get("accessToken") == token
        and current.identity == identity
    ):
        return None
    with caam_delivery_registry.registry_lock(home=home):
        sequence = _sequence(home=home) + 1
        delivery = Delivery(
            sequence=sequence,
            account_id=account_id,
            identity=identity,
            oauth={key: value for key, value in oauth.items() if key != "refreshToken"},
        )
        _write(path=_path(home=home, name="delivery-sequence.json"), value={"sequence": sequence})
        _write(path=_path(home=home, name="current-delivery.json"), value=asdict(delivery))
    return delivery


def load_current_delivery(*, home: Path) -> Delivery | None:
    body = _object(path=_path(home=home, name="current-delivery.json"))
    if body is None:
        return None
    sequence = body.get("sequence")
    account_id = body.get("account_id")
    identity = jsonio.as_object(value=body.get("identity"))
    oauth = jsonio.as_object(value=body.get("oauth"))
    if not isinstance(sequence, int) or isinstance(sequence, bool):
        return None
    if not isinstance(account_id, str) or identity is None or oauth is None:
        return None
    return Delivery(sequence=sequence, account_id=account_id, identity=identity, oauth=oauth)


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


def _write(*, path: Path, value: dict[str, object]) -> None:
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
