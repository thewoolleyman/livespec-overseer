"""Integration coverage for publishing the foreman's OWN wait states to the plan ledger epic.

Pins the ratified scenario in `SPECIFICATION/scenarios.md` that a foreman wait is
readable without opening its pane. The scenario test drives all THREE shipped
raise sites in one repository — the blocking-prompt escalation, the convene
escalation, and the panel convening — because the clause names three wait kinds
and a test that drives one passes equally against an implementation that
publishes that one and leaves the other two where they were, in a private
scratch area and a pane.

Only `bd` itself is faked. The argv handed to the fake is the one the shipped
ledger mutation surface builds, and the reader then recovers the waits from the
comment bodies that argv carried — so what is asserted is that a reader
consulting the governed plan's ledger epic, and nothing else, can tell what the
loop is waiting on.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import foreman_convene_obligations
import foreman_panel
import foreman_runtime_escalation
import foreman_runtime_identity
import pytest
from foreman_act_dispatch_result import CommandResult

__all__: list[str] = []

OVERSEER_DIR = Path(__file__).resolve().parents[2] / "overseer"
MODULE_PATH = OVERSEER_DIR / "foreman_wait_publication.py"
PLAN = "alpha"
SECOND_PLAN = "beta"
PLAN_EPIC = "overseer-7ranbh"
SECOND_PLAN_EPIC = "overseer-7ranbh.9"
FOREIGN_EPIC = "not-this-tenant-1"
FINGERPRINT = "a" * 64
PANEL_QUESTION = "Should the bounded formatter step proceed?"
ESCALATION_REASON = "cross_vendor_reviewers_unavailable"

Recorder = tuple[list[list[str]], Callable[..., CommandResult]]


def publication_module() -> ModuleType:
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_wait_publication")


def ledger_recorder(*, returncode: int = 0) -> Recorder:
    """Stand in for the `bd` binary alone, capturing the real argv it is handed."""
    commands: list[list[str]] = []

    def run(*, argv: list[str]) -> CommandResult:
        commands.append(argv)
        return CommandResult(returncode=returncode, stderr="ledger unreachable")

    return commands, run


def epic_records(*, plan_slugs: dict[str, str]) -> list[dict[str, object]]:
    return [
        {
            "id": epic_id,
            "issue_type": "epic",
            "status": "open",
            "metadata": {"plan_slug": plan_slug},
        }
        for epic_id, plan_slug in sorted(plan_slugs.items())
    ]


def publisher_for(
    *,
    publication: ModuleType,
    recorder: Recorder,
    records: list[dict[str, object]],
) -> Callable[..., object]:
    _commands, run = recorder

    def publish(*, repo: Path, wait: object) -> object:
        return publication.publish_wait_state(repo=repo, wait=wait, epic_records=records, run=run)

    return publish


def epic_comments(*, commands: list[list[str]], epic_id: str) -> list[dict[str, object]]:
    """What `bd comments <epic> --json` would return for the epic, and nothing else."""
    return [
        {"text": argv[-1]}
        for argv in commands
        if argv[:2] == ["bd", "comment"] and argv[2] == epic_id
    ]


def plan_tree_files(*, repo: Path) -> set[str]:
    return {str(path.relative_to(repo)) for path in sorted((repo / "plan").rglob("*"))}


RAISE_SITE_MODULES = (
    foreman_runtime_escalation,
    foreman_convene_obligations,
    foreman_panel,
)


def arm_publisher(*, monkeypatch: pytest.MonkeyPatch, publish: Callable[..., object]) -> None:
    """Redirect the declared seam on every module that READS it.

    Each raise site holds its own binding, so redirecting one would leave the
    other two publishing through the real ledger — the resolution subtlety this
    package documents for `DEFAULT_STORE_PATH`.
    """
    for module in RAISE_SITE_MODULES:
        monkeypatch.setattr(module, "WAIT_PUBLISHER", publish)


def raise_every_wait(*, repo: Path, tmp_path: Path) -> None:
    """Drive the three shipped raise sites, in the order the loop reaches them."""
    foreman_runtime_escalation.record_blocking_prompt_escalation(repo=repo)
    _ = foreman_convene_obligations.write_convene_escalation(
        repo=repo,
        topic=PLAN,
        question_fingerprint=FINGERPRINT,
        reason=ESCALATION_REASON,
        observed_at_epoch=1.0,
        request={"question_fingerprint": FINGERPRINT},
    )
    _ = foreman_panel.convene_panel(
        request={
            "schema_version": 1,
            "blocked_question": PANEL_QUESTION,
            "repo": str(repo),
            "topic": PLAN,
            "handoff_or_work_item": "Implement the bounded formatter step.",
            "repo_context": "Python stdlib-only control-plane repo.",
        },
        state_dir=tmp_path / "state",
        verdict_path=tmp_path / "verdict.json",
        dossier_dir=tmp_path / "dossier",
    )


def test_a_foreman_wait_is_readable_without_opening_its_pane(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert MODULE_PATH.is_file()
    publication = publication_module()
    repo = tmp_path / "livespec-overseer"
    (repo / "plan" / PLAN).mkdir(parents=True)
    (repo / ".livespec.jsonc").write_text("{}", encoding="utf-8")
    plan_tree_before = plan_tree_files(repo=repo)
    recorder = ledger_recorder()
    commands, _run = recorder
    arm_publisher(
        monkeypatch=monkeypatch,
        publish=publisher_for(
            publication=publication,
            recorder=recorder,
            # ONLY the governed plan's own epic. No record is fabricated for the
            # foreman's session topic, because no such record exists in any real
            # tenant: `plan_slug` is a PLAN's slug, and the foreman session names
            # no plan.
            records=epic_records(plan_slugs={PLAN_EPIC: PLAN}),
        ),
    )

    raise_every_wait(repo=repo, tmp_path=tmp_path)

    # THE READER consults the governed plan's ledger epic and nothing else — no
    # pane capture, no `tmp/overseer/foreman/` artifact — and can still name
    # every wait the loop is parked on, which plan owns it, and why.
    plan_waits = publication.read_wait_states(
        comments=epic_comments(commands=commands, epic_id=PLAN_EPIC)
    )
    by_kind = {wait.kind: wait for wait in plan_waits}
    assert set(by_kind) == set(publication.WAIT_KINDS)
    assert by_kind[publication.PICKER_OPEN].plan == PLAN
    assert by_kind[publication.ESCALATION_AWAITING_ANSWER].plan == PLAN
    assert by_kind[publication.ESCALATION_AWAITING_ANSWER].detail == ESCALATION_REASON
    assert by_kind[publication.PANEL_IN_PROGRESS].plan == PLAN
    assert by_kind[publication.PANEL_IN_PROGRESS].detail == PANEL_QUESTION
    # The prose half is what an operator scanning the epic reads, so the wait is
    # legible without running the parser at all.
    for wait in plan_waits:
        assert publication.WAIT_HEADLINES[wait.kind] in publication.render_wait_state(wait=wait)

    # The waits still live in the foreman's private runtime state as before —
    # the ratified clause forbids publishing ONLY there, not publishing there.
    private_records = sorted((repo / "tmp" / "overseer" / "foreman").rglob("*.json"))
    assert private_records != []

    # This publishes to the LEDGER and never to the plan tree, and it writes into
    # no orchestrator-owned snapshot: every ledger act issued is a comment onto
    # one of this tenant's own epics, and `plan/` is byte-for-byte untouched.
    assert plan_tree_files(repo=repo) == plan_tree_before
    assert [argv[:2] for argv in commands] == [["bd", "comment"]] * len(publication.WAIT_KINDS)
    assert {argv[2] for argv in commands} == {PLAN_EPIC}


def test_the_foreman_own_picker_reaches_every_plan_the_loop_governs(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE DISCRIMINATING CONTROL for the picker kind: it must resolve to a REAL epic.

    A picker the foreman raises is raised in the foreman's OWN pane and parks the
    whole per-repo loop, so it is not owned by one plan the way a convene
    escalation or a panel is. The foreman's session topic is the obvious thing to
    key it on, and it is the one key that cannot work: `plan_slug` carries a
    PLAN's slug, no ledger epic in any real tenant carries the foreman session
    name, and a publication keyed on it therefore resolves to nothing and reaches
    no epic at all — a fail-open no-op that no synthetic fixture may stand in for.

    So this test supplies epics for the governed PLANS only, deliberately none for
    the foreman topic, and asserts the wait still reaches every one of them.
    """
    assert MODULE_PATH.is_file()
    publication = publication_module()
    repo = tmp_path / "livespec-overseer"
    (repo / "plan" / PLAN).mkdir(parents=True)
    (repo / "plan" / SECOND_PLAN).mkdir(parents=True)
    # An archived plan is not governed, so the loop's wait is not published to it.
    (repo / "plan" / "archive" / "retired").mkdir(parents=True)
    foreman_topic = foreman_runtime_identity.canonical_session_name(repo=repo)
    recorder = ledger_recorder()
    commands, _run = recorder
    arm_publisher(
        monkeypatch=monkeypatch,
        publish=publisher_for(
            publication=publication,
            recorder=recorder,
            records=epic_records(plan_slugs={PLAN_EPIC: PLAN, SECOND_PLAN_EPIC: SECOND_PLAN}),
        ),
    )

    foreman_runtime_escalation.record_blocking_prompt_escalation(repo=repo)

    reached = {argv[2] for argv in commands}
    assert reached == {PLAN_EPIC, SECOND_PLAN_EPIC}
    published = [
        wait
        for epic_id in sorted(reached)
        for wait in publication.read_wait_states(
            comments=epic_comments(commands=commands, epic_id=epic_id)
        )
    ]
    assert [wait.kind for wait in published] == [publication.PICKER_OPEN] * 2
    assert {wait.plan for wait in published} == {PLAN, SECOND_PLAN}
    assert foreman_topic not in {wait.plan for wait in published}


def test_a_plan_epic_carrying_other_discussion_still_reads_cleanly(*, tmp_path: Path) -> None:
    """THE DISCRIMINATING CONTROL: the reader reports waits, not every comment.

    A plan epic carries handoffs, rulings and ordinary discussion alongside this
    state. A reader that answered "what is the loop waiting on?" by reporting
    whatever it found would name a wait on every epic in the tenant, so the
    scenario above would pass against an implementation that published nothing.
    """
    assert MODULE_PATH.is_file()
    publication = publication_module()
    repo = tmp_path / "livespec-overseer"
    repo.mkdir()
    recorder = ledger_recorder()
    commands, _run = recorder
    publish = publisher_for(
        publication=publication,
        recorder=recorder,
        records=epic_records(plan_slugs={PLAN_EPIC: PLAN}),
    )

    _ = publish(
        repo=repo,
        wait=publication.WaitState(
            kind=publication.PANEL_IN_PROGRESS, plan=PLAN, detail=PANEL_QUESTION
        ),
    )
    published = epic_comments(commands=commands, epic_id=PLAN_EPIC)
    marker = publication.WAIT_MARKER
    kind = publication.PANEL_IN_PROGRESS
    non_waits: list[dict[str, object]] = [
        {"text": "An ordinary handoff entry that mentions no wait at all."},
        {"text": f"{marker} quoted inline in prose, with no payload line."},
        {"body": f"{marker}: a headline whose payload is\nnot valid JSON at all"},
        {"content": f"{marker}: a headline whose payload is\n17"},
        {"text": f'{marker}: unknown kind\n{{"kind": "lunch", "plan": "a", "detail": "d"}}'},
        {"text": f'{marker}: bad plan\n{{"kind": "{kind}", "plan": 7, "detail": "d"}}'},
        {"text": f'{marker}: bad detail\n{{"kind": "{kind}", "plan": "a", "detail": 7}}'},
        {"text": 7, "body": f"{marker} not a wait either"},
        {"id": "a-comment-record-carrying-no-text-at-all"},
    ]

    recovered = publication.read_wait_states(comments=non_waits + published)

    assert [wait.kind for wait in recovered] == [publication.PANEL_IN_PROGRESS]


def test_an_unpublishable_wait_is_refused_and_never_withheld(*, tmp_path: Path) -> None:
    """Publication is FAIL-OPEN: every refusal names itself and none of them raises."""
    assert MODULE_PATH.is_file()
    publication = publication_module()
    repo = tmp_path / "livespec-overseer"
    repo.mkdir()
    wait = publication.WaitState(kind=publication.PICKER_OPEN, plan=PLAN, detail="a picker is open")
    resolvable = epic_records(plan_slugs={PLAN_EPIC: PLAN})
    _commands, run = ledger_recorder()

    # An empty plan names no governed plan, and is refused BEFORE any ledger read.
    empty_plan = publication.publish_wait_state(
        repo=repo,
        wait=publication.WaitState(kind=publication.PICKER_OPEN, plan="", detail="d"),
        epic_records=resolvable,
        run=run,
    )
    assert empty_plan.failure().reason == publication.PLAN_EPIC_UNRESOLVED

    # A plan with no epic in the ledger cannot be published to.
    unresolved = publication.publish_wait_state(repo=repo, wait=wait, epic_records=[], run=run)
    assert unresolved.failure().reason == publication.PLAN_EPIC_UNRESOLVED

    # The tenant-ownership guard on the shipped mutation surface applies here too.
    foreign = publication.publish_wait_state(
        repo=repo,
        wait=wait,
        epic_records=epic_records(plan_slugs={FOREIGN_EPIC: PLAN}),
        run=run,
    )
    assert foreign.failure().reason == "foreign_work_item_id"

    # A ledger that answers non-zero raises RuntimeError inside the shipped
    # mutation; it arrives here on the failure track rather than as an exception,
    # which is what keeps a raise site from losing its wait to a ledger outage.
    _failing_commands, failing_run = ledger_recorder(returncode=1)
    unreachable = publication.publish_wait_state(
        repo=repo, wait=wait, epic_records=resolvable, run=failing_run
    )
    assert unreachable.failure().reason == publication.LEDGER_PUBLICATION_FAILED
    assert "ledger unreachable" in unreachable.failure().detail

    published = publication.publish_wait_state(
        repo=repo, wait=wait, epic_records=resolvable, run=run
    )
    assert published.unwrap().epic_id == PLAN_EPIC
    assert published.unwrap().text == publication.render_wait_state(wait=wait)


def test_every_raise_site_keeps_its_wait_when_the_ledger_cannot_be_reached(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The private record is written FIRST, so a refusal costs visibility, not the wait."""
    assert MODULE_PATH.is_file()
    publication = publication_module()
    repo = tmp_path / "livespec-overseer"
    (repo / "plan" / PLAN).mkdir(parents=True)
    recorder = ledger_recorder()
    commands, _run = recorder
    arm_publisher(
        monkeypatch=monkeypatch,
        publish=publisher_for(publication=publication, recorder=recorder, records=[]),
    )

    raise_every_wait(repo=repo, tmp_path=tmp_path)

    assert commands == []
    assert sorted((repo / "tmp" / "overseer" / "foreman").rglob("*.json")) != []
    assert (tmp_path / "verdict.json").is_file()


@pytest.mark.parametrize("kind", ["picker-open", "escalation-awaiting-answer", "panel-in-progress"])
def test_each_ratified_wait_kind_round_trips_through_the_ledger(*, kind: str) -> None:
    """Every kind the clause names renders and reads back as the same state."""
    assert MODULE_PATH.is_file()
    publication = publication_module()
    wait = publication.WaitState(kind=kind, plan=PLAN, detail="why the loop is parked")

    recovered = publication.read_wait_states(
        comments=[{"text": publication.render_wait_state(wait=wait)}]
    )

    assert recovered == [wait]
