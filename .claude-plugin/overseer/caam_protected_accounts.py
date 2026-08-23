"""Protected account floor state for caam rotation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

import jsonio

__all__: list[str] = [
    "ProtectedAccounts",
    "apply_protected_accounts",
    "protected_account_default",
]

STATE_KEY: Final = "protected_accounts"
_CLEAR_VALUES: Final = frozenset(("auto", "none", "off"))
_DEFAULT_ENV: Final = "CAAM_ROTATE_PROTECTED_ACCOUNT_DEFAULT"
_DEFAULT_FLOOR: Final = "10"
_MAX_FLOOR = 100.0


@dataclass(frozen=True, kw_only=True)
class ProtectedAccounts:
    values: dict[str, float]
    messages: tuple[str, ...]

    def floor_for(self, *, account: str) -> float:
        return self.values.get(account, 0.0)

    def summary(self) -> str | None:
        if not self.values:
            return None
        pairs = ", ".join(f"{account}={floor:g}%" for account, floor in self.values.items())
        return f"protected-accounts: {pairs}"


def protected_account_default() -> float:
    return float(os.environ.get(_DEFAULT_ENV, _DEFAULT_FLOOR))


def apply_protected_accounts(
    *, state: dict[str, object], requested_accounts: tuple[tuple[str, str], ...]
) -> ProtectedAccounts:
    protected = dict(_stored_accounts(state=state))
    messages: list[str] = []
    for account, requested_floor in requested_accounts:
        _apply_requested_account(
            protected=protected,
            account=account,
            requested_floor=requested_floor,
            messages=messages,
        )
    if protected or requested_accounts or STATE_KEY in state:
        state[STATE_KEY] = protected
    summary = ProtectedAccounts(values=protected, messages=tuple(messages)).summary()
    if summary is not None:
        messages.append(summary)
    return ProtectedAccounts(values=protected, messages=tuple(messages))


def _stored_accounts(*, state: dict[str, object]) -> dict[str, float]:
    stored = jsonio.as_object(value=state.get(STATE_KEY)) or {}
    return {
        account: floor
        for account, value in stored.items()
        if isinstance(value, int | float) and _floor_allowed(floor=(floor := float(value)))
    }


def _apply_requested_account(
    *,
    protected: dict[str, float],
    account: str,
    requested_floor: str,
    messages: list[str],
) -> None:
    value = requested_floor.strip().lower()
    if not account:
        messages.append(_ignore_message(account=account, value=value))
        return
    if value in _CLEAR_VALUES:
        _ = protected.pop(account, None)
        return
    floor = _parsed_floor(value=value)
    if floor is None:
        messages.append(_ignore_message(account=account, value=value))
        return
    protected[account] = floor


def _parsed_floor(*, value: str) -> float | None:
    try:
        floor = protected_account_default() if value == "" else float(value)
    except ValueError:
        return None
    return floor if _floor_allowed(floor=floor) else None


def _floor_allowed(*, floor: float) -> bool:
    return 0.0 <= floor <= _MAX_FLOOR


def _ignore_message(*, account: str, value: str) -> str:
    return f"protected-accounts: ignoring --protected-account={account}={value}"
