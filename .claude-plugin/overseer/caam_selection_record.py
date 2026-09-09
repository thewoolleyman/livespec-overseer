"""The published selection record: which account this host is spending.

Ratified in SPECIFICATION v049: contracts.md fixes this artifact's shape and
spec.md fixes when it is written. Both are cited at FILE level deliberately --
heading-level citations in source rot the first time a section is renamed.

The record exists for a CREDENTIAL CONSUMER -- a party outside the host's
interactive agent that bills against the same accounts under its own
separately-provisioned credential, which this operation neither stores,
installs, nor refreshes. Such a consumer cannot follow a rotation unless the
operation states which account it selected.

Two properties of this module are load-bearing and easy to erode:

- It carries NO read path, deliberately. `spec.md` requires that the operation
  MUST NOT read the record back as evidence of the active account, and the
  cheapest way to keep that true is to ship no function that could. Tests read
  the file directly.
- It never accepts a partial identity. The record names the account by BOTH the
  account-manager profile name AND the stable account identifier, and
  `contracts.md` says neither MAY be omitted -- a name-only record would follow
  a renamed profile to the wrong account, which is the whole hazard the
  identifier exists to close. A caller with no identifier does not get a
  degraded record; it gets no write at all.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

__all__: list[str] = [
    "SELECTION_RECORD_REL",
    "publish_selection",
    "selection_record_path",
]

# Beside the operation's durable store, per contracts.md ("MUST live in the same
# host state directory"), and a SEPARATE file from `state.json`: a consumer MUST
# NOT have to parse operation state to learn the selection, and a change to that
# cache's internal shape MUST NOT break one.
SELECTION_RECORD_REL: Final = Path(".local/state/caam-usage-rotate/selected-account.json")


def selection_record_path(*, home: Path) -> Path:
    return home / SELECTION_RECORD_REL


def publish_selection(
    *,
    profile: str,
    account_uuid: str | None,
    written_at: str,
    home: Path,
) -> bool:
    """Write the record for a FULLY determined account. Returns whether it wrote.

    `account_uuid` is accepted as optional and refused here rather than at every
    call site: a pass that determined the profile name but no identifier MUST
    suppress publication rather than degrade it, and centralising that refusal
    means a new caller cannot forget it.

    The write mirrors `caam_profile_state.save_state` exactly -- 0700 directory,
    write-then-chmod-then-replace -- so a consumer reading concurrently observes
    either the previous publication or the new one and never a partial file.
    """

    if not account_uuid:
        return False

    record_path = selection_record_path(home=home)
    record_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {
        "account_uuid": account_uuid,
        "profile": profile,
        "written_at": written_at,
    }
    tmp_path = record_path.with_name(record_path.name + ".tmp")
    _ = tmp_path.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    tmp_path.chmod(0o600)
    _ = tmp_path.replace(record_path)
    return True
