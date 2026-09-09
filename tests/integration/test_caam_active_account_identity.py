"""Integration-tier coverage for the v049 identity clauses of the rotation pass.

Tier: `tests.integration` is one of the documented governed scenario tiers.

Scenario: "The stable account identifier is resolved even when the account manager
names the profile" (SPECIFICATION/scenarios.md), plus the reported-condition half
of spec.md's "An unresolved identifier is a reported condition, not a failure
path".

HOW THESE LEGS MEASURE THE RESOLUTION. In this slice the resolved identifier has
exactly ONE operator-facing consequence -- the absence of the unresolved-identity
condition line; publication is a later slice under the same plan epic. So the
legs are read TOGETHER: leg 3 shows the same pass, driven the same way, DOES emit
that line when neither identity source carries an identifier, which is what makes
its absence in legs 1 and 2 evidence of a resolution rather than of silence. Legs
1 and 2 also separate the two sources the ratified clause names, the live account
file and the account's stored snapshot: each leg leaves only ONE of them able to
answer, so between them they prove the pass reads both.

Only process boundaries are seamed -- the account manager subprocess, the usage
endpoint, and the state file -- and `home=` is injected, so no leg touches real
host state.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from caam_anthropic_loop import Flags
from caam_anthropic_pass import run_pass
from caam_decision import UsageRecord

__all__: list[str] = []

pytestmark = pytest.mark.integration

NAMED_PROFILE = "active"
CAAM_STATUS = json.dumps({"tools": [{"tool": "claude", "active_profile": NAMED_PROFILE}]})


class _FakeCaam:
    """The account manager subprocess, whose report NAMES the active profile."""

    returncode = 0
    stdout = CAAM_STATUS
    stderr = ""


def _usage() -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=80.0,
        seven_day_remaining=70.0,
        five_hour_resets_at="2026-09-09T12:00:00Z",
        seven_day_resets_at="2026-09-11T00:00:00Z",
        fable_remaining=90.0,
        fable_resets_at="2026-09-11T00:00:00Z",
    )


def _flags() -> Flags:
    return Flags(
        scheduled=True,
        force=False,
        dry_run=False,
        no_models=True,
        no_warm=True,
        session_models=(),
        protected_accounts=(),
    )


def _home(*, tmp_path: Path, live_uuid: str | None, snapshot_uuid: str | None) -> Path:
    """A host whose two identity sources carry only what a leg wants them to.

    The vault holds a second profile so the pass has a fleet to render, and NEITHER
    profile's snapshot carries the live account's identifier unless a leg asks for
    it -- so the identity fallback could not name the active profile, and a pass
    that determines one has done so from the account manager's report.
    """
    vault = tmp_path / ".local/share/caam/vault/claude"
    for name in (NAMED_PROFILE, "other"):
        (vault / name).mkdir(parents=True)
    _write_account_file(path=tmp_path / ".claude.json", uuid=live_uuid)
    if snapshot_uuid is not None:
        _write_account_file(path=vault / NAMED_PROFILE / ".claude.json", uuid=snapshot_uuid)
    return tmp_path


def _write_account_file(*, path: Path, uuid: str | None) -> None:
    account: dict[str, object] = {} if uuid is None else {"accountUuid": uuid}
    path.write_text(json.dumps({"oauthAccount": account}), encoding="utf-8")


def _run(*, home: Path) -> tuple[int, list[str]]:
    lines: list[str] = []
    code = run_pass(
        flags=_flags(),
        home=home,
        now=1789000000.0,
        stdout=lines.append,
        caam_runner=lambda *, args: _FakeCaam(),
        fetcher=lambda *, creds_path, now=None: (_usage(), None),
        save_state=lambda *, state, state_path: None,
    )
    return code, lines


def _current_row(*, lines: list[str]) -> str:
    return next(line for line in lines if "✅" in line)


def _identity_notes(*, lines: list[str]) -> list[str]:
    """Every report line stating the active account's identifier went unresolved.

    Matched on what an OPERATOR reads -- a `note:` line about the stable account
    identifier -- rather than on a constant imported from the implementation, so a
    report that stopped saying it cannot pass by agreeing with itself.
    """
    return [
        line for line in lines if line.startswith("note: ") and "stable account identifier" in line
    ]


def test_a_pass_named_by_the_account_manager_still_resolves_the_stable_identifier(
    *, tmp_path: Path
) -> None:
    """LEG 1 -- the scenario. The account manager's report names the profile, so the
    identity fallback is not needed; the pass determines the account AND resolves
    its stable identifier from the live account file, which is the only source that
    carries one here."""
    code, lines = _run(home=_home(tmp_path=tmp_path, live_uuid="live-uuid", snapshot_uuid=None))

    # The fallback could not have named it: no snapshot carries the live identifier,
    # so a determined active account proves the account manager's report answered.
    assert code == 0
    assert NAMED_PROFILE in _current_row(lines=lines)
    assert _identity_notes(lines=lines) == []


def test_a_named_profile_resolves_its_identifier_from_its_stored_snapshot(
    *, tmp_path: Path
) -> None:
    """LEG 2. The other source the ratified clause names. The live account file
    carries no identifier -- it can be absent, unreadable, or mid-rewrite -- and the
    named profile's own stored snapshot answers for the same account."""
    code, lines = _run(home=_home(tmp_path=tmp_path, live_uuid=None, snapshot_uuid="snapshot-uuid"))

    assert code == 0
    assert NAMED_PROFILE in _current_row(lines=lines)
    assert _identity_notes(lines=lines) == []


def test_an_unresolvable_identifier_is_reported_and_the_pass_continues(*, tmp_path: Path) -> None:
    """LEG 3 -- the control, and the reported-condition clause. Neither source
    carries an identifier for the profile the account manager names. The pass
    REPORTS the condition, finishes its observation and reporting work, and does not
    exit non-zero on account of it."""
    code, lines = _run(home=_home(tmp_path=tmp_path, live_uuid=None, snapshot_uuid=None))

    assert code == 0
    notes = _identity_notes(lines=lines)
    assert len(notes) == 1, f"expected exactly one unresolved-identity note, got {notes}"
    assert NAMED_PROFILE in notes[0]
    # It continued: the account table still names the determined account, and the
    # decision still ran to a hold.
    assert NAMED_PROFILE in _current_row(lines=lines)
    assert any(line.startswith("hold: ") for line in lines)
    assert not any(line.startswith("FAIL") for line in lines)
