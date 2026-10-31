"""Serialized switch execution for caam account rotation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Final

from _caam_switch_host import (
    SwitchLock,
    SwitchLockFactory,
    acquire_switch_lock,
    caam_activate,
)
from _caam_switch_recovery import post_install_outcome, restore_failure
from _caam_switch_render import target_summary
from _caam_switch_state import (
    LiveSwitchState,
    StateRestoreError,
    StateValidationError,
    apply_activated_state,
    capture_live_state,
    restore_rejected_state,
)
from _caam_switch_types import (
    ACTIVATE_TIMEOUT_S,
    REASON_FAIL_ACTIVATE,
    REASON_FAIL_DID_NOT_STICK,
    REASON_FAIL_ERROR,
    REASON_FAIL_POST_INSTALL_WRITE,
    REASON_FAIL_RESTORE,
    REASON_FAIL_STATE_VALIDATION,
    REASON_FAIL_TARGET_CREDENTIAL,
    REASON_HOLD_ACTIVE_CHANGED,
    REASON_SWITCHED,
    ActivateRunner,
    ActiveReader,
    CaamProcess,
    SaveState,
    SwitchRequest,
    SwitchResult,
    UsageFetcher,
)
from _caam_switch_verify import activation_message
from caam_decision import decision_switched
from caam_profile_state import caam_vault

__all__: list[str] = [
    "ACTIVATE_TIMEOUT_S",
    "LOCK_REL",
    "REASON_FAIL_ACTIVATE",
    "REASON_FAIL_DID_NOT_STICK",
    "REASON_FAIL_ERROR",
    "REASON_FAIL_POST_INSTALL_WRITE",
    "REASON_FAIL_RESTORE",
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

LOCK_REL: Final = Path(".local/state/caam-usage-rotate/switch.lock")
_TOOL: Final = "claude"
_HOLD_LOCKED: Final = "hold: another caam-anthropic-loop holds the switch lock"
REASON_HOLD_LOCK_HELD: Final = "hold-lock-held"


def switch_account(*, request: SwitchRequest) -> SwitchResult:
    try:
        return _switch_account_uncaught(request=request)
    except StateRestoreError as restoration:
        return restore_failure(request=request, restoration=restoration)
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
    preflight_failure = _preflight_failure(request=request)
    if preflight_failure is not None:
        return preflight_failure
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
    did_not_stick, post_install_failure = post_install_outcome(
        request=request,
        state=preserved_state,
        apply_state=apply_activated_state,
    )
    if post_install_failure is not None:
        return post_install_failure
    if did_not_stick:
        return _did_not_stick_failure(request=request, state=preserved_state)
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
                current_five_hour_remaining=request.current.five_hour_remaining or 0.0,
                target=target_summary(target=request.target, now=request.now),
            ),
        ),
    )


def _preflight_failure(*, request: SwitchRequest) -> SwitchResult | None:
    """Return a hold or refusal discovered before live-state capture."""
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
    return None


def _did_not_stick_failure(*, request: SwitchRequest, state: LiveSwitchState) -> SwitchResult:
    restore_rejected_state(state=state)
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
