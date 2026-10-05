"""Identity integrity ACROSS a reply's whole payload, not just at the entry used.

A second independent review of the observation adapter confirmed the pane-
ownership and non-positive-identity fixes and found two malformed payloads still
succeeding. Both share one shape: the adapter validated the entry it was going to
USE and ignored the rest of the payload, so a reply it could already see was
malformed became authoritative evidence.

  1. **A single invalid non-leader process identity was tolerated.** With a valid
     leader present, a sibling entry carrying `pid: true`, `pid: 0`, `pid: -1`, or
     no `pid` at all still returned the leader. The duplicate check put invalid
     identities into its bookkeeping as `None` rather than refusing them, so an
     invalid identity was only caught if it appeared TWICE — which is the wrong
     trigger: one impossible pid already means the server's process list cannot
     be trusted, and that list is what the restart interlock would read.
  2. **Duplicate pane coordinates enumerated as two panes.** A listing carrying
     `w1:p1` twice, with different tab ids and cwds, returned both rows. A pane
     id is unique within a server by construction
     (`plan/herdr-overseer/research/002-herdr-api-evidence.md`), so a listing
     that repeats one is contradictory — and the daemon uses enumeration to
     decide whether the pane it is bound to still exists, which two conflicting
     answers cannot support.

Both are PURE-layer judgements about a reply's internal consistency, so they are
asserted directly against `herdr_calls` with no socket and no herdr binary —
which also means they hold on the CI lane, where herdr is absent.

**Each case carries its positive control in the same test.** A guard that
refuses valid payloads too would satisfy every negative assertion here, and that
is exactly how an over-tightened check hides: a unique decoy `pid: 77` must still
resolve its leader, and two DISTINCT pane ids must still enumerate as two panes.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

__all__: list[str] = []

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "overseer"
CALLS_PATH = PACKAGE_DIR / "herdr_calls.py"

PANE = "w1:p1"
GROUP = 42
LEADER: dict[str, object] = {"pid": GROUP, "name": "leader", "cmdline": "leader", "cwd": "/l"}


def _calls() -> Any:
    assert CALLS_PATH.is_file(), f"the pure herdr call layer needs {CALLS_PATH.name}"
    return importlib.import_module("herdr_calls")


def _foreground(*, calls: Any, processes: list[object]) -> Any:
    return calls.foreground_process(
        result={
            "process_info": {
                "pane_id": PANE,
                "shell_pid": 10,
                "foreground_process_group_id": GROUP,
                "foreground_processes": processes,
            }
        }
    )


def _row(*, pane_id: str, tab_id: str = "w1:t1", cwd: str = "/a") -> dict[str, object]:
    return {"pane_id": pane_id, "tab_id": tab_id, "workspace_id": "w1", "cwd": cwd}


def test_an_invalid_identity_anywhere_in_the_foreground_list_refuses_the_reading():
    """One impossible pid condemns the whole list, even beside a valid leader.

    The leader is present and well-formed in every case, so the earlier
    behaviour returned it and discarded the fact that its sibling was
    impossible. `pid: true` is listed first deliberately: `bool` is an `int`
    subclass, so it is the case a naive integer check admits as pid 1.
    """
    calls = _calls()
    cases = {
        "a boolean pid": {"pid": True, "name": "boolish"},
        "a zero pid": {"pid": 0, "name": "zero"},
        "a negative pid": {"pid": -1, "name": "negative"},
        "no pid at all": {"name": "anonymous"},
        "a non-integer pid": {"pid": "77", "name": "stringy"},
    }

    for defect, decoy in cases.items():
        assert (
            _foreground(calls=calls, processes=[decoy, LEADER]) is None
        ), f"a foreground list containing {defect} was trusted"
        # Also when it follows the leader: position must not decide.
        assert (
            _foreground(calls=calls, processes=[LEADER, decoy]) is None
        ), f"{defect} after the leader was trusted"


def test_a_valid_unique_decoy_still_resolves_its_leader():
    """The positive control for the check above — valid siblings are not refused.

    A pane running a pipeline legitimately reports several processes in its
    foreground group, so refusing every list with more than one entry would
    break real readings rather than malformed ones.
    """
    calls = _calls()

    reading = _foreground(
        calls=calls,
        processes=[{"pid": 77, "name": "decoy", "cmdline": "decoy", "cwd": "/d"}, LEADER],
    )

    assert reading is not None
    assert reading.name == "leader"
    assert reading.process_group_id == GROUP


def test_a_listing_repeating_a_pane_coordinate_is_refused():
    """A pane id is unique within a server, so a listing repeating one is contradictory.

    The two rows here disagree about the pane's tab and cwd, which is what makes
    "pick one" indefensible; but the refusal is on the REPEAT itself rather than
    on the disagreement, because a caller cannot know which fields a server might
    repeat consistently and a repeated coordinate is malformed either way.
    """
    calls = _calls()

    repeated = calls.pane_rows(
        result={
            "panes": [
                _row(pane_id=PANE, tab_id="w1:t1", cwd="/a"),
                _row(pane_id=PANE, tab_id="w1:t9", cwd="/b"),
            ]
        }
    )

    assert repeated is None, f"a listing repeating {PANE} was accepted: {repeated}"


def test_distinct_pane_coordinates_still_enumerate_as_separate_panes():
    """The positive control: a real multi-pane listing is unaffected."""
    calls = _calls()

    rows = calls.pane_rows(
        result={"panes": [_row(pane_id=PANE), _row(pane_id="w1:p2", tab_id="w1:t1")]}
    )

    assert rows is not None
    assert [row.pane_id for row in rows] == [PANE, "w1:p2"]
