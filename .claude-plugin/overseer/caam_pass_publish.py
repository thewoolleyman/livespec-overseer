"""Publishing the selected account from within a rotation pass.

Ratified in SPECIFICATION v049; spec.md fixes when the record is written and
contracts.md fixes its shape. Both are cited at FILE level deliberately --
heading-level citations in source rot the first time a section is renamed.

This module owns WHEN a pass publishes and WHAT A FAILED PUBLICATION DOES TO
IT, so `caam_anthropic_pass` composes publication rather than assembling it.
That file owns the decision flow and sits against its LLOC ceiling; where an
account's identifier comes from, and which outcomes forfeit the write, are this
concern's business rather than the flow's.

Publication is answered ONCE per pass, which is what `PassPublication.settled`
records. Three outcomes settle it, and the reasons differ:

- A completed switch publishes the DESTINATION profile, read from that profile's
  own stored snapshot. It deliberately does NOT read the live account file: that
  file is the account manager's to rewrite during a switch, so reading it here
  would race that write. The record must end the pass naming the account now in
  use, so this write wins over the determined one.
- A pass that could not take the lock serializing the decision-and-switch
  sequence publishes NOTHING. The caller holding that lock is deciding the very
  fact the record states, so the write is that caller's to make, and a
  well-meaning republication here would overwrite a fresher truth with a stale
  one.
- Every other outcome publishes the identity the pass determined, whole. The
  whole identity is carried rather than its two fields, so no path can pair one
  account's name with another's identifier. A partial identity is refused by
  `publish_selection` itself, so a pass that named a profile but resolved no
  identifier writes nothing rather than a name-only record a consumer could
  follow to the wrong account.

An unresolved identifier has TWO consequences -- the record is suppressed AND
the condition is reported -- and they are one fact about the pass, so
`pass_publication` performs both. Splitting them let a caller do one without the
other, which is how a silent suppression ships.

Nothing here returns whether a record was written. Whether it was is not a fact
the pass acts on, and returning it would invite a caller to branch on it. What
DOES cross back is the exit code, because spec.md makes a failed publication a
failure path: it is reported on a clearly-marked line and the pass exits
non-zero, having already reported its table and persisted its state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from caam_anthropic_finish import LineWriter
from caam_decide_context import DecisionContext
from caam_profile_state import caam_vault
from caam_profiles import ActiveIdentity, account_uuid, unresolved_identity_note
from caam_selection_record import publish_selection

__all__: list[str] = ["PassPublication", "pass_publication", "pass_stamp"]

# `FAIL` because that is the prefix the operator contract keys on: a pass whose
# publication failed IS a failed pass, however complete the rest of its work.
_FAIL_PUBLISH: Final = "FAIL could not publish the selected account record"


def pass_stamp(*, now: float) -> str:
    """The pass's own instant, so every surface it stamps reads one clock."""
    return datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(kw_only=True)
class PassPublication:
    """One pass's publication: whether it still owes a write, and how it went."""

    home: Path
    now: float
    active: ActiveIdentity
    stdout: LineWriter
    settled: bool = False
    failed: bool = False

    def suppress(self) -> None:
        """Forfeit this pass's write, without recording a failure.

        Called where another caller holds the decision lock. Nothing is wrong;
        the fact the record states simply is not this pass's to state.
        """

        self.settled = True

    def publish_switched(self, *, profile: str) -> None:
        """Publish the account a completed switch moved onto."""

        snapshot = caam_vault(home=self.home) / profile / ".claude.json"
        self._write(profile=profile, uuid=account_uuid(claude_json_path=snapshot))

    def publish(self, *, code: int) -> int:
        """Publish the determined identity if still owed, and return the pass's code.

        A no-op on a pass already settled by a switch or by lock contention, so
        it can be called unconditionally at the end of the flow. The code is
        raised to two ONLY by a publication that failed -- a successful write
        never changes an exit code it did not earn.
        """

        self._write(profile=self.active.profile, uuid=self.active.account_uuid)
        return 2 if self.failed else code

    def _write(self, *, profile: str, uuid: str | None) -> None:
        if self.settled:
            return
        self.settled = True
        try:
            _ = publish_selection(
                profile=profile,
                account_uuid=uuid,
                written_at=pass_stamp(now=self.now),
                home=self.home,
            )
        except OSError as exc:
            # Reported and carried, never raised: the rotation and the report are
            # complete work, and unwinding the pass to signal a failed publication
            # would cost more than the failure it reports.
            self.failed = True
            self.stdout(f"{_FAIL_PUBLISH}: {exc}")


def pass_publication(*, context: DecisionContext, active: ActiveIdentity) -> PassPublication:
    """Open publication for a pass, reporting an identity it could not fully resolve.

    The note is emitted HERE, at the moment the pass's identity becomes known,
    because the same gap that reports it is the gap that suppresses the write --
    and because a pass that later fails to read usage exits before its table and
    would otherwise say nothing about it. It is a reported condition, not a
    failure path, so it never touches the exit code.
    """

    if active.account_uuid is None:
        context.stdout(unresolved_identity_note(profile=active.profile))
    return PassPublication(
        home=context.home,
        now=context.now,
        active=active,
        stdout=context.stdout,
    )
