"""Shared track/state-file fixtures for the `signals` beside-tests.

Extracted so `test_signals.py` (pane-text parsing + marker certification) and
`test_signals_process_identity.py` share ONE pair of builders instead of one test
module importing the other's privates. Neither half exceeded a ceiling alone
before the split; their COMBINED module crossed the 200-LLOC soft band, which is
what forced it.

No tests live here. The name keeps the `test_*` prefix deliberately: coverage
omits `overseer/test_*.py`, so a differently-named helper in this package would be
measured as product code and demand 100% coverage of a test fixture.
"""

import os

import signals

__all__: list[str] = ["declare_state", "setup_track"]


def setup_track(tmp_path):
    """A watched track: a repo with the session's own ``plan/<topic>/`` dir.

    The overseer's markers live under ``<repo>/tmp/overseer/<topic>/`` (created by
    the marker-writing helpers), NEVER under ``plan/`` — the ``plan/`` dir here is
    only the session's own workflow tree, which the overseer never touches.
    """
    repo = tmp_path / "repo"
    topic = "mytopic"
    (repo / "plan" / topic).mkdir(parents=True)
    return repo, topic


def declare_state(repo, topic, value, *, mtime):
    """The session writes its ONE state file, creating the parent TEMP dir first.

    The single indicator lives at ``<repo>/tmp/overseer/<topic>/.overseer-state``, whose
    parent does not exist yet — so the helper mkdirs it.
    """
    path = signals.state_path(str(repo), topic)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path
