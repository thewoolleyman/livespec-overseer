"""Integration coverage for the maintainer-owned UNROUTED-PLAN BOUND.

Pins two ratified scenarios in `SPECIFICATION/scenarios.md`: that a tick which
actions a plan resets that plan's consecutive-unactioned count, and that a
required input the repository does not supply resolves UNDETERMINED rather than
reading as an absent condition.

The reset scenario is driven through the shipped roster CLI across four
successive ticks because the discriminating assertion is about a LATER tick: an
implementation that accumulates rather than counting consecutively passes every
single-tick check and then reports actively-worked plans as past their bound.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import foreman_plan_roster
import pytest

__all__: list[str] = []

OVERSEER_DIR = Path(__file__).resolve().parents[2] / "overseer"
MODULE_PATH = OVERSEER_DIR / "foreman_unrouted_plan_bound.py"
CONFIG_KEY = "unrouted_plan_bound"


def bound_module() -> ModuleType:
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_unrouted_plan_bound")


def write_repo(*, repo: Path, bound: object, configure: bool = True) -> None:
    (repo / "plan" / "alpha").mkdir(parents=True)
    section: dict[str, object] = {}
    if configure:
        section[CONFIG_KEY] = bound
    (repo / ".livespec.jsonc").write_text(
        json.dumps({"livespec-overseer": section}), encoding="utf-8"
    )


def tick(
    *,
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    tick_identity: str,
    actioned_plan: str | None = None,
) -> dict[str, object]:
    argv = [
        "--repo",
        str(repo),
        "--snapshot-path",
        str(repo / "absent-snapshot.json"),
        "--tmux-session",
        "alpha",
        "--tick-identity",
        tick_identity,
    ]
    if actioned_plan is not None:
        argv += ["--actioned-plan", actioned_plan]
    assert foreman_plan_roster.main(argv=argv) == 0
    emitted = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    parsed = json.loads(emitted[-1])
    assert isinstance(parsed, dict)
    return parsed


def alpha_row(*, roster: dict[str, object]) -> dict[str, object]:
    rows = roster["rows"]
    assert isinstance(rows, list)
    matches = [row for row in rows if isinstance(row, dict) and row.get("plan") == "alpha"]
    assert len(matches) == 1
    return matches[0]


def test_an_actioning_tick_resets_the_count_and_a_later_tick_is_not_past_bound(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert MODULE_PATH.is_file()
    bounds = bound_module()
    assert bounds.CONFIG_KEY == CONFIG_KEY
    repo = tmp_path / "repo"
    write_repo(repo=repo, bound=2)

    below = alpha_row(roster=tick(repo=repo, capsys=capsys, tick_identity="daemon-1:1"))
    assert below["consecutive_unactioned_ticks"] == 1
    assert below["unactioned_past_bound"] is False

    reached = tick(repo=repo, capsys=capsys, tick_identity="daemon-1:2")
    assert reached["unrouted_plan_bound"]["bound"] == 2
    assert reached["unrouted_plan_bound"]["resolution"] == "configured"
    at_bound = alpha_row(roster=reached)
    assert at_bound["consecutive_unactioned_ticks"] == 2
    assert at_bound["unactioned_past_bound"] is True

    actioned = alpha_row(
        roster=tick(repo=repo, capsys=capsys, tick_identity="daemon-1:3", actioned_plan="alpha")
    )
    assert actioned["consecutive_unactioned_ticks"] == 0
    assert actioned["unactioned_past_bound"] is False

    # THE DISCRIMINATING CONTROL: the count the plan carried before the action
    # must not carry through it. A cumulative implementation reads 4 here and
    # reports a plan it has just worked as past its bound.
    later = alpha_row(roster=tick(repo=repo, capsys=capsys, tick_identity="daemon-1:4"))
    assert later["consecutive_unactioned_ticks"] == 1
    assert later["unactioned_past_bound"] is False


def test_an_unconfigured_bound_resolves_undetermined_never_absent_condition(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert MODULE_PATH.is_file()
    bounds = bound_module()
    repo = tmp_path / "repo"
    write_repo(repo=repo, bound=None, configure=False)

    resolved = bounds.resolve_unrouted_plan_bound(repo=repo)
    assert resolved.bound is None
    assert resolved.undetermined_reason == bounds.BOUND_UNCONFIGURED

    roster = tick(repo=repo, capsys=capsys, tick_identity="daemon-1:1")
    assert roster["unrouted_plan_bound"] == {
        "bound": None,
        "configured": None,
        "resolution": bounds.UNDETERMINED,
        "undetermined_reason": bounds.BOUND_UNCONFIGURED,
        "source": "unconfigured",
    }
    row = alpha_row(roster=roster)
    assert row["consecutive_unactioned_ticks"] == 1
    assert row["unactioned_past_bound"] == bounds.UNDETERMINED
    # Never absent-condition: an unavailable input must not render as the
    # boolean `False` a determined, not-past-bound plan carries.
    assert not isinstance(row["unactioned_past_bound"], bool)
    assert row["unactioned_past_bound_undetermined_reason"] == bounds.BOUND_UNCONFIGURED

    no_config = tmp_path / "no-config"
    (no_config / "plan" / "alpha").mkdir(parents=True)
    assert (
        bounds.resolve_unrouted_plan_bound(repo=no_config).undetermined_reason
        == bounds.BOUND_UNCONFIGURED
    )

    no_section = tmp_path / "no-section"
    (no_section / "plan" / "alpha").mkdir(parents=True)
    (no_section / ".livespec.jsonc").write_text(
        json.dumps({"spec_root": "SPECIFICATION"}), encoding="utf-8"
    )
    assert (
        bounds.resolve_unrouted_plan_bound(repo=no_section).undetermined_reason
        == bounds.BOUND_UNCONFIGURED
    )


def test_an_unavailable_count_and_an_unusable_bound_both_resolve_undetermined(
    *, tmp_path: Path
) -> None:
    assert MODULE_PATH.is_file()
    bounds = bound_module()
    configured = tmp_path / "configured"
    write_repo(repo=configured, bound=2)

    # No tick identity means no count was recorded this pass, which is the other
    # unavailable input the condition can meet.
    roster = foreman_plan_roster.compose_roster(
        repo=configured,
        snapshot_path=configured / "absent-snapshot.json",
        tmux_sessions=["alpha"],
    )
    row = alpha_row(roster=roster)
    assert "consecutive_unactioned_ticks" not in row
    assert row["unactioned_past_bound"] == bounds.UNDETERMINED
    assert row["unactioned_past_bound_undetermined_reason"] == bounds.COUNT_UNAVAILABLE

    for index, value in enumerate([True, "2", 0, ["2"]]):
        repo = tmp_path / f"unusable-{index}"
        write_repo(repo=repo, bound=value)
        unusable = bounds.resolve_unrouted_plan_bound(repo=repo)
        assert unusable.bound is None
        assert unusable.undetermined_reason == bounds.BOUND_NOT_A_TICK_COUNT
        assert unusable.source == str(repo / ".livespec.jsonc")
        assert unusable.document()["configured"] == (value if index != 3 else None)

    usable = bounds.resolve_unrouted_plan_bound(repo=configured)
    assert bounds.unactioned_past_bound(count=1, bound=usable).verdict is False
    assert bounds.unactioned_past_bound(count=2, bound=usable).verdict is True
    unavailable = bounds.unactioned_past_bound(count=None, bound=usable)
    assert unavailable.verdict == bounds.UNDETERMINED
    assert unavailable.undetermined_reason == bounds.COUNT_UNAVAILABLE
