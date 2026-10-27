"""Serialized switch execution for caam account rotation."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from _caam_switch_host import (
    SwitchLock,
    SwitchLockFactory,
    acquire_switch_lock,
    caam_activate,
)
from _caam_switch_render import target_summary
from _caam_switch_state import (
    LiveSwitchState,
    StateValidationError,
    apply_activated_state,
    capture_live_state,
    restore_rejected_state,
)
from _caam_switch_types import (
    ActivateRunner,
    ActiveReader,
    CaamProcess,
    SaveState,
    UsageFetcher,
)
from _caam_switch_verify import activation_message, switch_did_not_stick
from caam_decision import ProfileUsage, UsageRecord, decision_switched
from caam_profile_state import caam_vault

__all__: list[str] = [
    "ACTIVATE_TIMEOUT_S",
    "LOCK_REL",
    "REASON_FAIL_ACTIVATE",
    "REASON_FAIL_DID_NOT_STICK",
    "REASON_FAIL_ERROR",
    "REASON_FAIL_STATE_VALIDATION",
    "REASON_FAIL_TARGET_CREDENTIAL",
    "REASON_HOLD_ACTIVE_CHANGED",
    "REASON_HOLD_LOCK_HELD",
    "REASON_SWITCHED",
    "ActivateRunner",
    "ActiveReader",
    "CaamProcess",
    "SaveState",
    "SwitchLock",
    "SwitchLockFactory",
    "SwitchRequest",
    "SwitchResult",
    "UsageFetcher",
    "acquire_switch_lock",
    "caam_activate",
    "switch_account",
]

ACTIVATE_TIMEOUT_S: Final = 60.0
LOCK_REL: Final = Path(".local/state/caam-usage-rotate/switch.lock")
_TOOL: Final = "claude"
_HOLD_LOCKED: Final = "hold: another caam-anthropic-loop holds the switch lock"

# The seven outcomes a switch attempt can reach, named HERE rather than
# reconstructed downstream from the operator lines below. Two of them exit ZERO
# without moving anything and three exit two for entirely different causes, so a
# reader keyed on the exit code alone cannot tell a lock contention from a
# credential that would have broken every running session.
REASON_SWITCHED: Final = "switched"
REASON_HOLD_LOCK_HELD: Final = "hold-lock-held"
REASON_HOLD_ACTIVE_CHANGED: Final = "hold-active-changed"
REASON_FAIL_TARGET_CREDENTIAL: Final = "fail-target-credential"
REASON_FAIL_ACTIVATE: Final = "fail-activate"
REASON_FAIL_DID_NOT_STICK: Final = "fail-did-not-stick"
REASON_FAIL_ERROR: Final = "fail-error"
REASON_FAIL_STATE_VALIDATION: Final = "fail-state-validation"


@dataclass(frozen=True, kw_only=True)
class SwitchResult:
    exit_code: int
    lines: tuple[str, ...]
    # Which of the seven outcomes above this is. Required rather than defaulted:
    # every branch that builds a result knows why it got there, and a default would
    # let a new one ship reporting somebody else's reason.
    reason: str
    # True on the ONE path that actually moved the live credential. An exit code
    # of zero does not mean that: a lock held by another pass, and an active
    # account that changed while this pass was deciding, both hold successfully
    # and return zero. Anything keyed on the code alone would treat those as
    # switches.
    switched: bool = False


@dataclass(frozen=True, kw_only=True)
class SwitchRequest:
    active_name: str
    target: ProfileUsage
    current: UsageRecord
    state: dict[str, object]
    home: Path
    now: float
    active_reader: ActiveReader
    fetcher: UsageFetcher
    activator: ActivateRunner
    lock_factory: SwitchLockFactory
    save: SaveState


def switch_account(*, request: SwitchRequest) -> SwitchResult:
    try:
        return _switch_account_uncaught(request=request)
    except (OSError, RuntimeError, subprocess.SubprocessError, TypeError, ValueError) as exc:
        request.save(state=request.state)
        return SwitchResult(
            exit_code=2,
            reason=REASON_FAIL_ERROR,
            lines=(f"FAIL {type(exc).__name__}: {exc}",),
        )


def _switch_account_uncaught(*, request: SwitchRequest) -> SwitchResult:
    lock = request.lock_factory(lock_path=request.home / LOCK_REL)
    if lock is None:
        request.save(state=request.state)
        return SwitchResult(exit_code=0, reason=REASON_HOLD_LOCK_HELD, lines=(_HOLD_LOCKED,))

    with lock:
        return _switch_under_lock(request=request)


def _switch_under_lock(*, request: SwitchRequest) -> SwitchResult:
    active_under_lock = request.active_reader()
    if active_under_lock != request.active_name:
        request.save(state=request.state)
        return SwitchResult(
            exit_code=0,
            reason=REASON_HOLD_ACTIVE_CHANGED,
            lines=(
                "hold: active changed "
                f"{request.active_name} -> {active_under_lock} while deciding; "
                "re-evaluating next tick",
            ),
        )
    usage, why = request.fetcher(
        creds_path=caam_vault(home=request.home) / request.target.name / ".credentials.json",
        now=request.now,
    )
    if usage is None:
        request.save(state=request.state)
        return SwitchResult(
            exit_code=2,
            reason=REASON_FAIL_TARGET_CREDENTIAL,
            lines=(
                "FAIL refusing to switch to "
                f"{request.target.name} -- its stored credential does not work right now "
                f"({why}). Installing it would break every running session.",
            ),
        )
    try:
        preserved_state = capture_live_state(home=request.home, target_name=request.target.name)
    except (OSError, StateValidationError) as exc:
        request.save(state=request.state)
        return SwitchResult(
            exit_code=2,
            reason=REASON_FAIL_STATE_VALIDATION,
            lines=(f"FAIL refusing to switch: {exc}",),
        )
    activation_failure = _activate(request=request, state=preserved_state)
    if activation_failure is not None:
        return activation_failure
    try:
        apply_activated_state(state=preserved_state)
        did_not_stick = switch_did_not_stick(home=request.home, target_name=request.target.name)
    except (OSError, RuntimeError, subprocess.SubprocessError, TypeError, ValueError):
        restore_rejected_state(state=preserved_state)
        raise
    if did_not_stick:
        restore_rejected_state(state=preserved_state)
        request.save(state=request.state)
        return SwitchResult(
            exit_code=2,
            reason=REASON_FAIL_DID_NOT_STICK,
            lines=(
                "FAIL switch to "
                f"{request.target.name} did not take effect -- the live credential or "
                "oauthAccount no longer matches the target snapshot. A running Claude session "
                "most likely refreshed its own identity over the swap. Re-run to retry.",
            ),
        )
    request.state["last_switch"] = {
        "at": request.now,
        "from": request.active_name,
        "to": request.target.name,
    }
    request.save(state=request.state)
    return SwitchResult(
        exit_code=0,
        reason=REASON_SWITCHED,
        switched=True,
        lines=(
            decision_switched(
                active_name=request.active_name,
                current_five_hour_remaining=request.current.five_hour_remaining,
                target=target_summary(target=request.target, now=request.now),
            ),
        ),
    )


def _activate(*, request: SwitchRequest, state: LiveSwitchState) -> SwitchResult | None:
    try:
        process = request.activator(
            args=("activate", _TOOL, request.target.name),
            timeout=ACTIVATE_TIMEOUT_S,
        )
    except (OSError, RuntimeError, subprocess.SubprocessError, TypeError, ValueError):
        restore_rejected_state(state=state)
        raise
    if process.returncode == 0:
        return None
    restore_rejected_state(state=state)
    request.save(state=request.state)
    return SwitchResult(
        exit_code=2,
        reason=REASON_FAIL_ACTIVATE,
        lines=(
            f"FAIL caam activate {request.target.name}: "
            f"{activation_message(stdout=process.stdout, stderr=process.stderr)}",
        ),
    )
