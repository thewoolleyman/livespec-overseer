"""`caam-delivery-push status`: one secret-free line per listed host, plus the role holder.

Host STATE is one of current, lagging, stale, not-converted, expired or failed.
The role holder's live profile and caam's selected profile are shown, with
`diverged` when they differ, because hosts receive the LIVE login.
"""

from __future__ import annotations

import time
from pathlib import Path

import caam_delivery_push
import jsonio
from caam_profile_state import caam_vault, live_creds_path
from caam_profiles import account_uuid
from caam_selection_record import selection_record_path

__all__: list[str] = ["host_state", "status_lines"]


def host_state(
    *, entry: dict[str, object], current_sequence: int, now: float, stale_after: float
) -> str:
    """The one STATE word for a host's push record."""
    success = entry.get("last_success")
    expires = entry.get("expires_at")
    if entry.get("state") == "not-converted":
        return "not-converted"
    if isinstance(expires, int | float) and expires / 1000 <= now:
        return "expired"
    if entry.get("state") == "failed":
        return "failed"
    if not isinstance(success, float) or now - success > stale_after:
        return "stale"
    applied = entry.get("sequence")
    return "lagging" if not isinstance(applied, int) or applied < current_sequence else "current"


def status_lines(*, home: Path, now: float, reissue_available: bool) -> list[str]:
    """Host table, then the role holder's live and selected profiles."""
    config = caam_delivery_push.load_config(home=home)
    stale = float(str(config["stale_after_s"]))
    state = caam_delivery_push.load_state(home=home)
    counter = _object(path=home / ".local/state/caam-usage-rotate/delivery-sequence.json") or {}
    current = counter.get("sequence")
    sequence = current if isinstance(current, int) else 0
    lines = ["label  target  platform  state  sequence  last-success  last-error"]
    for host in caam_delivery_push.load_hosts(home=home):
        entry = state.get(host.label, {})
        success = entry.get("last_success")
        when = (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(success))
            if isinstance(success, float)
            else "never"
        )
        lines.append(
            f"{host.label}  {host.target}  {host.platform}  "
            f"{host_state(entry=entry, current_sequence=sequence, now=now, stale_after=stale)}  "
            f"{entry.get('sequence', '-')}  {when}  {entry.get('last_error', '') or '-'}"
        )
    live = _live_profile(home=home)
    selection = _object(path=selection_record_path(home=home)) or {}
    selected = selection.get("profile")
    lines.append(f"role holder live profile: {live or '-'}")
    lines.append(f"caam selected profile: {selected or '-'}")
    if account_uuid(claude_json_path=home / ".claude.json") != selection.get("account_uuid"):
        lines.append("diverged: hosts receive the live login, not caam's selected profile")
    oauth = jsonio.as_object(
        value=(_object(path=live_creds_path(home=home)) or {}).get("claudeAiOauth")
    )
    expiry = None if oauth is None else jsonio.as_float(value=oauth.get("expiresAt"))
    if expiry is not None and expiry / 1000 <= now:
        lines.append("expired: the role holder's live credential has expired; not refreshed here")
    if not reissue_available:
        lines.append("remote-control: re-issue unavailable (remote_control_reissue.py not present)")
    return lines


def _live_profile(*, home: Path) -> str | None:
    live = account_uuid(claude_json_path=home / ".claude.json")
    vault = caam_vault(home=home)
    if live is None or not vault.is_dir():
        return live
    for profile in sorted(vault.iterdir(), key=lambda path: path.name):
        if (
            not profile.name.startswith("_")
            and account_uuid(claude_json_path=profile / ".claude.json") == live
        ):
            return profile.name
    return live


def _object(*, path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    return None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()
