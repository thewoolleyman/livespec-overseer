"""The separate factory-account decision and identity-only record."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import jsonio
from caam_decision import ProfileUsage, five_hour_remaining_floor, rank_profiles, weekly_reserve
from caam_decision_protection import protection_floor_for, weekly_left
from caam_profile_state import caam_vault
from caam_profiles import account_uuid
from caam_refusal_hold import refusal_state

__all__: list[str] = [
    "FACTORY_SELECTION_RECORD_REL",
    "FactorySelection",
    "factory_selection",
    "publish_factory_selection",
]

FACTORY_SELECTION_RECORD_REL: Final = Path(
    ".local/state/caam-usage-rotate/factory-selected-account.json"
)
_NO_QUALIFYING_ACCOUNT: Final = "no managed account qualifies for factory selection"


@dataclass(frozen=True, kw_only=True)
class FactorySelection:
    profile: str | None
    account_uuid: str | None
    reason: str | None


def factory_selection(
    *,
    home: Path,
    profiles: tuple[ProfileUsage, ...],
    interactive_name: str,
    state: dict[str, object],
    protection_floors: Mapping[str, float],
    now: float,
) -> FactorySelection:
    """Choose only after interactive selection is final, without feeding it back."""
    held = refusal_state(state=state, profiles=profiles, active_name=interactive_name, now=now).held
    candidates = tuple(
        candidate
        for profile in profiles
        for candidate in (
            _candidate(
                profile=profile,
                home=home,
                interactive_name=interactive_name,
                protection_floors=protection_floors,
            ),
        )
        if candidate is not None and candidate.profile not in held
    )
    allowed = _prefer_unprotected(candidates=candidates, protection_floors=protection_floors)
    prior_uuid = _prior_account_uuid(home=home)
    kept = next((candidate for candidate in allowed if candidate.account_uuid == prior_uuid), None)
    if kept is not None:
        return kept
    if not allowed:
        return FactorySelection(profile=None, account_uuid=None, reason=_NO_QUALIFYING_ACCOUNT)
    allowed_names = {item.profile for item in allowed}
    ranked_profiles = tuple(profile for profile in profiles if profile.name in allowed_names)
    ranked = rank_profiles(profiles=ranked_profiles)
    return next(item for profile in ranked for item in allowed if item.profile == profile.name)


def publish_factory_selection(*, home: Path, selection: FactorySelection, written_at: str) -> None:
    """Atomically publish the factory decision with owner-only permissions."""
    record_path = home / FACTORY_SELECTION_RECORD_REL
    record_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {
        "account_uuid": selection.account_uuid,
        "profile": selection.profile,
        "reason": selection.reason,
        "written_at": written_at,
    }
    temporary = record_path.with_name(record_path.name + ".tmp")
    _ = temporary.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    temporary.chmod(0o600)
    _ = temporary.replace(record_path)


def _candidate(
    *,
    profile: ProfileUsage,
    home: Path,
    interactive_name: str,
    protection_floors: Mapping[str, float],
) -> FactorySelection | None:
    usage = profile.usage
    uuid = account_uuid(claude_json_path=caam_vault(home=home) / profile.name / ".claude.json")
    floor = protection_floor_for(name=profile.name, protection_floors=protection_floors)
    if (
        profile.name == interactive_name
        or profile.source != "live"
        or usage is None
        or uuid is None
        or usage.five_hour_remaining <= five_hour_remaining_floor()
        or usage.seven_day_remaining <= weekly_reserve()
        or weekly_left(usage=usage, protection_floor=floor) <= 0.0
    ):
        return None
    return FactorySelection(profile=profile.name, account_uuid=uuid, reason=None)


def _prefer_unprotected(
    *, candidates: tuple[FactorySelection, ...], protection_floors: Mapping[str, float]
) -> tuple[FactorySelection, ...]:
    unprotected = tuple(
        candidate
        for candidate in candidates
        if protection_floor_for(name=candidate.profile, protection_floors=protection_floors) == 0.0
    )
    return unprotected or candidates


def _prior_account_uuid(*, home: Path) -> str | None:
    try:
        value: object = json.loads(
            (home / FACTORY_SELECTION_RECORD_REL).read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    body = jsonio.as_object(value=value)
    if body is None:
        return None
    uuid = body.get("account_uuid")
    return uuid if isinstance(uuid, str) else None
