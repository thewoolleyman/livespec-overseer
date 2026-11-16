"""The live access-token fingerprint plus live account id the push loop watches."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonio
from caam_profile_state import live_creds_path
from caam_profiles import account_uuid

__all__: list[str] = ["live_pair"]


def live_pair(*, home: Path) -> tuple[str, str] | None:
    """A fingerprint of the live access token plus the live account id, read locally."""
    try:
        cred = json.loads(live_creds_path(home=home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    oauth = jsonio.as_object(value=jsonio.as_object(value=cred) and cred.get("claudeAiOauth"))
    token = None if oauth is None else oauth.get("accessToken")
    account = account_uuid(claude_json_path=home / ".claude.json")
    if not isinstance(token, str) or account is None:
        return None
    return hashlib.sha256(token.encode()).hexdigest()[:12], account
