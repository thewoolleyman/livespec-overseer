"""The release-lane detector's controls, driven by this lane's REAL history.

Work-item overseer-hgq4wi.15. The lane failed 139 of 157 runs across 25 days and
nobody knew; both times it was caught, it was caught by luck. These tests exist
to prove the detector separates the cases that luck could not.
"""

from __future__ import annotations

import json
from pathlib import Path

from overseer.release_lane_watch import lane_state, notice_text

__all__: list[str] = []

_HISTORY = Path(__file__).resolve().parent / "release-tag-history.json"


def _history() -> list[dict[str, str]]:
    return json.loads(_HISTORY.read_text(encoding="utf-8"))


def _between(*, rows: list[dict[str, str]], first: str, last: str) -> list[dict[str, str]]:
    return [r for r in rows if first <= r["created_at"] <= last]


def test_replay_over_the_real_sixteen_day_outage_reports_both_boundaries() -> None:
    """THE control this lane makes cheap, and the only one that separates day 1 from day 16.

    A detector emitting "the last run failed" produces identical output on the
    first cut of the block and on the hundred-and-twenty-third. Replaying the
    real 2026-08-03..2026-08-19 range and requiring the full count plus BOTH
    green boundaries is what distinguishes them.
    """
    window = _between(rows=_history(), first="2026-08-03T03:38:02Z", last="2026-08-19T12:11:08Z")

    state = lane_state(runs=window)

    assert state["consecutive_failures"] == 123
    assert state["failing_since"] == "2026-08-03T05:31:01Z"
    assert state["last_green"] == "2026-08-03T03:38:02Z"
    assert state["truncated"] is False


def test_the_notice_carries_the_absolute_last_green_not_a_relative_age() -> None:
    """On this lane the last green can be sixteen days back.

    "failing since 2026-08-03" is actionable; a relative age invites the reader
    to assume recency, which is exactly how a sixteen-day outage stays unnoticed.
    """
    window = _between(rows=_history(), first="2026-08-03T03:38:02Z", last="2026-08-19T12:11:08Z")

    text = notice_text(workflow="release-tag", state=lane_state(runs=window))

    assert "2026-08-05" not in text  # not a paraphrase of the block's interior
    assert "2026-08-03T05:31:01Z" in text
    assert "2026-08-03T03:38:02Z" in text
    assert "123" in text


def test_a_block_flush_against_the_oldest_run_is_reported_as_truncated() -> None:
    """A QUERY LIMIT IS A MEASUREMENT BOUNDARY, and this is the control for it.

    The same real block reads as 123 cuts with enough history and as a much
    smaller number when the window clips it. Three attempts across two sessions
    undercounted this outage before the rule was applied. A caller that cannot
    see a green above the block has measured a LOWER BOUND, and the detector
    must say so rather than report the short number as fact.
    """
    clipped = _between(rows=_history(), first="2026-08-18T00:00:00Z", last="2026-08-19T12:11:08Z")

    state = lane_state(runs=clipped)

    assert state["truncated"] is True
    assert state["last_green"] is None
    assert state["consecutive_failures"] < 123
    assert "at least" in notice_text(workflow="release-tag", state=state)


def test_a_healthy_lane_is_silent() -> None:
    """A watcher that speaks on every run is muted within a day."""
    healthy = [
        {"conclusion": "success", "created_at": "2026-08-20T08:19:21Z"},
        {"conclusion": "success", "created_at": "2026-08-20T09:46:04Z"},
    ]

    state = lane_state(runs=healthy)

    assert state["healthy"] is True
    assert notice_text(workflow="release-tag", state=state) == ""


def test_a_single_transient_failure_is_silent_but_two_are_not() -> None:
    """One failed cut is indistinguishable from a flake; two did not self-recover."""
    one = [
        {"conclusion": "success", "created_at": "2026-08-20T08:19:21Z"},
        {"conclusion": "failure", "created_at": "2026-08-20T09:46:04Z"},
    ]
    two = [*one, {"conclusion": "failure", "created_at": "2026-08-20T10:00:00Z"}]

    assert notice_text(workflow="release-tag", state=lane_state(runs=one)) == ""
    assert notice_text(workflow="release-tag", state=lane_state(runs=two)) != ""


def test_undecided_runs_neither_start_nor_end_an_outage() -> None:
    """A cancelled or in-flight run is not evidence either way.

    Counting one as a failure inflates an outage; counting it as a success ends
    one that is still running.
    """
    rows = [
        {"conclusion": "success", "created_at": "2026-08-20T01:00:00Z"},
        {"conclusion": "failure", "created_at": "2026-08-20T02:00:00Z"},
        {"conclusion": "cancelled", "created_at": "2026-08-20T03:00:00Z"},
        {"conclusion": "failure", "created_at": "2026-08-20T04:00:00Z"},
    ]

    state = lane_state(runs=rows)

    assert state["consecutive_failures"] == 2
    assert state["last_green"] == "2026-08-20T01:00:00Z"


def test_the_verdict_is_keyed_on_the_supplied_workflow_alone() -> None:
    """Keyed on the WORKFLOW, not on master's overall health.

    Ordinary CI on master was green throughout the sixteen-day outage, so any
    master-health signal reported healthy for its whole duration. This detector
    can only see the run history it is handed, which is the structural form of
    that requirement: a healthy sibling workflow cannot mask a failing one.
    """
    failing = _between(rows=_history(), first="2026-08-03T03:38:02Z", last="2026-08-19T12:11:08Z")
    healthy_sibling = [{"conclusion": "success", "created_at": "2026-08-10T00:00:00Z"}]

    assert lane_state(runs=failing)["healthy"] is False
    assert lane_state(runs=healthy_sibling)["healthy"] is True


def test_an_empty_history_is_not_reported_as_a_failing_lane() -> None:
    """No runs is not evidence of an outage.

    A forge query can legitimately return nothing — a brand-new workflow, or a
    filter that matched none. Reporting that as a failing lane would train the
    reader to ignore the watcher, which is the failure mode this whole item
    exists to avoid.
    """
    state = lane_state(runs=[])

    assert state["healthy"] is True
    assert state["runs_considered"] == 0
    assert state["last_green"] is None
    assert notice_text(workflow="release-tag", state=state) == ""
