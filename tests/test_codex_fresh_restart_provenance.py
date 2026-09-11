"""The provenance a fresh-Codex restart records, and what it refuses to record.

The record is what lets a later ordinary tick finish a restart whose bounded
live-adoption proof timed out. It is only worth having if it is exact, so it is written
ONLY when this attempt can name a canonical successor rollout, and it is read back only
when every member it needs survived intact. A half-read record would be worse than none:
the comparison it exists to support is the whole reason a late reconciliation may
consume a ``ready`` declaration at all.
"""

from __future__ import annotations

import contextlib
import io as _io
import json

import _supervisor_codex_successor
import codex_sessions
import pytest
import registry
import signals
from test_codex_late_successor_reconciliation import (
    PRIOR_INDEXED_AT,
    RENAMED_AT,
    write_index,
)
from test_supervisor_builders import (
    FRESH_CODEX_SESSION_ID,
    adopt_codex_ready,
    codex_busy_capture,
    mapped_track,
)

__all__: list[str] = []

PRIOR_SESSION_ID = "019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"
UNINDEXED_SESSION_ID = "codex-rollout-without-a-uuid"


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _sidecar_record(*, tmp_path, member):
    """Write one hand-authored provenance member into an otherwise ordinary round."""
    stamp = tmp_path / "stamps.json"
    registry.write_injection_stamp(repo=str(tmp_path), topic="topic", ts=10.0, stamp_path=stamp)
    data = json.loads(stamp.read_text(encoding="utf-8"))
    key = next(iter(data))
    data[key]["codex_fresh_restart"] = member
    stamp.write_text(json.dumps(data), encoding="utf-8")
    return registry.read_codex_fresh_restart(repo=str(tmp_path), topic="topic", stamp_path=stamp)


def test_a_round_with_no_recorded_restart_reads_back_as_nothing(*, tmp_path):
    stamp = tmp_path / "stamps.json"
    registry.write_injection_stamp(repo=str(tmp_path), topic="topic", ts=10.0, stamp_path=stamp)

    assert (
        registry.read_codex_fresh_restart(repo=str(tmp_path), topic="topic", stamp_path=stamp)
        is None
    )


def test_a_track_with_no_round_at_all_reads_back_as_nothing(*, tmp_path):
    assert (
        registry.read_codex_fresh_restart(
            repo=str(tmp_path), topic="topic", stamp_path=tmp_path / "stamps.json"
        )
        is None
    )


def test_a_provenance_member_that_is_not_an_object_is_refused(*, tmp_path):
    assert _sidecar_record(tmp_path=tmp_path, member="01a08dd5") is None


def test_a_provenance_record_missing_any_identity_member_is_refused(*, tmp_path):
    """Fail-closed field by field: five sixths of an identity proves nothing."""
    complete = {
        "predecessor": "a",
        "successor": "b",
        "tmux": "c",
        "pane": "d",
        "repo": "e",
        "resume": "f",
    }
    for member in complete:
        partial = {name: value for name, value in complete.items() if name != member}
        assert _sidecar_record(tmp_path=tmp_path, member=partial) is None
    empty_valued = {**complete, "tmux": ""}
    assert _sidecar_record(tmp_path=tmp_path, member=empty_valued) is None

    assert _sidecar_record(tmp_path=tmp_path, member=complete) == registry.CodexFreshRestart(
        predecessor="a",
        successor="b",
        tmux="c",
        pane="d",
        repo="e",
        resume="f",
        resume_submitted=False,  # absent reads as NOT delivered — the safe direction
    )


def test_marking_a_resume_delivered_is_a_no_op_when_nothing_was_recorded(*, tmp_path):
    """The restart marks unconditionally after a confirmed submit; an unrecorded attempt
    must not grow a half-built record out of it."""
    stamp = tmp_path / "stamps.json"
    registry.write_injection_stamp(repo=str(tmp_path), topic="topic", ts=10.0, stamp_path=stamp)

    registry.mark_codex_fresh_restart_resume_submitted(
        repo=str(tmp_path), topic="topic", stamp_path=stamp
    )
    registry.mark_codex_fresh_restart_resume_submitted(
        repo=str(tmp_path), topic="other", stamp_path=stamp
    )

    assert (
        registry.read_codex_fresh_restart(repo=str(tmp_path), topic="topic", stamp_path=stamp)
        is None
    )
    assert (
        registry.read_injection_stamp(repo=str(tmp_path), topic="topic", stamp_path=stamp) == 10.0
    )


def _named_from(*, tmp_path, slot, indexed, live_session_id):
    """Ask the naming proof for the successor's IDENTITY under one evidence shape."""
    root = tmp_path / slot
    root.mkdir()
    repo, topic, session, _prior, _fake, sup = adopt_codex_ready(tmp_path=root)
    home = root / "naming-codex-home"
    records = [(PRIOR_SESSION_ID, PRIOR_INDEXED_AT)]
    if indexed is not None:
        records.append((indexed, RENAMED_AT))
    write_index(home=home, topic=topic, records=records)
    sup.codex_home = str(home)
    sup.live_codex = (
        {}
        if live_session_id is None
        else {
            (session, topic): codex_sessions.CodexSession(
                pid=5150, name=topic, cwd=str(repo), session_id=live_session_id
            )
        }
    )
    return _supervisor_codex_successor.named_successor_rollout(
        sup=sup,
        track=mapped_track(repo=repo, topic=topic, session=session),
        session=session,
        prior_session_id=PRIOR_SESSION_ID,
    )


def test_the_naming_proof_reports_the_successor_it_actually_proved(*, tmp_path):
    """Four evidence shapes, one answer each — the durable record first, the fd join
    second, and silence whenever neither can name a comparable rollout."""
    indexed_answer = _named_from(
        tmp_path=tmp_path, slot="indexed", indexed=FRESH_CODEX_SESSION_ID, live_session_id=None
    )
    live_answer = _named_from(
        tmp_path=tmp_path, slot="live", indexed=None, live_session_id=FRESH_CODEX_SESSION_ID
    )
    no_evidence = _named_from(tmp_path=tmp_path, slot="none", indexed=None, live_session_id=None)
    unchanged = _named_from(
        tmp_path=tmp_path, slot="same", indexed=None, live_session_id=PRIOR_SESSION_ID
    )

    assert indexed_answer == FRESH_CODEX_SESSION_ID
    assert live_answer == FRESH_CODEX_SESSION_ID
    assert no_evidence is None
    assert unchanged is None


def test_a_successor_whose_rollout_id_is_uncomparable_records_no_provenance(*, tmp_path):
    """The restart still runs — this is the store-bound unindexed shape, which the arm
    has always supported — but nothing is recorded, so no late tick can reconcile it.

    That is deliberate and it is the conservative direction: an id that cannot be
    compared cannot later prove the daemon launched this session, and a record that
    cannot discriminate is worse than no record at all.
    """
    repo, topic, session, prior_session_id, fake, sup = adopt_codex_ready(tmp_path=tmp_path)
    home = tmp_path / "unindexed-codex-home"
    write_index(home=home, topic=topic, records=[(prior_session_id, PRIOR_INDEXED_AT)])
    sup.codex_home = str(home)
    live = {"session_id": UNINDEXED_SESSION_ID}

    def paste_effects(paste_session, text):
        if text == f"/rename {topic}":
            return
        fake.panes[paste_session] = codex_busy_capture(ctx=95)
        live["session_id"] = None  # the successor stops holding its rollout open

    fake.on_paste = paste_effects

    def store_bound_only() -> None:
        sup.live_codex = (
            {}
            if live["session_id"] is None
            else {
                (session, topic): codex_sessions.CodexSession(
                    pid=5150, name=topic, cwd=str(repo), session_id=live["session_id"]
                )
            }
        )

    sup._refresh_codex_sessions = store_bound_only
    log = _io.StringIO()

    with contextlib.redirect_stderr(log):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "restarting"
    assert "never named for this plan topic" not in log.getvalue()  # naming DID succeed
    assert signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    assert (
        registry.read_codex_fresh_restart(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )
