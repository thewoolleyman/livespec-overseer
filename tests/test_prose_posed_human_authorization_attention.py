"""A prose-posed human authorization must reach the machine-readable attention surface.

`overseer-j2vbcq`. A session parked on a human decision posed as PROSE at a free
prompt — no picker frame, no numbered-cursor marker, no selection footer — read
`picker_open false` AND `human_wait false` on the daemon snapshot while the decision
was genuinely pending. `picker_open` was RIGHT and must stay right: there is no
structured picker in that shape. The gap is everything else.

The remedy has two legs and neither of them reads the pane's prose.

**The compliance leg** uses the channel `overseer/marker-protocol.md` already
mandates: a session waiting on a human that no structured gate can carry writes
`blocked: <reason>`, which sets `human_wait` from the state file with no pane read at
all. That path is asserted end to end here rather than assumed, because the whole
remedy rests on it.

**The non-declaration leg** is the actual gap. Between a session becoming
prose-blocked and its declaration, the daemon cannot tell "nothing pending" from
"pending but undeclared", so a session that answers the keep-going nudge
conversationally without ever declaring stays silently mis-declared. The daemon now
surfaces that as `undeclared-idle` — and BOUNDS it, so it cannot repeat indefinitely.

**No prose heuristic** (`overseer-i6eu2k`, and
`plan/archive/supervision-safety-and-attention-truth/research/prose-question-detector-inversion.md`).
Recognising a question in a capture is forbidden, not merely controlled: this fleet's
sessions write prose ABOUT pending questions when supervision is working well, so a
prose detector's errors concentrate on its best-written members. The two-way control
below proves the new signal is blind to prose in BOTH directions, and
`test_undeclared_idle_reads_no_pane_capture` proves it structurally.
"""

from __future__ import annotations

import ast
import contextlib
import io as _io
import json
from pathlib import Path

import _supervisor_config
import foreman_plan_roster
import pytest
import registry
import supervisor
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent

# A pane whose PROSE poses a human-directed question at an ordinary free prompt. It
# carries no checkbox glyph, no numbered-cursor option line and no selection footer,
# so it is not a structured gate — which is exactly the shape `overseer-j2vbcq`
# measured, and exactly the shape a prose detector would key on.
_PROSE_QUESTION = (
    "I am idle waiting on a USER AUTHORIZATION, not on a dispatch slot, and no peer "
    "answer can substitute for that authorization. How should this be landed? "
    "1. Force-push the rebase. 2. Open a fresh PR. 3. Hand it to the foreman."
)


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _tracked(*, tmp_path, capture, clock=None):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=capture)
    kwargs = {} if clock is None else {"now": lambda: clock["t"]}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, **kwargs)
    sup.claude_status_by_session = {session: "idle"}
    return repo, topic, fake, sup, mapped_track(repo=repo, topic=topic, session=session)


def _bounded(*, monkeypatch, after: float, until: float) -> None:
    """Shrink the shipped durations so a test clock can cross them.

    Every step below must stay under `CONDITION_CONTINUITY_GAP`, or `advance_condition`
    would read the jump as a gap and restart the episode — which would make the bound
    look enforced when it was only reset.
    """
    monkeypatch.setattr(_supervisor_config, "UNDECLARED_IDLE_AFTER", after, raising=False)
    monkeypatch.setattr(_supervisor_config, "UNDECLARED_IDLE_REPORTED_UNTIL", until, raising=False)


# --------------------------------------------------------------------------- #
# 1. COMPLIANCE LEG — the declared human wait, proven end to end.
# 3. `picker_open` MUST REMAIN FALSE for this shape.
# --------------------------------------------------------------------------- #


def test_blocked_declaration_with_no_structured_gate_is_a_machine_readable_human_wait(*, tmp_path):
    _repo, _topic, _fake, sup, track = _tracked(
        tmp_path=tmp_path, capture=idle_capture(ctx=74, body=_PROSE_QUESTION)
    )
    declare(
        repo=_repo,
        topic=_topic,
        value="blocked: waiting on a user authorization no peer can substitute for",
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        row = sup.evaluate(track=track, act=True)

    assert row.status == "blocked:human"
    assert row.human_wait is True
    # Criterion 3: the fix must not be reached by widening picker detection. There is
    # no structured picker in this pane and the field must keep saying so.
    assert row.picker_open is False
    assert supervisor.needs_attention(row=row) is True


# --------------------------------------------------------------------------- #
# 2. NEGATIVE CONTROL — mere idleness is not a human wait.
# --------------------------------------------------------------------------- #


def test_ordinary_idle_pane_with_no_pending_question_is_not_marked_as_awaiting_a_human(*, tmp_path):
    _repo, _topic, _fake, sup, track = _tracked(tmp_path=tmp_path, capture=idle_capture(ctx=74))

    with contextlib.redirect_stderr(_io.StringIO()):
        row = sup.evaluate(track=track, act=True)

    assert row.human_wait is False
    assert row.picker_open is False
    assert row.status != "blocked:human"


# --------------------------------------------------------------------------- #
# 4. ROSTER RESOLUTION — assert the emoji, not just the field.
# --------------------------------------------------------------------------- #


def test_a_declared_human_wait_resolves_to_the_blocked_emoji_on_the_plan_roster(*, tmp_path):
    repo = tmp_path / "repo"
    (repo / "plan" / "alpha").mkdir(parents=True)
    snapshot_path = tmp_path / "status.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "daemon_instance_id": "daemon-1",
                "tick_generation": 1,
                "written_at": "2026-08-22T00:00:00Z",
                "rows": [
                    {
                        "repo": str(repo),
                        "topic": "alpha",
                        "tmux": "alpha",
                        "runtime": "claude",
                        "status": "blocked:human",
                        "human_wait": True,
                        "picker_open": False,
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    roster = foreman_plan_roster.compose_roster(
        repo=repo, snapshot_path=snapshot_path, tmux_sessions=["alpha"]
    )

    row = roster["rows"][0]
    assert row["session_state"] == foreman_plan_roster.SESSION_PICKER_PARKED
    # The mapping is where the row becomes visible to an operator, so the emoji is the
    # assertion — not the underlying field it is derived from.
    assert row["emoji"] == "🔴"


# --------------------------------------------------------------------------- #
# 5. NON-DECLARATION LEG — the actual gap, and its BOUND.
# --------------------------------------------------------------------------- #


def test_idle_past_the_nudge_floor_without_a_declaration_is_surfaced_and_then_bounded(
    *, tmp_path, monkeypatch
):
    _bounded(monkeypatch=monkeypatch, after=30.0, until=120.0)
    clock = {"t": 1000.0}
    _repo, _topic, fake, sup, track = _tracked(
        tmp_path=tmp_path, capture=idle_capture(ctx=74), clock=clock
    )

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        healthy = sup.evaluate(track=track, act=True)
        clock["t"] += 31.0
        surfaced = sup.evaluate(track=track, act=True)
        clock["t"] += 60.0
        still_surfaced = sup.evaluate(track=track, act=True)
        clock["t"] += 60.0
        past_bound = sup.evaluate(track=track, act=True)
        clock["t"] += 600.0
        long_past_bound = sup.evaluate(track=track, act=True)

    # Distinguishable from healthy idle: the same pane, the same declaration state,
    # a different status once the floor is crossed.
    assert healthy.status == "idle-with-context-left"
    assert supervisor.needs_attention(row=healthy) is False
    assert surfaced.status == "undeclared-idle"
    assert supervisor.needs_attention(row=surfaced) is True
    assert "no ready, blocked or winding-down declaration" in (surfaced.note or "")
    assert still_surfaced.status == "undeclared-idle"

    # THE BOUND, asserted rather than the condition alone. Two siblings under this
    # subject (`overseer-t6m`, `overseer-94fs`) are unbounded-shield defects; an
    # unbounded report here would be the third. Past the bound the row stops being
    # held and cannot re-raise without an intervening non-idle episode, however long
    # the session then sits there.
    assert past_bound.status == "idle-with-context-left"
    assert supervisor.needs_attention(row=past_bound) is False
    assert long_past_bound.status == "idle-with-context-left"

    # Edge-triggered AND bounded: one alert for the whole episode, not one per tick
    # and not a fresh one once the bound has passed.
    events = [json.loads(line) for line in err.getvalue().splitlines()]
    undeclared = [event for event in events if "undeclared idle (" in str(event.get("message"))]
    assert len(undeclared) == 1
    assert undeclared[0]["severity"] == "alert"
    # Report-only: the condition never keystrokes on its own account.
    assert not fake.has(method="respawn")


def test_read_only_evaluation_surfaces_the_condition_without_alerting(*, tmp_path, monkeypatch):
    _bounded(monkeypatch=monkeypatch, after=30.0, until=120.0)
    clock = {"t": 1000.0}
    _repo, _topic, _fake, sup, track = _tracked(
        tmp_path=tmp_path, capture=idle_capture(ctx=74), clock=clock
    )

    with contextlib.redirect_stderr(_io.StringIO()) as err:
        _ = sup.evaluate(track=track, act=False)
        clock["t"] += 31.0
        row = sup.evaluate(track=track, act=False)

    assert row.status == "undeclared-idle"
    assert "undeclared idle" not in err.getvalue()


@pytest.mark.parametrize("declaration", ["winding-down", "blocked: needs a human"])
def test_a_session_that_declares_is_never_reported_undeclared(
    *, tmp_path, monkeypatch, declaration
):
    _bounded(monkeypatch=monkeypatch, after=30.0, until=120.0)
    clock = {"t": 1000.0}
    _repo, _topic, _fake, sup, track = _tracked(
        tmp_path=tmp_path, capture=idle_capture(ctx=74, body=_PROSE_QUESTION), clock=clock
    )
    declare(repo=_repo, topic=_topic, value=declaration)

    with contextlib.redirect_stderr(_io.StringIO()):
        _ = sup.evaluate(track=track, act=True)
        clock["t"] += 31.0
        row = sup.evaluate(track=track, act=True)

    assert row.status != "undeclared-idle"


# --------------------------------------------------------------------------- #
# 6. NO PROSE HEURISTIC — proven two ways: behaviourally and structurally.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("body", ["", _PROSE_QUESTION])
def test_the_undeclared_signal_is_blind_to_the_panes_prose(*, tmp_path, monkeypatch, body):
    """Question-like prose neither raises the condition nor suppresses it.

    A pane whose prose poses three numbered options and one whose prose poses nothing
    reach the SAME verdict, because the verdict is derived from the state file and the
    idle clock and never from the capture.
    """
    _bounded(monkeypatch=monkeypatch, after=30.0, until=120.0)
    clock = {"t": 1000.0}
    _repo, _topic, _fake, sup, track = _tracked(
        tmp_path=tmp_path, capture=idle_capture(ctx=74, body=body), clock=clock
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        _ = sup.evaluate(track=track, act=True)
        clock["t"] += 31.0
        row = sup.evaluate(track=track, act=True)

    assert row.status == "undeclared-idle"
    assert row.picker_open is False


def test_undeclared_idle_reads_no_pane_capture():
    """The prohibition is structural, not a promise: the module cannot see the pane.

    Keyed on the ATTRIBUTE ACCESS rather than on the source text, so the module may
    still EXPLAIN in prose why it does not read a capture — the same distinction the
    picker detector had to learn when quoted markers in prose raised `picker_open`.
    """
    for tree in ("overseer", ".claude-plugin/overseer"):
        module_path = _REPO_ROOT / tree / "_supervisor_undeclared_idle.py"
        assert module_path.is_file(), f"{tree} is missing the undeclared-idle monitor"
        source = module_path.read_text(encoding="utf-8")
        attributes = {
            node.attr for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Attribute)
        }
        assert "capture" not in attributes, f"{tree} reads the pane capture"


# --------------------------------------------------------------------------- #
# The shipped durations, so a green suite cannot rest on monkeypatched ones.
# --------------------------------------------------------------------------- #


def test_the_shipped_report_window_sits_past_the_nudge_floor_and_is_bounded():
    after = getattr(_supervisor_config, "UNDECLARED_IDLE_AFTER", None)
    until = getattr(_supervisor_config, "UNDECLARED_IDLE_REPORTED_UNTIL", None)

    assert after is not None and after > _supervisor_config.IDLE_NUDGE_AFTER
    assert until is not None and until > after
