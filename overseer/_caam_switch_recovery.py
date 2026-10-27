"""Post-install recovery and reporting for a rejected caam account switch."""

from __future__ import annotations

import subprocess

from _caam_switch_state import (
    LiveSwitchState,
    StateRestoreError,
    apply_activated_state,
    restore_rejected_state,
)
from _caam_switch_types import (
    REASON_FAIL_POST_INSTALL_WRITE,
    REASON_FAIL_RESTORE,
    SwitchRequest,
    SwitchResult,
)
from _caam_switch_verify import switch_did_not_stick

__all__: list[str] = ["post_install_outcome"]


def post_install_outcome(
    *, request: SwitchRequest, state: LiveSwitchState
) -> tuple[bool, SwitchResult | None]:
    """Repair installed state or name every live file whose restoration failed."""
    try:
        apply_activated_state(state=state)
        return (
            switch_did_not_stick(home=request.home, target_name=request.target.name),
            None,
        )
    except (OSError, RuntimeError, subprocess.SubprocessError, TypeError, ValueError) as exc:
        try:
            restore_rejected_state(state=state)
        except StateRestoreError as restoration:
            request.save(state=request.state)
            return (
                False,
                SwitchResult(
                    exit_code=2,
                    reason=REASON_FAIL_RESTORE,
                    lines=(
                        "FAIL switch to "
                        f"{request.target.name}: post-install write failed "
                        f"({type(exc).__name__}: {exc}); restoration failed for "
                        f"{', '.join(str(path) for path in restoration.paths)}.",
                    ),
                ),
            )
        request.save(state=request.state)
        return (
            False,
            SwitchResult(
                exit_code=2,
                reason=REASON_FAIL_POST_INSTALL_WRITE,
                lines=(
                    "FAIL switch to "
                    f"{request.target.name}: post-install write failed "
                    f"({type(exc).__name__}: {exc}); restored pre-switch state.",
                ),
            ),
        )
