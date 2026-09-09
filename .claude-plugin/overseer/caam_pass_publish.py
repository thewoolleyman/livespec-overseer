"""Publishing the selected account from within a rotation pass.

Ratified in SPECIFICATION v049; spec.md fixes when the record is written and
contracts.md fixes its shape. Both are cited at FILE level deliberately --
heading-level citations in source rot the first time a section is renamed.

This module holds the two call shapes a pass needs, so `caam_anthropic_pass`
composes publication rather than assembling it. That file owns the decision flow
and sits against its LLOC ceiling; where an account's identifier comes from is
this concern's business rather than the flow's.

The two entry points differ in ONE thing -- the source of the stable identifier --
and that difference is the point:

- `publish_determined` takes the identity the pass already resolved, whole.
- `publish_switched` runs after a switch MOVED the credential, and reads the
  destination profile's own stored snapshot. It deliberately does NOT read the
  live account file: that file is the account manager's to rewrite during a
  switch, so reading it here would race that write.

Neither returns anything. Whether a record was written is not a fact the pass
acts on, and returning it would invite a caller to branch on it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from caam_profile_state import caam_vault
from caam_profiles import ActiveIdentity, account_uuid
from caam_selection_record import publish_selection

__all__: list[str] = ["publish_determined", "publish_switched"]


def _stamp(*, now: float) -> str:
    """The pass's own instant, so a consumer reads one clock rather than two."""
    return datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def publish_determined(*, home: Path, now: float, active: ActiveIdentity) -> None:
    """Publish the account this pass determined active.

    The whole identity is taken rather than its two fields, so a caller cannot
    pair one account's name with another's identifier. A partial identity is
    refused by `publish_selection` itself, so a pass that named a profile but
    resolved no identifier writes nothing rather than a name-only record a
    consumer could follow to the wrong account.
    """

    _ = publish_selection(
        profile=active.profile,
        account_uuid=active.account_uuid,
        written_at=_stamp(now=now),
        home=home,
    )


def publish_switched(*, home: Path, now: float, profile: str) -> None:
    """Publish the account a completed switch moved onto."""

    snapshot = caam_vault(home=home) / profile / ".claude.json"
    _ = publish_selection(
        profile=profile,
        account_uuid=account_uuid(claude_json_path=snapshot),
        written_at=_stamp(now=now),
        home=home,
    )
