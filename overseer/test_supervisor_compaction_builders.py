"""Builders for the context-compaction beside-tests.

No tests live here; see `test_supervisor_fakes` for why the `test_` prefix and the
public member names are both load-bearing.

Every fixture here MAPS its track into the store before ticking. That is not
boilerplate: the compaction record is a durable per-track field, and
`registry.record_context_compaction` is a field-scoped update that no-ops when the
row does not exist — so an unmapped track would tick forever with the latch silently
never persisting, and the beside-test would pass against a daemon that cannot.
"""

import codex_sessions
import registry
from test_supervisor_capture_builders import (
    busy_capture,
    codex_busy_capture,
    codex_idle_capture,
    idle_capture,
)
from test_supervisor_codex_builders import FRESH_CODEX_SESSION_ID, adopt_sup, codex_home_with
from test_supervisor_core_builders import make_supervisor
from test_supervisor_fakes import FakeTmux
from test_supervisor_store_builders import make_plan, mapped_track

__all__: list[str] = []

PREDECESSOR_CODEX_ID = "019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"
SUCCESSOR_CLAUDE_IDENTITY = "claude:4242:successor-start:topic"


def stored_track(*, sup, repo, topic):
    """Re-read the track from the store, the way each fresh tick's `build_rows` does.

    The durable record is carried ON the track, so a test that kept one Track object
    across ticks would be testing an in-memory value and would pass even if nothing
    were persisted at all.
    """
    wanted = registry.norm(repo=str(repo))
    for track in registry.read_valid_mapping(store_path=sup.store_path):
        if registry.norm(repo=track.repo) == wanted and track.topic == topic:
            return track
    raise AssertionError(f"no mapping row for {repo}::{topic}")


def compaction_record(*, sup, repo, topic):
    return stored_track(sup=sup, repo=repo, topic=topic).context_compaction


def claude_compaction_track(*, tmp_path, ctx):
    """A mapped Claude track busy below its wind-down threshold."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=busy_capture(ctx=ctx))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )
    return repo, topic, session, fake, sup


def codex_compaction_track(*, tmp_path, ctx):
    """A mapped Codex track busy below its wind-down threshold.

    Discovery is modelled ACROSS the respawn exactly as `adopt_codex_ready` models it:
    before the respawn the topic resolves to the predecessor's rollout, afterwards to
    `FRESH_CODEX_SESSION_ID`. That id CHANGE is both the restart's own post-respawn
    proof and — independently — the evidence this subsystem clears its latch on.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=codex_busy_capture(ctx=ctx), cmd="bun")
    fake.codex_busy_frame = codex_busy_capture(ctx=95)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={},
        starttimes={},
        codex_home=str(
            codex_home_with(
                tmp_path=tmp_path,
                topic=topic,
                session_id=PREDECESSOR_CODEX_ID,
                rollout=False,
                renamed_to=FRESH_CODEX_SESSION_ID,
            )
        ),
    )

    def seeded_codex_session():
        respawned = any(call[0] == "respawn" for call in fake.calls)
        live_id = FRESH_CODEX_SESSION_ID if respawned else PREDECESSOR_CODEX_ID
        sup.live_codex = {
            (session, topic): codex_sessions.CodexSession(
                pid=4242, name=topic, cwd=str(repo), session_id=live_id
            )
        }

    seeded_codex_session()
    sup._refresh_codex_sessions = seeded_codex_session
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session), store_path=sup.store_path
    )
    return repo, topic, session, fake, sup


def show_pane(*, fake, session, capture):
    fake.panes[session] = capture


def claude_busy(*, ctx):
    return busy_capture(ctx=ctx)


def claude_idle(*, ctx):
    return idle_capture(ctx=ctx)


def codex_busy(*, ctx):
    return codex_busy_capture(ctx=ctx)


def codex_idle(*, ctx, topic="topic"):
    return codex_idle_capture(ctx=ctx, topic=topic)
