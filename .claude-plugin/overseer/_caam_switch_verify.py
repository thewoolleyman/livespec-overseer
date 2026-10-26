"""Post-activation verification helpers for caam account switches."""

from __future__ import annotations

from pathlib import Path

from caam_profile_state import caam_vault, live_creds_path
from caam_usage import read_creds

__all__: list[str] = ["activation_message", "switch_did_not_stick"]


def activation_message(*, stdout: str, stderr: str) -> str:
    """Select the useful diagnostic from an unsuccessful caam invocation."""
    return stderr.strip() or stdout.strip()


def switch_did_not_stick(*, home: Path, target_name: str) -> bool:
    """Whether activation left the live credential unlike its vault snapshot."""
    target_token, _ = read_creds(
        path=caam_vault(home=home) / target_name / ".credentials.json",
    )
    live, _ = read_creds(path=live_creds_path(home=home))
    return target_token is not None and live is not None and target_token != live
