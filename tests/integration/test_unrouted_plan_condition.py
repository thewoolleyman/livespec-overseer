"""Integration coverage for the UNROUTED-PLAN condition and its enumerated remedy.

Pins the ratified scenario in `SPECIFICATION/scenarios.md` that an unrouted plan
yields the enumerated remedy as the foreman's own action, and completes the
attention-view leg of the missing-required-input scenario that
`test_unrouted_plan_bound` deliberately left to this slice.

The scenario test drives the shipped roster CLI over FOUR plans in one tick,
one per session state, because the property under test is that the remedy is
read from a mapping that is TOTAL over the states in which the condition can
hold. A single plan cannot show that: it passes just as well against an
implementation that identifies one remedy and escalates for every other state,
which is exactly the substitution the ratified clause forbids.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import foreman_act_types
import foreman_plan_roster
import pytest

__all__: list[str] = []

OVERSEER_DIR = Path(__file__).resolve().parents[2] / "overseer"
MODULE_PATH = OVERSEER_DIR / "foreman_unrouted_plan_condition.py"
CONFIG_KEY = "unrouted_plan_bound"
# Plan, its daemon status (None means the snapshot carries no row for it), and
# the session-lifecycle act the DELEGATION FLOOR enumerates for that state.
PLAN_CASES = (
    ("alpha", None, "plan_start"),
    ("beta", "idle", "qualifying_session_resume"),
    ("gamma", "blocked:human", "blocked_session_answer"),
)
WORKED_PLAN = "delta"


def condition_module() -> ModuleType:
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_unrouted_plan_condition")


def write_repo(*, repo: Path, plans: list[str], bound: object = 1) -> None:
    for plan in plans:
        (repo / "plan" / plan).mkdir(parents=True)
    (repo / ".livespec.jsonc").write_text(
        json.dumps({"livespec-overseer": {CONFIG_KEY: bound}}), encoding="utf-8"
    )


def write_attention(*, repo: Path, items: list[dict[str, object]]) -> None:
    (repo / "attention.json").write_text(
        json.dumps({"schema_version": 1, "items": items}), encoding="utf-8"
    )


def write_snapshot(*, repo: Path, statuses: dict[str, str]) -> Path:
    path = repo / "snapshot.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "daemon_instance_id": "daemon-1",
                "tick_generation": 1,
                "written_at": "2026-08-26T00:00:00Z",
                "rows": [
                    {
                        "repo": str(repo),
                        "topic": plan,
                        "tmux": plan,
                        "runtime": "codex",
                        "status": status,
                    }
                    for plan, status in sorted(statuses.items())
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def tick(
    *,
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    tick_identity: str,
    snapshot_path: Path | None = None,
    tmux_sessions: list[str] | None = None,
) -> dict[str, object]:
    argv = [
        "--repo",
        str(repo),
        "--snapshot-path",
        str(snapshot_path if snapshot_path is not None else repo / "absent-snapshot.json"),
        "--tick-identity",
        tick_identity,
    ]
    for session in tmux_sessions if tmux_sessions is not None else []:
        argv += ["--tmux-session", session]
    if tmux_sessions is None:
        argv += ["--tmux-session", ""]
    assert foreman_plan_roster.main(argv=argv) == 0
    emitted = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    parsed = json.loads(emitted[-1])
    assert isinstance(parsed, dict)
    return parsed


def row_for(*, roster: dict[str, object], plan: str) -> dict[str, object]:
    rows = roster["rows"]
    assert isinstance(rows, list)
    matches = [row for row in rows if isinstance(row, dict) and row.get("plan") == plan]
    assert len(matches) == 1
    return matches[0]


def test_an_unrouted_plan_yields_the_enumerated_remedy_as_the_foremans_own_action(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert MODULE_PATH.is_file()
    condition = condition_module()
    repo = tmp_path / "repo"
    plans = [plan for plan, _status, _remedy in PLAN_CASES] + [WORKED_PLAN]
    write_repo(repo=repo, plans=plans)
    write_attention(repo=repo, items=[{"id": f"item-{plan}", "tmux": plan} for plan in plans])
    snapshot_path = write_snapshot(
        repo=repo,
        statuses={plan: status for plan, status, _remedy in PLAN_CASES if status is not None}
        | {WORKED_PLAN: "working"},
    )

    roster = tick(
        repo=repo,
        capsys=capsys,
        tick_identity="daemon-1:1",
        snapshot_path=snapshot_path,
        tmux_sessions=plans,
    )
    assert roster["attention_view"] == {
        "available": True,
        "item_count": len(plans),
        "undetermined_reason": None,
    }

    for plan, _status, expected_remedy in PLAN_CASES:
        row = row_for(roster=roster, plan=plan)
        assert row["unrouted_plan_condition"] == condition.HOLDS
        # The remedy the foreman identifies IS the act it takes or proposes for
        # that plan on that tick, and it is one of the enumerated unsticking
        # acts rather than an escalation standing in for one.
        assert row["unrouted_plan_remedy"] == expected_remedy
        assert row["unrouted_plan_remedy"] in foreman_act_types.ACTION_IDS
        assert row["unrouted_plan_condition_undetermined_reasons"] == []
        # Re-checkable by a reader who did not perform the determination.
        assert row["unrouted_plan_condition_inputs"] == {
            "ready_work_aging": True,
            "session_state": row["session_state"],
            "unactioned_past_bound": True,
        }

    # A live session working the plan is the one state in which the condition
    # cannot hold, so it is also the one state carrying no remedy.
    worked = row_for(roster=roster, plan=WORKED_PLAN)
    assert worked["session_state"] == condition.SESSION_WORKING
    assert worked["unrouted_plan_condition"] == condition.ABSENT
    assert worked["unrouted_plan_remedy"] is None

    # THE DISCRIMINATING CONTROL for "no escalation is substituted for a remedy
    # already available": the mapping is TOTAL over every session state other
    # than `working`, so a plan in the condition can never lack a remedy and
    # the foreman never reaches the position of escalating for want of one.
    assert set(condition.REMEDY_BY_SESSION_STATE) | {condition.SESSION_WORKING} == set(
        foreman_plan_roster.SESSION_STATES
    )
    assert set(condition.REMEDY_BY_SESSION_STATE.values()) <= set(foreman_act_types.ACTION_IDS)


def test_a_missing_attention_view_fact_yields_undetermined_never_absent_condition(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert MODULE_PATH.is_file()
    condition = condition_module()
    repo = tmp_path / "repo"
    write_repo(repo=repo, plans=["alpha"])

    unavailable = tick(repo=repo, capsys=capsys, tick_identity="daemon-1:1")
    assert unavailable["attention_view"] == {
        "available": False,
        "item_count": None,
        "undetermined_reason": condition.ATTENTION_VIEW_UNAVAILABLE,
    }
    row = row_for(roster=unavailable, plan="alpha")
    assert row["unrouted_plan_condition"] == condition.UNDETERMINED
    assert row["unrouted_plan_condition_undetermined_reasons"] == [
        condition.ATTENTION_VIEW_UNAVAILABLE
    ]
    assert row["unrouted_plan_remedy"] is None
    # Never absent-condition: an unavailable input is not evidence that the plan
    # is being worked, so it must not read as the determined ABSENT.
    assert row["unrouted_plan_condition"] != condition.ABSENT
    assert row["unrouted_plan_condition_inputs"]["ready_work_aging"] is None

    # THE DISCRIMINATING CONTROL: with the view AVAILABLE but carrying nothing
    # for this plan, the very same tick resolves the condition ABSENT. So the
    # UNDETERMINED above is caused by the missing input and not merely by the
    # absence of aging ready work, which is the confusion the clause forbids.
    write_attention(repo=repo, items=[{"id": "item-other", "tmux": "other-plan"}])
    available = tick(repo=repo, capsys=capsys, tick_identity="daemon-1:2")
    determined = row_for(roster=available, plan="alpha")
    assert available["attention_view"]["available"] is True
    assert determined["unrouted_plan_condition"] == condition.ABSENT
    assert determined["unrouted_plan_condition_undetermined_reasons"] == []
    assert determined["unrouted_plan_condition_inputs"]["ready_work_aging"] is False


def test_every_unavailable_input_resolves_undetermined_and_names_itself() -> None:
    assert MODULE_PATH.is_file()
    condition = condition_module()
    determined = condition.PlanAttentionFacts(ready_work_aging=True, session_state="idle")

    named = condition.unrouted_plan_condition(
        facts=determined,
        unactioned_past_bound=condition.UNDETERMINED,
        unactioned_past_bound_undetermined_reason="unrouted_plan_bound_unconfigured",
    )
    assert named.condition == condition.UNDETERMINED
    assert named.undetermined_reasons == ("unrouted_plan_bound_unconfigured",)
    assert named.remedy is None

    unnamed = condition.unrouted_plan_condition(
        facts=determined, unactioned_past_bound=condition.UNDETERMINED
    )
    assert unnamed.undetermined_reasons == (condition.PAST_BOUND_UNDETERMINED,)

    for session_state in (None, "not-a-session-state"):
        facts = condition.PlanAttentionFacts(ready_work_aging=True, session_state=session_state)
        resolved = condition.unrouted_plan_condition(facts=facts, unactioned_past_bound=True)
        assert resolved.condition == condition.UNDETERMINED
        assert resolved.undetermined_reasons == (condition.SESSION_STATE_UNAVAILABLE,)

    every_leg = condition.unrouted_plan_condition(
        facts=condition.PlanAttentionFacts(ready_work_aging=None, session_state=None),
        unactioned_past_bound=condition.UNDETERMINED,
    )
    assert every_leg.undetermined_reasons == (
        condition.PAST_BOUND_UNDETERMINED,
        condition.ATTENTION_VIEW_UNAVAILABLE,
        condition.SESSION_STATE_UNAVAILABLE,
    )


def test_the_condition_is_a_total_function_of_its_three_determined_legs() -> None:
    assert MODULE_PATH.is_file()
    condition = condition_module()
    legs = (
        (True, True, "no-session", condition.HOLDS),
        (False, True, "no-session", condition.ABSENT),
        (True, False, "no-session", condition.ABSENT),
        (True, True, condition.SESSION_WORKING, condition.ABSENT),
    )
    for past_bound, aging, session_state, expected in legs:
        resolved = condition.unrouted_plan_condition(
            facts=condition.PlanAttentionFacts(ready_work_aging=aging, session_state=session_state),
            unactioned_past_bound=past_bound,
        )
        assert resolved.condition == expected
        assert resolved.undetermined_reasons == ()
        assert resolved.remedy == (
            foreman_act_types.PLAN_START if expected == condition.HOLDS else None
        )


def test_the_attention_projection_and_row_annotation_fail_closed() -> None:
    assert MODULE_PATH.is_file()
    condition = condition_module()

    view: dict[str, object] = {"items": [{"session_name": "alpha"}, "not-an-object"]}
    assert condition.plan_attention_facts(
        plan="alpha", attention=view, session_state="idle"
    ) == condition.PlanAttentionFacts(ready_work_aging=True, session_state="idle")
    assert condition.plan_attention_facts(
        plan="alpha", attention={"items": "not-a-list"}, session_state=17
    ) == condition.PlanAttentionFacts(ready_work_aging=None, session_state=None)
    assert condition.plan_attention_facts(
        plan=17, attention=view, session_state="idle"
    ) == condition.PlanAttentionFacts(ready_work_aging=None, session_state="idle")

    rows: list[dict[str, object]] = [
        {"plan": "alpha", "session_state": "idle", "unactioned_past_bound": True},
        {"plan": "beta", "session_state": "idle"},
    ]
    document = condition.annotate_unrouted_plan_condition(rows=rows, attention=view)
    assert document == {"available": True, "item_count": 1, "undetermined_reason": None}
    assert rows[0]["unrouted_plan_condition"] == condition.HOLDS
    assert rows[0]["unrouted_plan_remedy"] == foreman_act_types.QUALIFYING_SESSION_RESUME
    # A row carrying no recorded verdict is an unavailable input, never an
    # absent condition.
    assert rows[1]["unrouted_plan_condition"] == condition.UNDETERMINED
    assert rows[1]["unrouted_plan_condition_undetermined_reasons"] == [
        condition.PAST_BOUND_UNDETERMINED
    ]
    assert rows[1]["unrouted_plan_remedy"] is None
