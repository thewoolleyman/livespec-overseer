"""Integration-tier coverage for the v049 published selection record.

Tier: `tests.integration` is one of the documented governed scenario tiers.

Scenarios (SPECIFICATION/scenarios.md):
  - "A pass that switches publishes the newly selected account's identity"
  - "A pass that holds after a hand-run activation publishes the account it found active"
  - "Republishing an unchanged identity is not reported as a change"
  - "An unreadable usage response does not suppress publication"

Only process boundaries are seamed -- the account manager subprocess, the usage
endpoint, and the state file -- and `home=` is injected, so no leg touches real
host state. The record is read back from DISK as bytes rather than through any
product helper, deliberately: `spec.md` forbids the operation from reading the
record back as evidence, so the module ships no read path for a test to lean on.
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

ACTIVE = "active"
OTHER = "other"
RECORD_REL = Path(".local/state/caam-usage-rotate/selected-account.json")


class _FakeCaam:
    """The account manager subprocess; `stdout` is rebound per leg."""

    returncode = 0
    stdout = ""
    stderr = ""


def _caam_naming(profile: str) -> type[_FakeCaam]:
    body = json.dumps({"tools": [{"tool": "claude", "active_profile": profile}]})
    return type("_Caam", (_FakeCaam,), {"stdout": body})


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


def _home(*, tmp_path: Path, live_uuid: str | None) -> Path:
    """A host with two vault profiles, each snapshot carrying its own identifier."""
    vault = tmp_path / ".local/share/caam/vault/claude"
    for name in (ACTIVE, OTHER):
        (vault / name).mkdir(parents=True, exist_ok=True)
        _write_account_file(path=vault / name / ".claude.json", uuid=f"uuid-{name}")
    _write_account_file(path=tmp_path / ".claude.json", uuid=live_uuid)
    return tmp_path


def _run(*, home: Path, naming: str, usage: UsageRecord | None = None) -> tuple[int, list[str]]:
    lines: list[str] = []
    record = usage if usage is not None else _usage()
    code = run_pass(
        flags=_flags(),
        home=home,
        now=1789000000.0,
        stdout=lines.append,
        caam_runner=lambda *, args: _caam_naming(naming)(),
        fetcher=lambda *, creds_path, now=None: (record, None),
        save_state=lambda *, state, state_path: None,
    )
    return code, lines


def _record(*, home: Path) -> dict[str, object] | None:
    """The published record as bytes on disk, or None when nothing was published."""
    path = home / RECORD_REL
    if not path.is_file():
        return None
    parsed: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def test_a_pass_that_holds_publishes_the_account_it_found_active(*, tmp_path: Path) -> None:
    """The record names the account active at the end of the pass, by BOTH fields.

    A hold publishes exactly as a switch does: the clause is keyed on the pass
    having FULLY determined an account, not on it having moved one.
    """
    home = _home(tmp_path=tmp_path, live_uuid=f"uuid-{ACTIVE}")

    code, _lines = _run(home=home, naming=ACTIVE)

    record = _record(home=home)
    assert record is not None, "a pass that fully determined an account must publish"
    assert record["profile"] == ACTIVE
    assert record["account_uuid"] == f"uuid-{ACTIVE}"
    assert record["written_at"], "the record must carry the time at which it was written"
    assert code == 0


def test_the_published_record_carries_no_credential_material(*, tmp_path: Path) -> None:
    """Identity only. The record's whole key set is asserted, so a later field
    carrying a token cannot be added without this failing."""
    home = _home(tmp_path=tmp_path, live_uuid=f"uuid-{ACTIVE}")

    _code, _lines = _run(home=home, naming=ACTIVE)

    raw = (home / RECORD_REL).read_text(encoding="utf-8")
    assert set(json.loads(raw)) == {"account_uuid", "profile", "written_at"}
    for forbidden in ("token", "credential", "secret", "sk-ant"):
        assert forbidden not in raw.lower(), f"record carries {forbidden!r}: {raw}"


def test_a_hand_run_activation_converges_within_one_pass(*, tmp_path: Path) -> None:
    """An operator activated another account outside the operation.

    A hand-run activation takes no lock, so a record written only when this
    operation itself switches would be permanently wrong afterwards. The next
    pass must follow the account it FINDS active.
    """
    home = _home(tmp_path=tmp_path, live_uuid=f"uuid-{ACTIVE}")
    _code, _lines = _run(home=home, naming=ACTIVE)
    assert (_record(home=home) or {})["profile"] == ACTIVE

    # The operator activates the other account by hand: the live account file and
    # the account manager's report both now name it.
    _write_account_file(path=home / ".claude.json", uuid=f"uuid-{OTHER}")
    _code, _lines = _run(home=home, naming=OTHER)

    record = _record(home=home)
    assert record is not None
    assert record["profile"] == OTHER, "the record must follow an activation it did not perform"
    assert record["account_uuid"] == f"uuid-{OTHER}"


def test_republishing_an_unchanged_identity_is_not_reported_as_a_change(*, tmp_path: Path) -> None:
    """Two identical passes: the record is rewritten, and neither pass calls it a rotation."""
    home = _home(tmp_path=tmp_path, live_uuid=f"uuid-{ACTIVE}")

    _code, first = _run(home=home, naming=ACTIVE)
    before = _record(home=home)
    _code, second = _run(home=home, naming=ACTIVE)
    after = _record(home=home)

    assert before is not None and after is not None
    assert before["profile"] == after["profile"] == ACTIVE
    assert before["account_uuid"] == after["account_uuid"]
    for lines in (first, second):
        assert not any(line.startswith("switch: ") for line in lines)
        assert any(line.startswith("hold: ") for line in lines)


def test_a_pass_that_switches_publishes_the_newly_selected_account(*, tmp_path: Path) -> None:
    """The record ends the pass naming the account now in use, not the one it started on.

    The active account is nearly drained and the candidate is not, so the decision
    reaches a switch. The switch itself is seamed at its own process boundary -- it
    reports having MOVED the credential -- and the assertion is that the record
    follows the move rather than the account the pass opened with.
    """
    home = _home(tmp_path=tmp_path, live_uuid=f"uuid-{ACTIVE}")

    def _fetch(
        *, creds_path: Path, now: float | None = None
    ) -> tuple[UsageRecord | None, str | None]:
        _ = now
        drained = OTHER not in str(creds_path)
        return (_usage(five_hour_remaining=2.0 if drained else 95.0), None)

    switched: list[str] = []

    def _switch(*, request: object) -> object:
        from caam_switch import SwitchResult

        target = getattr(request, "target", None)
        name = getattr(target, "name", OTHER) if target is not None else OTHER
        switched.append(name)
        after = getattr(request, "after_switch", None)
        if callable(after):
            after(active_name=name)
        return SwitchResult(
            exit_code=0, lines=(f"switch: -> {name}",), reason="switched", switched=True
        )

    lines: list[str] = []
    code = run_pass(
        flags=_flags(),
        home=home,
        now=1789000000.0,
        stdout=lines.append,
        caam_runner=lambda *, args: _caam_naming(ACTIVE)(),
        fetcher=_fetch,
        save_state=lambda *, state, state_path: None,
        switch_account=_switch,
    )

    assert switched == [OTHER], f"expected a switch onto {OTHER}, got {switched}"
    record = _record(home=home)
    assert record is not None
    assert record["profile"] == OTHER, "the record must name the account the switch moved to"
    assert record["account_uuid"] == f"uuid-{OTHER}"
    assert code == 0


def test_an_unreadable_usage_response_does_not_suppress_publication(*, tmp_path: Path) -> None:
    """The identity is known; the missing figures bear only on the report.

    The pass exits non-zero because it cannot render the table, and publishes
    anyway -- suppressing here would strand a consumer on a stale account for a
    reason that has nothing to do with which account was selected.
    """
    home = _home(tmp_path=tmp_path, live_uuid=f"uuid-{ACTIVE}")

    lines: list[str] = []
    code = run_pass(
        flags=_flags(),
        home=home,
        now=1789000000.0,
        stdout=lines.append,
        caam_runner=lambda *, args: _caam_naming(ACTIVE)(),
        fetcher=lambda *, creds_path, now=None: (None, "usage endpoint unreachable"),
        save_state=lambda *, state, state_path: None,
    )

    record = _record(home=home)
    assert record is not None, "a fully determined identity publishes even with no usage"
    assert record["profile"] == ACTIVE
    assert record["account_uuid"] == f"uuid-{ACTIVE}"
    assert any("cannot read usage" in line for line in lines)
    assert code != 0
