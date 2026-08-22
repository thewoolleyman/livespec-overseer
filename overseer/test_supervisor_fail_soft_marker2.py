"""Beside-tests for supervisor.py — fail soft marker2.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io
import json
import os
from pathlib import Path

import codex_sessions
import pytest
import registry
from test_supervisor_builders import (
    adopt_sup,
    arm_ready_marker,
    codex_idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_codex_restart_alerts_when_the_codex_session_vanished_before_the_respawn(*, tmp_path):
    """#4/B5: `_do_codex_restart` resolves the session id from the live per-tick map. If
    the codex process died between the map refresh and the restart, there is no id to
    resume — so it must alert and KEEP the declaration, never respawn a guessed target."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=codex_idle_capture(ctx=40), cmd="bun")
    sup = make_supervisor(
        tmp_path=tmp_path, fake=fake
    )  # `live_codex` left EMPTY: the session is gone
    marker = arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        sup._do_codex_restart(
            track=mapped_track(repo=repo, topic=topic, session=session), target=session
        )

    assert "codex session vanished before restart" in err.getvalue()
    assert session in err.getvalue()
    assert not fake.has(method="respawn")  # nothing respawned without a resolved session id
    assert marker.exists()


# --------------------------------------------------------------------------- #
# Watch-set resolution, GC fail-soft, and the post-auto-link re-join.
# --------------------------------------------------------------------------- #


def _fleet_manifest(*repo_names, tmp_path):
    """A tmp `.livespec-fleet-manifest.jsonc` naming ``repo_names`` as fleet members.

    `registry.watch_set` resolves each name against the manifest repo's PARENT, so the
    manifest lives one level down (`<tmp>/core/`) and the repos are its siblings.
    """
    core = tmp_path / "core"
    core.mkdir(exist_ok=True)
    manifest = core / ".livespec-fleet-manifest.jsonc"
    manifest.write_text(
        json.dumps({"fleet": [{"repo": name} for name in repo_names]}), encoding="utf-8"
    )
    return manifest


def test_watch_set_comes_from_the_home_declaration_when_no_repos_are_injected(*, tmp_path):
    """With no explicit `watch_repos`, the daemon watches what the `$HOME` declaration
    names — but only checkouts that EXIST and carry a `plan/` dir, so a declared repo that
    is not cloned locally is silently absent rather than a phantom watched repo.

    This is the relocation-critical path: the declaration is an ABSOLUTE `$HOME` path, so
    it resolves identically no matter where the overseer package itself lives. The
    superseded manifest seeding walked UP three directories from this file, which broke
    the instant the package moved out of `<core>/.claude/skills/`.
    """
    alpha, _ = make_plan(tmp_path=tmp_path, repo_name="alpha")
    (tmp_path / "gamma").mkdir()  # cloned, but no plan/ dir
    declaration = tmp_path / "repos.json"
    declaration.write_text(  # beta is declared but not cloned
        json.dumps(
            {
                "repos": [
                    str(tmp_path / "alpha"),
                    str(tmp_path / "beta"),
                    str(tmp_path / "gamma"),
                ]
            }
        ),
        encoding="utf-8",
    )
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), watch_set_path=str(declaration))

    assert sup._resolve_watch() == [os.path.normpath(str(alpha))]


def test_archive_gc_keeps_a_row_it_cannot_evaluate(*, tmp_path):
    """Fail-soft: a malformed mapping row (a non-string repo) cannot be evaluated for
    archival, so the GC KEEPS it rather than dropping data it does not understand."""
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    raw = json.dumps({"repo": 42, "topic": "t", "tmux": "sesA"}) + "\n"
    Path(sup.store_path).write_text(raw, encoding="utf-8")

    assert sup.archive_gc() == 0
    assert Path(sup.store_path).read_text(encoding="utf-8") == raw  # byte-identical


def test_build_rows_rejoins_after_auto_link_so_the_row_is_mapped_this_tick(*, tmp_path):
    """An auto-link MUTATES the store mid-tick, so `build_rows` must re-join afterwards.
    Without the re-join the tick would evaluate the stale pre-link snapshot and render the
    plan `unassigned` for a full interval despite having just linked its live session."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.sessions.add(session)
    fake.paths[session] = str(repo / "plan" / topic)  # cwd inside the repo → linkable
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()  # empty Claude registry: only auto-link can create the row
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={},
        starttimes={},
        watch_repos=[str(repo)],
    )

    rows = sup.build_rows(act=True)

    assert [(r.topic, r.tmux) for r in rows] == [(topic, session)]
    assert not rows[0].is_unassigned  # the re-joined row, not the stale unassigned one


def test_codex_track_is_rejected_when_its_live_session_runs_outside_the_repo(*, tmp_path):
    """`_is_codex_track` pins BOTH the (tmux, topic) key AND the repo. A live codex
    session named for this topic but running in a DIFFERENT repo is not this track's
    session, so no codex act (wrap-up, `codex resume` restart) may be aimed at it."""
    repo, topic = make_plan(tmp_path=tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=codex_idle_capture(ctx=40), cmd="bun")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=4242,
            name=topic,
            cwd=str(elsewhere),  # the ONE thing that differs
            session_id="019f6a1e-266d-7fc2-8eb2-15ec9d324fb8",
        )
    }

    assert (
        sup._is_codex_track(session=session, repo=str(repo), topic=topic, target=session) is False
    )
