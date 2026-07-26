"""Integration-tier scenario tests: discovery, relay, the nudge, and the probe.

Top-of-pyramid evidence for the five `## Scenario:` headings of
SPECIFICATION/scenarios.md that cover what the daemon does with a track it is NOT
winding down — how a `blocked:` declaration reaches the operator, how an idle
session with room left is nudged, what a plan with no session is allowed to
become, what the supervision probe may touch, and how a session name is derived
when two repositories share a topic.

Three of these are DISCOVERY-level, so they drive `tick()` over real plan
directories on disk rather than calling `evaluate` on a hand-built track. That is
the difference that matters here: the collision set, the unassigned row and the
auto-link are all computed FROM the discovery pass, so a test that hands the
Supervisor a pre-made Track would assert on its own setup.

Tier: `tests.integration` is one of the documented default `scenario_tiers`
prefixes, so `check-heading-coverage` direction 4 accepts these node ids without
this repo having to declare `scenario_tiers` in `pyproject.toml`.

The harness (`FakeTmux`, `make_supervisor`, `make_plan`, `declare`) is imported from the
beside-test module that owns it rather than duplicated — a second FakeTmux would
be a second thing to keep true.
"""

from __future__ import annotations

import contextlib
import io as _io
from pathlib import Path

from overseer import registry, signals, supervisor
from overseer.test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    nudge_count,
    wrapup_count,
)
from overseer.test_supervisor_fakes import (
    FakeTmux,
)

_HANDOFF = "supervisor-handoff.md"


def _plan(repo: Path, topic: str) -> None:
    """A second plan directory inside an existing repo (`make_plan` builds the first)."""
    plan = repo / "plan" / topic
    plan.mkdir(parents=True)
    (plan / "handoff.md").write_text("h\n")


@contextlib.contextmanager
def _watch_handoff_access():
    """Instrument `pathlib.Path`, yielding the basename of every existence test performed.

    `open` / `read_text` / `read_bytes` RAISE for the supervisor-handoff file — a read is a
    hard failure at the moment it happens rather than a subtly wrong assertion afterwards,
    which matters because "did not read a file" leaves no trace in a result. Those patches
    are scoped to that one basename so the rest of the daemon's file work is untouched.

    `exists` is recorded UNFILTERED, deliberately. Logging only the handoff file would make
    an empty log ambiguous between "the daemon skipped this probe" and "the daemon did no
    file work at all"; recording every basename lets the caller assert the handoff file is
    ABSENT from a log that still shows the daemon probing other things.

    Everything is restored in a `finally`, so a failing assertion cannot leak a patched
    `Path` into the next test.
    """
    originals = {
        name: getattr(Path, name) for name in ("exists", "open", "read_text", "read_bytes")
    }
    probes: list[str] = []

    def counting_exists(self, *args, **kwargs):
        probes.append(self.name)
        return originals["exists"](self, *args, **kwargs)

    def forbid(verb: str):
        original = originals[verb]

        def guard(self, *args, **kwargs):
            assert self.name != _HANDOFF, f"the probe must never {verb} {self}"
            return original(self, *args, **kwargs)

        return guard

    Path.exists = counting_exists
    for verb in ("open", "read_text", "read_bytes"):
        setattr(Path, verb, forbid(verb))
    try:
        yield probes
    finally:
        for name, original in originals.items():
            setattr(Path, name, original)


def test_scenario_a_blocked_declaration_is_relayed_not_answered(tmp_path):
    """Scenario: A blocked declaration is relayed, not answered.

    Given a session that wrote `blocked` with a one-line reason: the track is relayed to the
    operator as non-blocking TEXT, the alert names the topic, repository, session, pane and
    a jump command, and the session is never keystroked and never restarted while blocked.

    The pane is put deep in the danger band on purpose. At 13% remaining an undeclared track
    would be pasted a wrap-up and reported as NOT RESPONDING, so the `blocked:` declaration
    has to WIN a precedence contest rather than merely be the only thing happening. A test
    run above the threshold would pass even if `blocked` were checked last.

    "Relayed, not answered" is asserted twice over: the reason reaches the operator, and it
    reaches them as stderr text with no `AskUserQuestion` and no keystroke into the pane —
    the daemon must never raise a modal on a track's behalf, because that decision is
    already displayed in the track's own pane and belongs to the operator there.

    INJECTED DEFECTS THAT REDDEN IT (run 2026-07-26, each reverted):
      - the gate branch's `or blocked is not None` disjunct removed, demoting `blocked`
        below the threshold branch -> the track reads `danger`, gets a wrap-up pasted, and
        is reported as having declared NOTHING.
      - `_alert` reduced to `repo::topic` text -> the session/pane/jump assertions.
    """
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=13))  # deep in the danger band
    sup = make_supervisor(tmp_path, fake, out=_io.StringIO())
    declare(repo, topic, "blocked: waiting on the schema call")

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)

    assert view.status == "blocked:human"  # ...it outranks the danger band
    assert view.note == "waiting on the schema call"

    report = err.getvalue()
    assert "waiting on the schema call" in report  # the reason itself is relayed
    for coordinate in (topic, registry.repo_slug(str(repo)), session):
        assert coordinate in report
    assert f"tmux switch-client -t {session}" in report

    assert not fake.has("paste")  # never keystroked...
    assert not fake.has("keys")
    assert not fake.has("respawn")  # ...and never restarted while blocked


def test_scenario_an_idle_session_with_context_left_is_nudged_once_per_episode(tmp_path):
    """Scenario: An idle session with context left is nudged once per episode.

    Walks the whole episode lifecycle on one track: below the one-hour floor nothing is
    keystroked; past it exactly one keep-going message is pasted and the daemon records its
    OWN marker in the state file; a further idle tick does not nudge again; the session
    working clears the marker; and a fresh hour of idleness earns a second nudge.

    Two details are load-bearing and easy to lose:

    - The nudge is asserted as a NUDGE, not merely as "a paste". The wrap-up and the
      keep-going message travel the same bracketed-paste path, and they mean opposite
      things — one says stop, the other says continue. `wrapup_count` staying at zero is
      what makes this a nudge test rather than a paste test.
    - The marker is the daemon's ONLY self-authored token, and it must never look like a
      session declaration. It is checked by token, so a marker written as `ready` would
      redden here rather than silently arming a restart.

    INJECTED DEFECTS THAT REDDEN IT (run 2026-07-26, each reverted):
      - `_IDLE_NUDGE_AFTER = 0.0` -> the too-soon assertion fires on the first tick.
      - the `nudged_already` guard dropped -> the same episode nudges twice.
      - `_clear_idle_nudge_state` made a no-op -> the marker survives the working tick and
        the second episode never re-arms.
    """
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))  # well ABOVE the threshold
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path, fake, now=lambda: clock["t"], out=_io.StringIO())
    sup._claude_status = {session: "idle"}  # not `waiting`: free to continue
    track = mapped_track(repo, topic, session)

    assert sup.evaluate(track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake) == 0  # descriptive status, but idle < 1h: NOT keystroked
    assert signals.read_state(str(repo), topic) is None

    clock["t"] += supervisor._IDLE_NUDGE_AFTER + 1
    assert sup.evaluate(track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake) == 1  # ONE keep-going message...
    assert wrapup_count(fake) == 0  # ...and emphatically not a wind-down wrap-up
    marker = signals.read_state(str(repo), topic)
    assert marker is not None and marker.token == signals.STATE_IDLE_WITH_CONTEXT_LEFT

    clock["t"] += supervisor._IDLE_NUDGE_AFTER + 1
    sup.evaluate(track, act=True)
    assert nudge_count(fake) == 1  # same episode: not nudged again

    sup._claude_status = {session: "busy"}  # the session works again
    assert sup.evaluate(track, act=True).status == "working"
    assert signals.read_state(str(repo), topic) is None  # the marker clears...

    sup._claude_status = {session: "idle"}
    sup.evaluate(track, act=True)
    assert nudge_count(fake) == 1  # ...re-arming a FUTURE episode, not an immediate one
    clock["t"] += supervisor._IDLE_NUDGE_AFTER + 1
    sup.evaluate(track, act=True)
    assert nudge_count(fake) == 2


def test_scenario_an_unassigned_plan_is_discovered_but_never_auto_started(tmp_path):
    """Scenario: An unassigned plan is discovered but never auto-started.

    Given a watched repository containing a plan directory with no assigned session, the
    plan appears as `unassigned` and the daemon never launches a session for it.

    This runs `tick(act=True)` — the ACTING path, which is the only one where the claim has
    any content. `tick(act=False)` cannot launch anything by construction, so asserting
    surface-only behavior there would be vacuous.

    Ten ticks, not one. "Never auto-started" is a claim about a daemon that observes the
    same startable plan forever; a single observation cannot distinguish "never launches"
    from "launches on the second look".

    INJECTED DEFECT THAT REDDENS IT (run 2026-07-26, reverted): making `auto_link` create
    the session it looks for (`new_session` when `session_exists` is False) starts a session
    for a plan nobody asked to start, and the row stops reading `unassigned`.
    """
    repo, _topic = make_plan(tmp_path, topic="startable")
    fake = FakeTmux()  # NO session serves this plan
    sup = make_supervisor(tmp_path, fake, watch_repos=[str(repo)], out=_io.StringIO())

    for _ in range(10):  # a daemon looks at a startable plan over and over
        views = sup.tick(act=True)

    row = next(view for view in views if view.topic == "startable")
    assert row.status == "unassigned"
    assert row.tmux is None
    assert not fake.has("new")  # no session was created for it...
    assert not fake.has("respawn")  # ...by either launch mechanism
    assert registry.read_mapping(sup.store_path) == []  # and nothing was mapped


def test_scenario_the_supervision_probe_is_liveness_gated_and_existence_only(tmp_path):
    """Scenario: The supervision-artifact existence probe is liveness-gated and existence-only.

    The probe MAY test whether `plan/<topic>/supervisor-handoff.md` exists; it never opens,
    reads, or hashes it; and for a track with no live matching session it performs no
    file-level probe at all.

    The two negative clauses are asserted by INSTRUMENTING `pathlib.Path` rather than by
    inspecting the daemon's output, because "did not read a file" leaves no trace in a
    result: `open` / `read_text` / `read_bytes` raise on that filename, so any read is a hard
    failure at the moment it happens rather than a subtly wrong assertion afterwards.

    The liveness gate is exercised by DIFFERENCE, on the same repo and the same file: the
    live-session pass must probe it and the dead-session pass must not. Asserting only the
    absence would pass against a daemon that never probes at all, which is a different bug
    wearing the same green tick.

    INJECTED DEFECTS THAT REDDEN IT (run 2026-07-26, each reverted):
      - `_surface_supervision_offer` reading the file (`.read_text()`) instead of `.exists()`
        -> the patched reader raises.
      - the probe hoisted above the no-managed-pane return in `evaluate` -> the dead-session
        pass probes, so its count is no longer zero.
    """
    repo, topic = make_plan(tmp_path)
    (repo / "plan" / topic / _HANDOFF).write_text("a supervisor charter\n")
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path, fake, out=_io.StringIO())
    track = mapped_track(repo, topic, session)

    with _watch_handoff_access() as probes, contextlib.redirect_stderr(_io.StringIO()):
        live = sup.evaluate(track, act=True)  # a live, matching session
        live_probes = list(probes)

        probes.clear()
        fake.sessions.clear()  # the session goes away entirely
        dead = sup.evaluate(track, act=True)
        dead_probes = list(probes)

    assert live.status == "idle-with-context-left"  # a live tracked pane...
    assert _HANDOFF in live_probes  # ...MAY be probed for existence
    assert dead.status == "session-gone"  # no live matching session...
    assert _HANDOFF not in dead_probes  # ...means no file-level probe at all


def test_scenario_topics_colliding_across_repositories_get_qualified_session_names(tmp_path):
    """Scenario: Topics colliding across repositories get qualified session names.

    Given two watched repositories that both contain the same plan topic, a derived session
    name is qualified with the repository slug and a SINGLE dash; a topic unique to one
    repository keeps its bare name.

    Asserted through `auto_link`, not through `registry.tmux_id`. The unit-tier tests
    already pin the naming function; what has never been pinned above them is that the
    daemon computes the collision set from the DISCOVERY pass and then derives names with
    it. So the test lays out real plan directories, serves tmux sessions under both the
    qualified and the bare name, and lets `tick` decide which one it recognizes — the
    linking behavior is the observable consequence of the rule.

    Serving the bare `shared` session alongside the qualified one is the part that gives
    this teeth: a daemon that ignored the collision set would find that bare session,
    match its cwd, and link it. It must instead walk past it.

    The single dash is checked literally. `<slug>--<topic>` is the RETIRED form, and a
    double dash would still "contain the slug and the topic" — so a substring assertion
    would accept the regression this clause exists to prevent.

    INJECTED DEFECT THAT REDDENS IT (run 2026-07-26, reverted): `colliding_topics` returning
    an empty frozenset makes both repos derive the bare `shared`, so the qualified sessions
    are never linked and the bare one is claimed by whichever repo is discovered first.
    """
    alpha, _ = make_plan(tmp_path, repo_name="alpha", topic="shared")
    beta, _ = make_plan(tmp_path, repo_name="beta", topic="shared")
    _plan(beta, "solo")  # a topic unique to ONE repo

    fake = FakeTmux()
    fake.serve("alpha-shared", alpha, capture=idle_capture(ctx=73))
    fake.serve("beta-shared", beta, capture=idle_capture(ctx=73))
    fake.serve("solo", beta, capture=idle_capture(ctx=73))
    fake.serve("shared", alpha, capture=idle_capture(ctx=73))  # the RETIRED bare name
    sup = make_supervisor(tmp_path, fake, watch_repos=[str(alpha), str(beta)], out=_io.StringIO())

    with contextlib.redirect_stderr(_io.StringIO()):
        _ = sup.tick(act=True)

    linked = {(row.repo, row.topic): row.tmux for row in registry.read_mapping(sup.store_path)}
    assert linked[(str(alpha), "shared")] == "alpha-shared"  # qualified, SINGLE dash
    assert linked[(str(beta), "shared")] == "beta-shared"
    assert linked[(str(beta), "solo")] == "solo"  # unique topic keeps its bare name
    assert "shared" not in linked.values()  # the bare colliding session was NOT claimed
    assert "alpha--shared" not in linked.values()  # ...and the retired double dash is gone
