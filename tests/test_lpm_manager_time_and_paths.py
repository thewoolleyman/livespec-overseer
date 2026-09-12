"""Manager time and the deterministic local-record namespace.

Two rules from the credential-provider contract in SPECIFICATION/contracts.md that
are only visible at their EQUALITY and COLLISION edges, which is where both are pinned.

Time: every capture reads the UTC system clock and truncates TOWARD THE EARLIER whole
second, and every "at or after" boundary — worker deadlines, `expires_at`, validation age
— counts equality as the side requiring action. Rounding half-up would move a capture
ACROSS a fence it was taken before, the one direction a fence must never move.

Paths: `<home>` comes from the operating-system account database independently of `HOME`,
and each local record sits at a digest over length-prefixed identity values. Absence of a
file is DEFINED to mean "that entity does not exist", so a wrong directory or digest
reads as normal empty state rather than as an error — which is why the table is asserted
rather than trusted.
"""

from __future__ import annotations

import datetime
import hashlib
import importlib
import os
import pathlib

__all__: list[str] = []

_UTC = datetime.timezone.utc


def _modules():
    for name in ("_lpm_time.py", "_lpm_paths.py"):
        assert (
            pathlib.Path(__file__).parents[1] / "overseer" / name
        ).is_file(), f"overseer/{name} must exist"
    return importlib.import_module("_lpm_time"), importlib.import_module("_lpm_paths")


def test_a_capture_truncates_toward_the_earlier_second_in_utc():
    lpm_time, _ = _modules()
    late = datetime.datetime(2026, 9, 12, 10, 30, 59, 999999, tzinfo=_UTC)

    assert lpm_time.capture_manager_time(now=late) == "2026-09-12T10:30:59Z"
    # An offset-aware reading is normalized to UTC rather than spelled in its own zone.
    ahead = datetime.datetime(
        2026, 9, 12, 12, 30, 59, 999999, tzinfo=datetime.timezone(datetime.timedelta(hours=2))
    )
    assert lpm_time.capture_manager_time(now=ahead) == "2026-09-12T10:30:59Z"
    # A naive reading is treated as already-UTC: the UTC system clock is the only source.
    naive = datetime.datetime(2026, 9, 12, 10, 30, 59)
    assert lpm_time.capture_manager_time(now=naive) == "2026-09-12T10:30:59Z"


def test_only_the_fixed_width_spelling_of_a_real_instant_is_canonical():
    lpm_time, _ = _modules()

    assert lpm_time.is_canonical_timestamp(text="2026-09-12T10:30:59Z")
    assert not lpm_time.is_canonical_timestamp(text="2026-09-12T10:30:59.500Z")
    assert not lpm_time.is_canonical_timestamp(text="2026-09-12T10:30:59+00:00")
    assert not lpm_time.is_canonical_timestamp(text="2026-09-12t10:30:59Z")
    # Well-formed width, impossible calendar date: the pattern accepts it, the parse must not.
    assert not lpm_time.is_canonical_timestamp(text="2026-02-31T00:00:00Z")
    assert lpm_time.parse_manager_time(text="2026-09-12T10:30:59Z") == datetime.datetime(
        2026, 9, 12, 10, 30, 59, tzinfo=_UTC
    )


def test_durations_are_added_on_the_parsed_instant_and_re_emitted_canonically():
    lpm_time, _ = _modules()

    assert lpm_time.add_seconds(timestamp="2026-09-12T23:59:59Z", seconds=2) == (
        "2026-09-13T00:00:01Z"
    )
    assert lpm_time.add_seconds(timestamp="not-a-time", seconds=2) is None


def test_at_or_after_counts_equality_and_refuses_a_non_canonical_side():
    lpm_time, _ = _modules()
    moment = "2026-09-12T10:30:59Z"

    assert lpm_time.is_at_or_after(moment=moment, limit=moment) is True
    assert lpm_time.is_at_or_after(moment=moment, limit="2026-09-12T10:31:00Z") is False
    assert lpm_time.is_at_or_after(moment="10:30", limit=moment) is None
    assert lpm_time.is_at_or_after(moment=moment, limit="10:30") is None


def test_home_comes_from_the_account_database_and_an_unknown_uid_is_an_absence(monkeypatch):
    _, paths = _modules()
    monkeypatch.setenv("HOME", "/nowhere/invented")

    home = paths.account_database_home(uid=os.getuid())

    assert home is not None
    assert home != pathlib.Path("/nowhere/invented")
    assert paths.account_database_home(uid=0x7FFFFFFF) is None


def test_configuration_and_state_paths_are_the_contract_paths():
    _, paths = _modules()
    home = pathlib.Path("/home/operator")

    assert (
        paths.config_file(home=home) == home / ".config/livespec-overseer/llm-provider-manager.json"
    )
    assert paths.manager_state_dir(home=home) == (
        home / ".local/state/livespec-overseer/llm-provider-manager"
    )


def test_every_local_record_family_hashes_its_declared_identity_form():
    _, paths = _modules()
    state = pathlib.Path("/state")

    lease = paths.local_record_path(
        state_dir=state, family="lease", identity=("anthropic", "acct-1")
    ).unwrap()
    registration = paths.local_record_path(
        state_dir=state, family="run-registration", identity=("run-7",)
    ).unwrap()

    assert lease == state / "leases" / (
        hashlib.sha256(
            b"\x00" * 7 + b"\x09" + b"anthropic" + b"\x00" * 7 + b"\x06" + b"acct-1"
        ).hexdigest()
        + ".json"
    )
    # A run registration and a worker record hash the BARE UTF-8 value, as stated: a
    # single-value identity has no concatenation boundary for a separator to forge.
    assert registration == state / "run-registrations" / (
        hashlib.sha256(b"run-7").hexdigest() + ".json"
    )


def test_the_family_table_covers_every_contract_directory_and_refuses_anything_else():
    _, paths = _modules()
    state = pathlib.Path("/state")

    assert {row.directory for row in paths.LOCAL_PATH_FAMILIES.values()} == {
        "issuances",
        "target-commits",
        "leases",
        "assignments",
        "tombstones",
        "operations",
        "pending-metadata-effects",
        "run-registrations",
        "workers",
    }
    unknown = paths.local_record_path(state_dir=state, family="receipts", identity=("x",))
    wrong_arity = paths.local_record_path(state_dir=state, family="lease", identity=("x",))

    assert unknown.failure().error_type == "internal-bug"
    assert "unregistered local-record family" in unknown.failure().message
    assert wrong_arity.failure().error_type == "internal-bug"
    assert "provider, account_id" in wrong_arity.failure().message


def test_the_three_singleton_state_files_keep_their_contract_names():
    _, paths = _modules()

    assert paths.SELECTION_STATE_NAME == "selection-state.json"
    assert paths.PROOF_RECORD_NAME == "coexistence-proof.json"
    assert paths.AUDIT_LOG_NAME == "audit.jsonl"
