"""`caam-delivery-push status`: one secret-free line per listed host, plus the role holder.

Host STATE is exactly one of not-converted, expired, stale, lagging or current,
the first that applies in that order. A host never pushed successfully reads
stale. Each row names the account its last-applied delivery carried, with the
profile name the vault gives it, that delivery's sequence and when it was
applied, the last successful push, and the last error with its time. The role
holder's live and caam-selected accounts are shown with their profile names,
and `diverged` when they differ, because hosts receive the LIVE login.
"""

from __future__ import annotations

import time
from pathlib import Path

import caam_delivery_push
import jsonio
from caam_profile_state import caam_vault, live_creds_path
from caam_profiles import account_uuid
from caam_selection_record import selection_record_path

__all__: list[str] = ["host_state", "profile_name", "status_lines"]


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
    if not isinstance(success, float) or now - success > stale_after:
        return "stale"
    applied = entry.get("sequence")
    return "lagging" if not isinstance(applied, int) or applied < current_sequence else "current"


def profile_name(*, home: Path, account: object) -> str:
    """The vault profile whose identity names `account`, or `-` when none does."""
    vault = caam_vault(home=home)
    if not isinstance(account, str) or not vault.is_dir():
        return "-"
    for profile in sorted(vault.iterdir(), key=lambda path: path.name):
        if (
            not profile.name.startswith("_")
            and account_uuid(claude_json_path=profile / ".claude.json") == account
        ):
            return profile.name
    return "-"


def status_lines(*, home: Path, now: float, reissue_available: bool) -> list[str]:
    """Host table, then the role holder's live and selected accounts."""
    config = caam_delivery_push.load_config(home=home)
    stale = float(str(config["stale_after_s"]))
    state = caam_delivery_push.load_state(home=home)
    counter = _object(path=home / caam_delivery_push.STATE_DIR / "delivery-sequence.json") or {}
    current = counter.get("sequence")
    sequence = current if isinstance(current, int) else 0
    lines = ["label  target  platform  state  account  sequence  applied  last-success  last-error"]
    for host in caam_delivery_push.load_hosts(home=home):
        entry = state.get(host.label, {})
        account = entry.get("account_id")
        lines.append(
            f"{host.label}  {host.target}  {host.platform}  "
            f"{host_state(entry=entry, current_sequence=sequence, now=now, stale_after=stale)}  "
            f"account {account if isinstance(account, str) else '-'}"
            f" profile {profile_name(home=home, account=account)}  "
            f"sequence {entry.get('sequence', '-')} applied {_when(value=entry.get('applied_at'))}"
            f"  last-success {_when(value=entry.get('last_success'))}  "
            f"last-error {_error(entry=entry)}"
        )
    live = account_uuid(claude_json_path=home / ".claude.json")
    selection = _object(path=selection_record_path(home=home)) or {}
    selected = selection.get("account_uuid")
    lines.append(
        f"role holder live account: {live or '-'} profile {profile_name(home=home, account=live)}"
    )
    lines.append(
        f"caam selected account: {selected if isinstance(selected, str) else '-'}"
        f" profile {profile_name(home=home, account=selected)}"
    )
    if live != selected:
        lines.append("diverged: hosts receive the live login, not caam's selected account")
    oauth = jsonio.as_object(
        value=(_object(path=live_creds_path(home=home)) or {}).get("claudeAiOauth")
    )
    expiry = None if oauth is None else jsonio.as_float(value=oauth.get("expiresAt"))
    if expiry is not None and expiry / 1000 <= now:
        lines.append("expired: the role holder's live credential has expired; not refreshed here")
    if not reissue_available:
        lines.append("remote-control: re-issue unavailable (remote_control_reissue.py not present)")
    return lines


def _when(*, value: object) -> str:
    if not isinstance(value, int | float):
        return "never"
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(value))


def _error(*, entry: dict[str, object]) -> str:
    error = entry.get("last_error")
    if not isinstance(error, str) or not error:
        return "-"
    return f"{error} at {_when(value=entry.get('last_error_at'))}"


def _object(*, path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    return None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()
