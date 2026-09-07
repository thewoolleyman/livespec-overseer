"""A non-active account's reading must not be rendered as SOURCE=live (child
overseer-54k2za.54).

The active account is polled with the LIVE credential; every other account is
polled through its STORED SNAPSHOT credential (the Observation clause). Both
succeed and are recorded ``source="live"`` for the DECISION path's
live-verification -- but that means "credential exercised this pass", NOT "the
figure is a current live reading of the active login". The account table
conflated the two, so a deselected account's snapshot figure printed as an
authoritative ``SOURCE=live`` current value (observed live: anthropic-2 showed
13% for ~3.5h while actually 0%). The table must label a non-active account's
reading by its true provenance instead.
"""

from __future__ import annotations

from pathlib import Path

from caam_anthropic_loop import Flags
from caam_anthropic_pass import run_pass
from caam_decision import UsageRecord

__all__: list[str] = []


class _FakeProcess:
    returncode = 0
    stdout = '{"tools": [{"tool": "claude", "active_profile": "active"}]}'
    stderr = ""


def _usage(*, five_hour: float) -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=five_hour,
        seven_day_remaining=50.0,
        five_hour_resets_at="2026-08-22T12:00:00Z",
        seven_day_resets_at="2026-08-24T00:00:00Z",
        fable_remaining=90.0,
        fable_resets_at="2026-08-24T00:00:00Z",
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


def _run(*, home: Path, lines: list[str], fetcher) -> int:
    return run_pass(
        flags=_flags(),
        home=home,
        now=1787395200.0,
        stdout=lines.append,
        caam_runner=lambda *, args: _FakeProcess(),
        fetcher=fetcher,
        save_state=lambda *, state, state_path: None,
    )


def _row(*, lines: list[str], name: str) -> str:
    return next(line for line in lines if line.startswith(f"{name} "))


def test_nonactive_snapshot_reading_is_not_rendered_as_source_live(*, tmp_path: Path) -> None:
    for name in ("active", "other"):
        (tmp_path / ".local/share/caam/vault/claude" / name).mkdir(parents=True)

    def fetcher(*, creds_path: Path, now: float | None = None):
        del now
        # The active account is polled with the live credential (no "vault" in
        # its path); "other" is polled through its stored snapshot credential.
        from_snapshot = "vault" in str(creds_path)
        return _usage(five_hour=13.0 if from_snapshot else 20.0), None

    lines: list[str] = []
    _ = _run(home=tmp_path, lines=lines, fetcher=fetcher)

    active_row = _row(lines=lines, name="active")
    other_row = _row(lines=lines, name="other")

    # The active account's live-credential poll is genuinely live.
    assert active_row.split()[-1] == "live", active_row
    # The non-active account's figure came from its stored snapshot credential;
    # it must NOT be asserted as an authoritative live reading.
    assert other_row.split()[-1] != "live", other_row
    assert other_row.split()[-1] == "snapshot", other_row
