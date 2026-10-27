"""Post-activation verification helpers for caam account switches."""

from __future__ import annotations

import json
from pathlib import Path

import jsonio
from caam_profile_state import caam_vault, live_creds_path
from caam_usage import read_creds

__all__: list[str] = ["activation_message", "switch_did_not_stick"]


def activation_message(*, stdout: str, stderr: str) -> str:
    """Select the useful diagnostic from an unsuccessful caam invocation."""
    return stderr.strip() or stdout.strip()


def switch_did_not_stick(*, home: Path, target_name: str) -> bool:
    """Whether activation left either live identity unlike its target snapshot."""
    target_home = caam_vault(home=home) / target_name
    target_token, _ = read_creds(
        path=target_home / ".credentials.json",
    )
    live_token, _ = read_creds(path=live_creds_path(home=home))
    target_oauth_account = _oauth_account(path=target_home / ".claude.json")
    live_oauth_account = _oauth_account(path=home / ".claude.json")
    return (
        target_token is None
        or target_token != live_token
        or target_oauth_account is None
        or target_oauth_account != live_oauth_account
    )


def _oauth_account(*, path: Path) -> dict[str, object] | None:
    """The complete oauthAccount object, or None when the profile cannot verify it."""
    parsed: object = json.loads(path.read_text(encoding="utf-8"))
    profile = jsonio.as_object(value=parsed)
    return jsonio.as_object(value=None if profile is None else profile.get("oauthAccount"))
