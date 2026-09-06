"""A SQUATTED tmux name is not an absent session (`overseer-5p6d6g`).

The defect: a track whose tmux NAME is held by a live pane working in a DIFFERENT repo
reported the same plain `session-gone` as a track with no session at all. The row was
accurate and unreadable — the two cases point at opposite remedies, and the ambiguous
reading points at the destructive one. A seat read the measured row as "our session,
drifted cwd" and asked the foreign session to wind down and declare `ready` so it could
be "restarted correctly seated in this repo". Both halves would have broken it: a
project skill does not resolve outside its own project, and that pane declaring `ready`
would have written a state file for a topic it does not own. Only the session's own
refusal stopped it, and the next reader will not necessarily refuse.

**The fixture is the MEASURED shape** (filed 2026-08-21T23:10:23Z): topic
`caam-anthropic-loop`, tracked for `/data/projects/livespec-overseer`, with a live pane
of exactly that tmux name whose cwd is `/data/projects/vps-info`. The absolute prefixes
are re-rooted under `tmp_path` so the suite stays hermetic; `signals.path_in_repo` is a
pure path-prefix comparison with no filesystem access, so re-rooting changes nothing the
discriminator reads. The topic name, both repo basenames and the collision itself are
the measured ones.

**Re-measured on the operator host 2026-08-23T11:49:09Z, and the live instance is GONE:**
the foreign session was renamed `caam-anthropic-loop-legacy`, so the topic name now
resolves to a pane in its own repo. That is an ENVIRONMENT change, not a fix — nothing
in the daemon changed, and the next accidental collision reproduces the same row. So
this builds the FILED shape rather than today's cured one, and two of the controls below
are exactly the cured shapes that must NOT trip the discriminator.

Re-measured again at implementation time, 2026-09-06, and the finding is recorded rather
than assumed: this is a sandboxed factory clone with no operator host reachable, so no
live tmux reading was possible here. The acceptance evidence for "which case was
observed" is therefore the 2026-08-23 host reading above — the CURED state, foreign
session renamed out of the way — carried forward unchanged, not a fresh claim.
"""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "overseer"))

import registry
import supervisor
from test_supervisor_builders import (
    adopt_sup,
    make_plan,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

# The measured topic. It is also the tmux session name: `registry.tmux_id` prefixes the
# repo slug ONLY on a genuine cross-repo topic collision, and there is none here.
TOPIC = "caam-anthropic-loop"

MODULE_PATH = Path(__file__).resolve().parents[1] / "overseer" / "_supervisor_name_collision.py"


def measured_repos(*, tmp_path):
    """`(tracked, foreign)` — the two repos of the measured collision, re-rooted."""
    projects = tmp_path / "data" / "projects"
    tracked, _topic = make_plan(tmp_path=projects, repo_name="livespec-overseer", topic=TOPIC)
    foreign = projects / "vps-info"
    foreign.mkdir(parents=True)
    return tracked, foreign


def collision_supervisor(*, tmp_path, fake):
    """A supervisor with hermetic session discovery: no live Claude registry at all.

    That keeps the two softeners ahead of the discriminator (`live-outside-tmux` and
    `live-name-mismatch`) out of the way, so each test reads the leg it is about.
    """
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    return adopt_sup(
        tmp_path=tmp_path, fake=fake, sessions_dir=sessions_dir, ppid={}, starttimes={}
    )


def test_a_foreign_repos_pane_holding_the_topics_tmux_name_is_not_a_plain_absent_session(
    *, tmp_path
):
    """THE COLLISION CASE. The name is taken by a pane in another repo, and the row says so."""
    assert MODULE_PATH.is_file()
    module = importlib.import_module("_supervisor_name_collision")

    tracked, foreign = measured_repos(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(tracked), topic=TOPIC)
    assert session == TOPIC  # the collision is on the bare topic name
    fake = FakeTmux()
    fake.serve(session=session, repo=foreign)  # a live pane — but its cwd is the OTHER repo
    sup = collision_supervisor(tmp_path=tmp_path, fake=fake)

    view = sup.evaluate(track=mapped_track(repo=tracked, topic=TOPIC, session=session), act=True)

    assert view.status != "session-gone"  # the defect: it used to collapse to this
    assert view.status == module.NAME_COLLISION_STATUS
    assert view.note is not None
    assert str(foreign) in view.note  # the reader is told WHERE the holder is working
    assert view.tmux is None  # no session of OURS is in that tmux
    # It wants a human — the operator decides whether to rename, or to start elsewhere.
    assert supervisor.needs_attention(row=view) is True


def test_the_same_topic_with_no_pane_of_that_name_at_all_still_reads_session_gone(*, tmp_path):
    """THE NEGATIVE CONTROL. Without this leg the discriminator could not disagree, which
    is a shape this repo has already burned a day on (`overseer-of2y63`)."""
    tracked, _foreign = measured_repos(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(tracked), topic=TOPIC)
    fake = FakeTmux()  # no tmux session of that name exists at all
    sup = collision_supervisor(tmp_path=tmp_path, fake=fake)

    view = sup.evaluate(track=mapped_track(repo=tracked, topic=TOPIC, session=session), act=True)

    assert view.status == "session-gone"


def test_a_near_miss_neighbour_of_the_topic_name_is_not_read_as_a_collision(*, tmp_path):
    """The SECOND control, and the trap the 2026-08-23 re-measurement named: the host today
    holds `caam-anthropic-loop-legacy` in the foreign repo. A discriminator keyed on a
    prefix or a substring rather than the exact session name would call that a squat."""
    tracked, foreign = measured_repos(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(tracked), topic=TOPIC)
    fake = FakeTmux()
    fake.serve(session=f"{session}-legacy", repo=foreign)  # a NEAR-MISS, not the name
    sup = collision_supervisor(tmp_path=tmp_path, fake=fake)

    view = sup.evaluate(track=mapped_track(repo=tracked, topic=TOPIC, session=session), act=True)

    assert view.status == "session-gone"


def test_a_session_of_that_name_with_no_resolvable_pane_stays_session_gone(*, tmp_path):
    """The THIRD control, and the discriminator's fail-closed edge: a tmux session of the
    topic's name exists but resolves to NO pane, so there is no cwd to compare and nothing
    that could prove a squat. It reports the plain absence rather than guessing at one."""
    tracked, _foreign = measured_repos(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(tracked), topic=TOPIC)
    fake = FakeTmux()
    fake.sessions.add(session)
    fake.no_pane_sessions.add(session)
    sup = collision_supervisor(tmp_path=tmp_path, fake=fake)

    view = sup.evaluate(track=mapped_track(repo=tracked, topic=TOPIC, session=session), act=True)

    assert view.status == "session-gone"


def start_revalidation_inputs(*, repo, row_status):
    """A stale `plan_start` proposal and the daemon document that now disagrees with it.

    The proposal was built while a LIVE session held the row; the row now carries no
    identity at all, which is the disagreement `revalidate_start_identity` judges.
    """
    snapshot = {"daemon_instance_id": "daemon-1", "tick_generation": 7}
    document = {
        "schema_version": 1,
        "repo": str(repo),
        "sources": {"snapshot": {"status": "ok", "mode": "daemon-snapshot"}},
        "snapshot": {
            **snapshot,
            "rows": [
                {
                    "repo": str(repo),
                    "topic": TOPIC,
                    "tmux": TOPIC,
                    "runtime": "claude",
                    "status": row_status,
                    "session_identity": f"none:{repo}:{TOPIC}",
                }
            ],
        },
        "dispatch_journal": [],
    }
    proposal = {
        "schema_version": 1,
        "action_id": "plan_start",
        "repo": str(repo),
        "topic": TOPIC,
        "session_name": TOPIC,
        "snapshot": {**snapshot, "session_identity": f"claude:{repo}:{TOPIC}"},
    }
    return proposal, document


def test_a_name_collision_row_refuses_a_stale_start_as_a_changed_identity(*, tmp_path):
    """A `name-collision` row says nothing of OURS is running — exactly what `session-gone`
    says. So the foreman's start revalidation must keep refusing with
    `session_identity_changed` rather than `already_started`, which means "this track is
    already up". Without this the new status silently re-labels an existing refusal.

    The `session-gone` leg is the control: it is the behaviour being PRESERVED, not a new
    one, so a discriminator that only widened the reason for the new status would still
    have to keep it true for the old.
    """
    assert MODULE_PATH.is_file()
    revalidate = importlib.import_module("foreman_act_revalidate")
    module = importlib.import_module("_supervisor_name_collision")
    repo = tmp_path / "livespec-overseer"
    repo.mkdir()

    for status in ("session-gone", module.NAME_COLLISION_STATUS):
        proposal, document = start_revalidation_inputs(repo=repo, row_status=status)
        assert (
            revalidate.revalidate_start_identity(proposal=proposal, document=document)
            == "session_identity_changed"
        ), status


def test_a_pane_of_that_name_inside_the_tracked_repo_is_not_a_collision(*, tmp_path):
    """THE FOURTH control — the CURED state the host reached by renaming. A pane of the
    topic's name sitting in the track's OWN repo is an ordinary no-managed-pane case (our
    session exited to a shell, say), never a name held by something else."""
    tracked, _foreign = measured_repos(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(tracked), topic=TOPIC)
    fake = FakeTmux()
    fake.serve(session=session, repo=tracked, cmd="zsh")  # our own session, exited to a shell
    sup = collision_supervisor(tmp_path=tmp_path, fake=fake)

    view = sup.evaluate(track=mapped_track(repo=tracked, topic=TOPIC, session=session), act=True)

    assert view.status == "session-gone"
