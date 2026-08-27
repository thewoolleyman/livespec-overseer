"""Integration coverage for detection-staleness routing, and for what it refuses.

Pins the ratified scenario in `SPECIFICATION/scenarios.md` that a surfaced
detection-staleness item is routed to an attended surface and never run: the
item reaches an attended session for the owning plan or the grooming operation,
the foreman does not run the detection itself, and nothing other than that
routing discharges the item.

The scenario test drives the shipped roster CLI over a view carrying SIX
detection-staleness items in ONE tick — one per session state, one attributed to
a plan this roster does not carry, and one the view attributes to nothing —
because the property under test is that routing is TOTAL. A single item cannot
show that: it passes equally against an implementation that routes the one case
it was handed and silently drops every other, which is the ownership hole the
clause exists to close. A non-detection item rides in the same view as the
control that the surface routes THESE items rather than every item it sees.

The "never runs the detection" leg is pinned structurally rather than by
assertion about intent, and with a control that proves the scanner can fail: the
same scan over a shipped module that really does run commands must flag it. A
scan that flags nothing anywhere would report this surface clean whatever it
contained.
"""

from __future__ import annotations

import ast
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
MODULE_PATH = OVERSEER_DIR / "foreman_detection_staleness.py"
# The control for the execution scan below: a shipped foreman module that REALLY
# runs commands, so the scanner is proven able to fail rather than merely silent.
EXECUTING_MODULE_PATH = OVERSEER_DIR / "foreman_gather_sources.py"
# Modules and names by which any Python module could reach out and run something.
EXECUTION_MODULES = frozenset({"multiprocessing", "os", "pty", "shutil", "subprocess", "tmuxio"})
EXECUTION_NAMES = frozenset({"Popen", "execv", "execvp", "popen", "run_json_command", "system"})
# Plan, its daemon status (None means the snapshot carries no row for it), and
# the session-lifecycle act by which the item reaches that plan's attended
# session. `working` needs none: the attended session is already live.
PLAN_CASES = (
    ("alpha", "working", None),
    ("beta", "idle", "qualifying_session_resume"),
    ("gamma", "blocked:human", "blocked_session_answer"),
    ("delta", None, "plan_start"),
)
UNCARRIED_PLAN = "zeta"
STALE_KIND = "detection-staleness:spec-implementation-drift"


def routing_module() -> ModuleType:
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_detection_staleness")


def write_repo(*, repo: Path, plans: list[str]) -> None:
    for plan in plans:
        (repo / "plan" / plan).mkdir(parents=True)
    (repo / ".livespec.jsonc").write_text(
        json.dumps({"livespec-overseer": {"unrouted_plan_bound": 1}}), encoding="utf-8"
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
                "written_at": "2026-08-27T00:00:00Z",
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
    *, repo: Path, capsys: pytest.CaptureFixture[str], snapshot_path: Path
) -> dict[str, object]:
    argv = [
        "--repo",
        str(repo),
        "--snapshot-path",
        str(snapshot_path),
        "--tick-identity",
        "daemon-1:1",
    ]
    for plan, _status, _act in PLAN_CASES:
        argv += ["--tmux-session", plan]
    assert foreman_plan_roster.main(argv=argv) == 0
    emitted = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    parsed = json.loads(emitted[-1])
    assert isinstance(parsed, dict)
    return parsed


def routed_tick(*, repo: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    """One tick over every routing case the clause distinguishes."""
    plans = [plan for plan, _status, _act in PLAN_CASES]
    write_repo(repo=repo, plans=plans)
    write_attention(
        repo=repo,
        items=[
            *({"id": f"stale-{plan}", "kind": STALE_KIND, "plan": plan} for plan in plans),
            {"id": f"stale-{UNCARRIED_PLAN}", "kind": STALE_KIND, "plan": UNCARRIED_PLAN},
            {"id": "stale-unattributed", "kind": STALE_KIND, "title": "detection overdue"},
            # The control: an ordinary item in the SAME view, which this surface
            # must not route, so routing is shown to key on the declared kind.
            {"id": "ordinary", "kind": "work-item", "plan": "alpha"},
        ],
    )
    snapshot_path = write_snapshot(
        repo=repo,
        statuses={plan: status for plan, status, _act in PLAN_CASES if status is not None},
    )
    return tick(repo=repo, capsys=capsys, snapshot_path=snapshot_path)


def routings_by_id(*, roster: dict[str, object]) -> dict[str, dict[str, object]]:
    document = roster["detection_staleness"]
    assert isinstance(document, dict)
    routings = document["routings"]
    assert isinstance(routings, list)
    by_id: dict[str, dict[str, object]] = {}
    for routing in routings:
        assert isinstance(routing, dict)
        by_id[str(routing["item_id"])] = routing
    return by_id


def imported_and_called(*, path: Path) -> tuple[frozenset[str], frozenset[str]]:
    """Every module root this file imports, and every bare name it calls."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module.split(".")[0])
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return frozenset(modules), frozenset(names)


def reaches_execution(*, path: Path) -> bool:
    modules, names = imported_and_called(path=path)
    return bool(modules & EXECUTION_MODULES) or bool(names & EXECUTION_NAMES)


def test_a_surfaced_detection_staleness_item_is_routed_to_an_attended_surface(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert MODULE_PATH.is_file()
    module = routing_module()
    repo = tmp_path / "repo"

    roster = routed_tick(repo=repo, capsys=capsys)

    document = roster["detection_staleness"]
    assert isinstance(document, dict)
    # SIX detection-staleness items surfaced and SIX were routed: routing is
    # total, and the ordinary item riding beside them was not routed at all.
    assert document["available"] is True
    assert document["item_count"] == len(PLAN_CASES) + 2
    routings = routings_by_id(roster=roster)
    assert set(routings) == {
        *(f"stale-{plan}" for plan, _status, _act in PLAN_CASES),
        f"stale-{UNCARRIED_PLAN}",
        "stale-unattributed",
    }

    for plan, _status, act in PLAN_CASES:
        routing = routings[f"stale-{plan}"]
        # Routed to the attended session for the OWNING plan, naming the
        # enumerated act by which that session is started or resumed — or none,
        # where the plan's session is already attended and working.
        assert routing["target"] == module.ATTENDED_PLAN_SESSION
        assert routing["plan"] == plan
        assert routing["topic"] == plan
        assert routing["lifecycle_act"] == act
        assert plan in str(routing["reason"])

    # Neither remaining item names a plan this roster carries, so each routes to
    # the OTHER enumerated surface rather than being dropped for want of one.
    grooming = repo.name + "-grooming"
    for item_id in (f"stale-{UNCARRIED_PLAN}", "stale-unattributed"):
        routing = routings[item_id]
        assert routing["target"] == module.GROOMING_OPERATION
        assert routing["topic"] == grooming
        assert routing["lifecycle_act"] is None

    # Every routing names one of exactly two enumerated targets, and every act
    # it names is one the foreman's own closed act enumeration already carries.
    assert {str(routing["target"]) for routing in routings.values()} <= set(module.ROUTING_TARGETS)
    for routing in routings.values():
        act = routing["lifecycle_act"]
        assert act is None or act in foreman_act_types.ACTION_IDS


def test_the_item_is_not_treated_as_satisfied_by_any_act_other_than_that_routing(
    *, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert MODULE_PATH.is_file()
    module = routing_module()
    repo = tmp_path / "repo"
    roster = routed_tick(repo=repo, capsys=capsys)
    item_id = f"stale-{PLAN_CASES[1][0]}"
    routing = module.DetectionStalenessRouting(
        item_id=item_id,
        lifecycle_act=None,
        plan=None,
        reason="reconstructed from the tick's own routing",
        target=module.GROOMING_OPERATION,
        topic="ignored",
    )
    assert item_id in routings_by_id(roster=roster)

    # Every act that is NOT the routing — including the one act the clause
    # forbids outright, a claim that the detection was run — leaves the item
    # OUTSTANDING. An implementation that discharged the item on any of these
    # would satisfy it by something other than routing.
    unsatisfying: tuple[dict[str, object], ...] = (
        {"kind": "detection-run", "item_id": item_id, "outcome": "clean"},
        {"kind": "work_item_comment", "item_id": item_id},
        {"kind": "work_item_update", "item_id": item_id, "status": "closed"},
        {
            "kind": module.ROUTING_ACT_KIND,
            "item_id": "some-other-item",
            "target": "grooming-operation",
        },
        {"kind": module.ROUTING_ACT_KIND, "item_id": item_id, "target": "ran-it-myself"},
        {"kind": module.ROUTING_ACT_KIND, "item_id": item_id},
        {"item_id": item_id, "target": module.GROOMING_OPERATION},
    )
    for act in unsatisfying:
        assert module.satisfaction(routing=routing, acts=[act]) == module.OUTSTANDING
    assert module.satisfaction(routing=routing, acts=list(unsatisfying)) == module.OUTSTANDING

    # THE DISCRIMINATING CONTROL: the routing act itself, and only it, does
    # discharge the item — so each OUTSTANDING above is caused by the act not
    # being that routing, not by a predicate that can never return satisfied.
    for target in module.ROUTING_TARGETS:
        act = {"kind": module.ROUTING_ACT_KIND, "item_id": item_id, "target": target}
        assert module.satisfaction(routing=routing, acts=[*unsatisfying, act]) == module.ROUTED


def test_the_routing_surface_has_no_path_by_which_it_runs_a_detection() -> None:
    assert MODULE_PATH.is_file()
    module = routing_module()

    # The surface imports no execution primitive and calls no spawn name, so
    # there is no path from a surfaced item to running anything.
    assert reaches_execution(path=MODULE_PATH) is False
    # THE CONTROL: the same scan over a shipped module that really does run
    # commands flags it, so the clean reading above is a measurement.
    assert reaches_execution(path=EXECUTING_MODULE_PATH) is True

    # And the foreman's act vocabulary is CLOSED and carries no detection act at
    # all, so there is no enumerated act by which it could invoke one.
    assert [act for act in foreman_act_types.ACTION_IDS if "detect" in act] == []
    assert module.ROUTING_ACT_KIND not in foreman_act_types.ACTION_IDS


def test_routing_is_total_and_fails_toward_the_grooming_operation(*, tmp_path: Path) -> None:
    assert MODULE_PATH.is_file()
    module = routing_module()
    repo_slug = "livespec-overseer"
    grooming = f"{repo_slug}-grooming"
    states = module.session_states_by_plan(
        rows=[
            {"plan": "alpha", "session_state": "idle"},
            {"plan": "unreadable", "session_state": "no-such-state"},
            {"plan": "typeless", "session_state": 7},
            {"session_state": "idle"},
        ]
    )
    assert states == {"alpha": "idle", "unreadable": "no-such-state"}

    # A plan whose session state this roster cannot read is not evidence that
    # anyone is attending it, so the item routes to the grooming operation
    # rather than resolving to no target at all.
    for plan in ("unreadable", "typeless", "absent"):
        item = module.DetectionStalenessItem(
            item_id="stale-1", kind=STALE_KIND, plan=plan, title=""
        )
        routing = module.route_item(item=item, session_states=states, repo_slug=repo_slug)
        assert routing.target == module.GROOMING_OPERATION
        assert routing.topic == grooming
        assert routing.plan == plan
    # The control: a plan whose state IS readable routes to its attended session.
    attended = module.route_item(
        item=module.DetectionStalenessItem(
            item_id="stale-1", kind=STALE_KIND, plan="alpha", title="drift"
        ),
        session_states=states,
        repo_slug=repo_slug,
    )
    assert attended.target == module.ATTENDED_PLAN_SESSION
    assert attended.document()["lifecycle_act"] == "qualifying_session_resume"


def test_the_declared_kind_decides_what_is_routed_and_an_unreadable_view_is_named() -> None:
    assert MODULE_PATH.is_file()
    module = routing_module()

    # Recognition reads the item's OWN declared kind, normalized, so a producer
    # spelling it with underscores, in capitals, or scoped to one detection is
    # recognized while a title that merely mentions staleness is not.
    for kind in (STALE_KIND, "detection_staleness", "DETECTION-STALENESS", "detection-staleness"):
        assert module.is_detection_staleness(item={"kind": kind}) is True
        assert module.detection_kind(item={"kind": kind}) is not None
    for item in (
        {"kind": "work-item", "title": "detection-staleness is overdue"},
        {"kind": "detection-stalenessish"},
        {"kind": 7},
        {},
    ):
        assert module.is_detection_staleness(item=item) is False

    # An unreadable attention view is reported as unavailable and named, never
    # rendered as a view that carried no detection-staleness item.
    for attention in (None, {}, {"items": "not-a-list"}):
        document = module.detection_staleness_document(rows=[], attention=attention, repo=Path())
        assert document["available"] is False
        assert document["item_count"] is None
        assert document["routings"] == []
        assert document["undetermined_reason"] == module.ATTENTION_VIEW_UNAVAILABLE
    # The control: an available view that simply carries nothing reads EMPTY.
    empty = module.detection_staleness_document(
        rows=[], attention={"items": ["not-an-object", {"kind": "work-item"}]}, repo=Path()
    )
    assert empty["available"] is True
    assert empty["item_count"] == 0
    assert empty["undetermined_reason"] is None

    # An item carrying no id is still routed, under a stable placeholder, and
    # attribution falls through to whichever key the producer used.
    items = module.detection_staleness_items(
        attention={"items": [{"kind": STALE_KIND, "session_name": "beta"}]}
    )
    assert items is not None
    assert items[0].item_id == module.UNIDENTIFIED_ITEM_ID
    assert items[0].plan == "beta"
    assert items[0].title == ""
