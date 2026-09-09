"""Integration-tier coverage for the v049 publication refusals and failure rule.

Tier: `tests.integration` is one of the documented governed scenario tiers.

Scenarios (SPECIFICATION/scenarios.md):
  - "A pass that could not take the decision lock does not publish"
  - "An undetermined active account leaves the published record intact"
  - "An unresolvable stable identifier suppresses publication"
  - "The published record never influences a later pass's selection"
  - "A failed publication fails the pass without undoing it"

Only process boundaries are seamed -- the account manager subprocess, the usage
endpoint, and the state file -- and `home=` is injected, so no leg touches real
host state. The decision lock is deliberately NOT seamed: the contention leg
takes the real `fcntl` lock on the real path and lets the shipped switch path
discover it for itself, because a seamed lock factory would prove only that a
test can return a reason string.

The record is read back from DISK as bytes rather than through any product
helper: `spec.md` forbids the operation from reading the record back as
evidence, so the module ships no read path for a test to lean on. Each refusal
leg asserts on BYTES rather than on fields, because "leaves the record intact"
is a claim about the file not being rewritten -- a rewrite carrying identical
content would satisfy a field-by-field comparison while breaking the clause.
"""

from __future__ import annotations

import fcntl
import json
from pathlib import Path

import pytest
from caam_anthropic_loop import Flags
from caam_anthropic_pass import run_pass
from caam_decision import UsageRecord
from caam_switch import LOCK_REL, SwitchResult

__all__: list[str] = []

pytestmark = pytest.mark.integration

ACTIVE = "active"
OTHER = "other"
RECORD_REL = Path(".local/state/caam-usage-rotate/selected-account.json")

# The record a PREVIOUS pass published. Every refusal leg asserts these exact
# bytes survive, so the marker names an account no leg can otherwise produce.
PRIOR_RECORD = json.dumps(
    {
        "account_uuid": "uuid-published-earlier",
        "profile": "published-earlier",
        "written_at": "2000-01-01T00:00:00Z",
    },
    indent=1,
    sort_keys=True,
)


class _FakeCaam:
    """The account manager subprocess; `stdout` is rebound per leg."""

    returncode = 0
    stdout = ""
    stderr = ""


def _caam_naming(profile: str | None) -> type[_FakeCaam]:
    """A report naming `profile` active, or one naming nothing at all."""
    tool: dict[str, object] = {"tool": "claude"}
    if profile is not None:
        tool["active_profile"] = profile
    return type("_Caam", (_FakeCaam,), {"stdout": json.dumps({"tools": [tool]})})


def _usage(*, five_hour_remaining: float = 80.0) -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=five_hour_remaining,
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


def _write_account_file(*, path: Path, uuid: str | None) -> None:
    account: dict[str, object] = {} if uuid is None else {"accountUuid": uuid}
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps({"oauthAccount": account}), encoding="utf-8")


def _home(*, root: Path, live_uuid: str | None, snapshot_uuids: bool = True) -> Path:
    """A host with two vault profiles, optionally identified snapshots, and a live file."""
    vault = root / ".local/share/caam/vault/claude"
    for name in (ACTIVE, OTHER):
        (vault / name).mkdir(parents=True, exist_ok=True)
        _write_account_file(
            path=vault / name / ".claude.json",
            uuid=f"uuid-{name}" if snapshot_uuids else None,
        )
    _write_account_file(path=root / ".claude.json", uuid=live_uuid)
    return root


def _publish_earlier(*, home: Path) -> bytes:
    """Stand in for a record an earlier pass published; returns its exact bytes."""
    path = home / RECORD_REL
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _ = path.write_text(PRIOR_RECORD, encoding="utf-8")
    return path.read_bytes()


def _draining_fetcher(*, creds_path: Path, now: float | None = None):
    """The active account is nearly spent and the candidate is not, so a pass rotates."""
    _ = now
    return (_usage(five_hour_remaining=2.0 if OTHER not in str(creds_path) else 95.0), None)


def _holding_fetcher(*, creds_path: Path, now: float | None = None):
    """Every account comfortably above every trigger, so the pass holds."""
    _ = creds_path, now
    return (_usage(), None)


def _run(*, home: Path, naming: str | None, **overrides: object) -> tuple[int, list[str]]:
    lines: list[str] = []
    seams: dict[str, object] = {
        "caam_runner": lambda *, args: _caam_naming(naming)(),
        "fetcher": _holding_fetcher,
        "save_state": lambda *, state, state_path: None,
    }
    seams.update(overrides)
    code = run_pass(
        flags=_flags(),
        home=home,
        now=1789000000.0,
        stdout=lines.append,
        **seams,
    )
    return code, lines


def test_a_pass_that_could_not_take_the_decision_lock_does_not_publish(*, tmp_path: Path) -> None:
    """The lock-holding caller is deciding the very fact the record would state.

    The real `fcntl` lock is held on the real path, and the shipped switch path
    discovers the contention itself -- nothing about the lock is seamed. The pass
    is set up so that it WOULD otherwise publish: it fully determines the active
    account and reaches a rotation decision, so a record left unchanged here is
    evidence of the refusal rather than of a pass that never got that far.
    """
    home = _home(root=tmp_path, live_uuid=f"uuid-{ACTIVE}")
    before = _publish_earlier(home=home)

    lock_path = home / LOCK_REL
    lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as holder:
        fcntl.flock(holder.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        code, lines = _run(home=home, naming=ACTIVE, fetcher=_draining_fetcher)

    assert any("holds the switch lock" in line for line in lines), lines
    assert (home / RECORD_REL).read_bytes() == before, (
        "a pass that could not take the decision lock must leave the record "
        "for the lock-holding caller to write"
    )
    assert code == 0, "losing the lock is a hold, not a failure"


def test_an_undetermined_active_account_leaves_the_published_record_intact(
    *, tmp_path: Path
) -> None:
    """Neither path can name the active account, so nothing is published.

    The account manager reports no active profile and the live account file
    carries no identifier for the fallback to match, which is the shape a token
    refresh leaves behind when no snapshot answers either.
    """
    home = _home(root=tmp_path, live_uuid=None)
    before = _publish_earlier(home=home)

    code, lines = _run(home=home, naming=None)

    assert any(line.startswith("FAIL could not determine active") for line in lines), lines
    assert (home / RECORD_REL).read_bytes() == before
    assert code != 0


def test_an_unresolvable_stable_identifier_suppresses_publication(*, tmp_path: Path) -> None:
    """A name-only record would follow a renamed profile to the wrong account.

    The account manager names the active profile, so the pass determines it, but
    neither the live account file nor that profile's stored snapshot carries an
    identifier. A stale but COMPLETE record is the safer failure, so the earlier
    publication stands untouched and the gap is reported instead.
    """
    home = _home(root=tmp_path, live_uuid=None, snapshot_uuids=False)
    before = _publish_earlier(home=home)

    code, lines = _run(home=home, naming=ACTIVE)

    assert any("could not resolve a stable account identifier" in line for line in lines), lines
    assert (home / RECORD_REL).read_bytes() == before
    assert code == 0, "an unresolved identifier is a reported condition, not a failure path"


def test_the_published_record_never_influences_a_later_passs_selection(*, tmp_path: Path) -> None:
    """The record is an output. Two identical hosts, one carrying a stale record.

    The stale record names an account that exists in neither vault, so a pass
    that consulted it could not stay silent about it -- and both passes must
    reach the same eligibility, the same ranking and the same decision to move.
    """
    seen: dict[str, list[str]] = {}
    for leg in ("with-record", "without-record"):
        home = _home(root=tmp_path / leg, live_uuid=f"uuid-{ACTIVE}")
        if leg == "with-record":
            _ = _publish_earlier(home=home)
        switched: list[str] = []
        _code, lines = _run(
            home=home,
            naming=ACTIVE,
            fetcher=_draining_fetcher,
            switch_account=_recording_switch(switched=switched),
        )
        seen[leg] = lines
        assert switched == [OTHER], f"{leg}: expected a switch onto {OTHER}, got {switched}"
        assert not any(
            "published-earlier" in line for line in lines
        ), f"{leg}: the pass named the published record's account in its own report"

    assert (
        seen["with-record"] == seen["without-record"]
    ), "a stale published record changed what the pass reported or decided"


def test_a_failed_publication_fails_the_pass_without_undoing_it(*, tmp_path: Path) -> None:
    """The rotation and the report are complete work; only the publication failed.

    The record path is occupied by a DIRECTORY, so the shipped atomic replace
    fails for a real filesystem reason rather than a seamed one. The switch has
    already moved the credential by then, and discarding it to signal a failed
    publication would cost more than the failure it reports.
    """
    home = _home(root=tmp_path, live_uuid=f"uuid-{ACTIVE}")
    (home / RECORD_REL).mkdir(mode=0o700, parents=True)

    saved: list[str] = []
    switched: list[str] = []
    code, lines = _run(
        home=home,
        naming=ACTIVE,
        fetcher=_draining_fetcher,
        switch_account=_recording_switch(switched=switched),
        save_state=lambda *, state, state_path: saved.append(str(state_path)),
    )

    assert switched == [OTHER], "the switch must stand"
    assert saved, "a failed publication must not prevent the persistence of operation state"
    assert any(line.startswith("FAIL") and "publish" in line for line in lines), lines
    assert (
        sum(1 for line in lines if line.startswith("PROFILE")) >= 2
    ), f"the account table must still be reported, before and after the move: {lines}"
    assert code != 0


def _recording_switch(*, switched: list[str]):
    """A switch seamed at its own process boundary: it reports having MOVED."""

    def _switch(*, request: object) -> SwitchResult:
        target = getattr(request, "target", None)
        name = str(getattr(target, "name", OTHER))
        switched.append(name)
        return SwitchResult(
            exit_code=0, lines=(f"switch: -> {name}",), reason="switched", switched=True
        )

    return _switch
