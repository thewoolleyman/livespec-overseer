"""The post-rename idle gap a fresh Codex wrap-up restart has to survive.

Measured live 2026-09-11, on the first natural control of the fresh-Codex arm. The
daemon dispatched a restart at 00:19:33Z; the new carrier and binary came up at
00:19:33Z and 00:19:42Z; ``session_index.jsonl`` persisted the ``/rename`` record —
``thread_name`` for the successor rollout — at 00:19:46Z. The restart nonetheless gave
up at 00:20:04Z with ``codex-fresh-session-unadopted``, kept the predecessor's ``ready``
declaration, and never submitted the resume line at all. The surviving rollout took its
first user turn more than three hours later, by hand.

Nothing about the successor was missing: the carrier, its canonical rollout id, its cwd
and the durable thread-name record all existed. What was missing was FD EVIDENCE — the
``codex_sessions`` join needs a live process holding the rollout open, and in the idle
seconds right after the rename that join can come back empty. The old arm made that
join the gate on naming, and reached the resume submit only through it, so an empty
window there cost the whole round.

So the order changed: the name is confirmed from evidence that EXISTS in that phase (the
durable index record naming a rollout that is not the predecessor's), the resume turn is
submitted, and the fd-gated different-rollout join is then proved while Codex is
executing that turn. Nothing was weakened — the round still closes only on a canonical
successor rollout, in this tmux session and this repository, different from the one that
was live before the respawn.
"""

from __future__ import annotations

import contextlib
import io as _io
import json
from pathlib import Path

import codex_sessions
import pytest
import signals
from test_supervisor_builders import (
    FRESH_CODEX_SESSION_ID,
    TEST_EPIC,
    adopt_codex_ready,
    codex_busy_capture,
    mapped_track,
)

__all__: list[str] = []

# The measured timeline: the predecessor's index record, then the one `/rename` appends
# for the successor thirteen seconds after the respawn.
PRIOR_INDEXED_AT = "2026-09-11T00:10:00Z"
RENAMED_AT = "2026-09-11T00:19:46Z"


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _write_index(*, home: Path, topic: str, records) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "session_index.jsonl").write_text(
        "".join(
            json.dumps({"id": session_id, "thread_name": topic, "updated_at": updated}) + "\n"
            for session_id, updated in records
        ),
        encoding="utf-8",
    )


def _post_rename_idle_gap(*, tmp_path, rename_persists):
    """Model the measured sequence: named in the index, undiscoverable while idle.

    ``rename_persists`` is the one thing that varies. With it, `/rename <topic>` appends
    the successor's durable record exactly as Codex does; without it nothing ever names
    the successor, which is the failure leg — the round must keep the declaration rather
    than submit a resume line into a session it cannot prove it can track.

    Live discovery stays EMPTY for as long as the successor is idle, and starts reporting
    the fresh rollout only once the resume turn has been pasted. That is the gap itself:
    every fd-gated probe taken before the submit is counted, so a restart that still
    depends on one before submitting is visible rather than merely slow.
    """
    repo, topic, session, session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    home = tmp_path / "post-rename-codex-home"
    _write_index(home=home, topic=topic, records=[(session_id, PRIOR_INDEXED_AT)])
    sup.codex_home = str(home)
    seen = {"resume_pasted": False, "fd_probes_before_resume": 0}

    def paste_effects(paste_session, text):
        if text == f"/rename {topic}":
            if rename_persists:
                _write_index(
                    home=home,
                    topic=topic,
                    records=[
                        (session_id, PRIOR_INDEXED_AT),
                        (FRESH_CODEX_SESSION_ID, RENAMED_AT),
                    ],
                )
            return  # a slash command asks the model for nothing; the pane stays idle
        fake.panes[paste_session] = codex_busy_capture(ctx=95)
        seen["resume_pasted"] = True

    fake.on_paste = paste_effects

    def discoverable_only_while_working() -> None:
        if not seen["resume_pasted"]:
            seen["fd_probes_before_resume"] += 1
            sup.live_codex = {}
            return
        sup.live_codex = {
            (session, topic): codex_sessions.CodexSession(
                pid=5150, name=topic, cwd=str(repo), session_id=FRESH_CODEX_SESSION_ID
            )
        }

    sup._refresh_codex_sessions = discoverable_only_while_working
    return repo, topic, session, fake, sup, seen


def test_a_fresh_codex_restart_completes_across_the_post_rename_discovery_gap(*, tmp_path):
    """The whole measured round, end to end, with the fd join empty the entire idle phase.

    Sabotage: put the fd-gated live join back in front of the resume submit and this goes
    red exactly where the live control did — no resume, declaration retained, and the
    successor left sitting idle with an empty context window and nothing to do.
    """
    repo, topic, session, fake, sup, seen = _post_rename_idle_gap(
        tmp_path=tmp_path, rename_persists=True
    )
    log = _io.StringIO()

    with contextlib.redirect_stderr(log):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "restarting"
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_RESTARTED
    # The naming phase needed no fd evidence at all — which is the fix, stated as a number.
    assert seen["fd_probes_before_resume"] == 0
    pastes = fake.paste_texts()
    assert pastes[0] == f"/rename {topic}"  # named first, from the durable record...
    assert TEST_EPIC in pastes[1]  # ...then the ledger-grounded resume turn
    assert len([call for call in fake.calls if call[0] == "respawn"]) == 1
    assert log.getvalue().count(f"restarted (codex) {repo}::{topic}") == 1

    # EXACTLY once: the consumed declaration leaves nothing for a second tick to act on.
    fake.calls.clear()
    with contextlib.redirect_stderr(log):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert not fake.has(method="respawn")
    assert log.getvalue().count(f"restarted (codex) {repo}::{topic}") == 1


def test_a_fresh_codex_restart_that_cannot_confirm_the_name_keeps_ready_and_says_so(*, tmp_path):
    """A successor nothing names is a successor the daemon cannot prove it can track.

    The resume line is never submitted into it — submitting first and discovering later
    that the round cannot be proved would spend the declaration on a session the next
    tick cannot find. So the declaration is retained with its own diagnostic, distinct
    from the un-submitted-resume and unadopted-successor legs.
    """
    repo, topic, session, fake, sup, _seen = _post_rename_idle_gap(
        tmp_path=tmp_path, rename_persists=False
    )
    log = _io.StringIO()

    with contextlib.redirect_stderr(log):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    assert "never named for this plan topic" in log.getvalue()
    assert "never took the resume line" not in log.getvalue()
    assert f"restarted (codex) {repo}::{topic}" not in log.getvalue()
    assert fake.paste_texts() == [f"/rename {topic}"]  # the resume was never submitted
