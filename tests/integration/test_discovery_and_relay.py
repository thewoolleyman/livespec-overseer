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

from overseer import _supervisor_config, registry, signals
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
_FILE_PROBE_VERBS = ("exists", "is_file")
_FILE_READ_VERBS = ("open", "read_text", "read_bytes")


def _plan(*, repo: Path, topic: str) -> None:
    """A second plan directory inside an existing repo (`make_plan` builds the first)."""
    plan = repo / "plan" / topic
    plan.mkdir(parents=True)
    (plan / "handoff.md").write_text("h\n")


def _inside_plan_file(*, path: Path, plan_dir: Path) -> bool:
    try:
        path.relative_to(plan_dir)
    except ValueError:
        return False
    return path != plan_dir


def _guard_plan_probe(*, verb: str, original, plan_dir: Path, probes: list[str]):
    def guard(self, *args, **kwargs):
        if _inside_plan_file(path=self, plan_dir=plan_dir):
            raise AssertionError(f"discovery must never {verb} file-level path {self}")
        probes.append(f"{verb}:{self.name}")
        return original(self, *args, **kwargs)

    return guard


def _guard_plan_read(*, verb: str, original, plan_dir: Path):
    def guard(self, *args, **kwargs):
        if _inside_plan_file(path=self, plan_dir=plan_dir):
            raise AssertionError(f"discovery must never {verb} {self}")
        return original(self, *args, **kwargs)

    return guard


@contextlib.contextmanager
def _watch_plan_file_access(*, plan_dir: Path):
    """Instrument `pathlib.Path`, yielding every file-level probe inside one plan dir.

    `exists` / `is_file` / `open` / `read_text` / `read_bytes` RAISE for any file below the
    plan directory. A probe is therefore a hard failure at the moment it happens rather
    than a subtly wrong assertion afterwards, which matters because "did not read a file"
    leaves no trace in a result. Directory checks remain allowed: discovery keys on
    `plan/<topic>/` as a directory and is allowed to enumerate it.

    The yielded list records each allowed existence-style query outside the plan
    directory, so an empty failure log is not ambiguous with a patch that failed to install.

    Everything is restored in a `finally`, so a failing assertion cannot leak a patched
    `Path` into the next test.
    """
    originals = {name: getattr(Path, name) for name in (*_FILE_PROBE_VERBS, *_FILE_READ_VERBS)}
    probes: list[str] = []

    for verb in _FILE_PROBE_VERBS:
        setattr(
            Path,
            verb,
            _guard_plan_probe(
                verb=verb, original=originals[verb], plan_dir=plan_dir, probes=probes
            ),
        )
    for verb in _FILE_READ_VERBS:
        setattr(
            Path,
            verb,
            _guard_plan_read(verb=verb, original=originals[verb], plan_dir=plan_dir),
        )
    try:
        yield probes
    finally:
        for name, original in originals.items():
            setattr(Path, name, original)


@contextlib.contextmanager
def _watch_handoff_read_access():
    """Instrument `pathlib.Path`, raising on attempts to read `supervisor-handoff.md`."""
    originals = {name: getattr(Path, name) for name in ("open", "read_text", "read_bytes")}

    def forbid(*, verb: str):
        original = originals[verb]

        def guard(self, *args, **kwargs):
            assert self.name != _HANDOFF, f"the probe must never {verb} {self}"
            return original(self, *args, **kwargs)

        return guard

    for verb in ("open", "read_text", "read_bytes"):
        setattr(Path, verb, forbid(verb=verb))
    try:
        yield
    finally:
        for name, original in originals.items():
            setattr(Path, name, original)


@contextlib.contextmanager
def _record_handoff_exists():
    """Record whether evaluation still performs the separate live-session offer probe."""
    original = Path.exists
    probes: list[str] = []

    def counting_exists(self, *args, **kwargs):
        probes.append(self.name)
        return original(self, *args, **kwargs)

    Path.exists = counting_exists
    try:
        yield probes
    finally:
        Path.exists = original


def test_scenario_a_blocked_declaration_is_relayed_not_answered(*, tmp_path):
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
      - `alert` reduced to `repo::topic` text -> the session/pane/jump assertions.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=13))  # deep in the danger band
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    declare(repo=repo, topic=topic, value="blocked: waiting on the schema call")

    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "blocked:human"  # ...it outranks the danger band
    assert view.note == "0m: waiting on the schema call"

    report = err.getvalue()
    assert "waiting on the schema call" in report  # the reason itself is relayed
    for coordinate in (topic, registry.repo_slug(repo=str(repo)), session):
        assert coordinate in report
    assert f"tmux switch-client -t {session}" in report

    assert not fake.has(method="paste")  # never keystroked...
    assert not fake.has(method="keys")
    assert not fake.has(method="respawn")  # ...and never restarted while blocked


def test_scenario_an_idle_session_with_context_left_is_nudged_once_per_episode(*, tmp_path):
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
      - `IDLE_NUDGE_AFTER = 0.0` -> the too-soon assertion fires on the first tick.
      - the `nudged_already` guard dropped -> the same episode nudges twice.
      - `_clear_idle_nudge_state` made a no-op -> the marker survives the working tick and
        the second episode never re-arms.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))  # well ABOVE the threshold
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"], out=_io.StringIO())
    sup.claude_status_by_session = {session: "idle"}  # not `waiting`: free to continue
    track = mapped_track(repo=repo, topic=topic, session=session)

    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=fake) == 0  # descriptive status, but idle < 1h: NOT keystroked
    assert signals.read_state(repo=str(repo), topic=topic) is None

    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=fake) == 1  # ONE keep-going message...
    assert wrapup_count(fake=fake) == 0  # ...and emphatically not a wind-down wrap-up
    marker = signals.read_state(repo=str(repo), topic=topic)
    assert marker is not None and marker.token == signals.STATE_IDLE_WITH_CONTEXT_LEFT

    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    sup.evaluate(track=track, act=True)
    assert nudge_count(fake=fake) == 1  # same episode: not nudged again

    sup.claude_status_by_session = {session: "busy"}  # the session works again
    assert sup.evaluate(track=track, act=True).status == "working"
    assert signals.read_state(repo=str(repo), topic=topic) is None  # the marker clears...

    sup.claude_status_by_session = {session: "idle"}
    sup.evaluate(track=track, act=True)
    assert nudge_count(fake=fake) == 1  # ...re-arming a FUTURE episode, not an immediate one
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    sup.evaluate(track=track, act=True)
    assert nudge_count(fake=fake) == 2


def test_scenario_an_unassigned_plan_is_discovered_but_never_auto_started(*, tmp_path):
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
    repo, _topic = make_plan(tmp_path=tmp_path, topic="startable")
    fake = FakeTmux()  # NO session serves this plan
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)], out=_io.StringIO())

    for _ in range(10):  # a daemon looks at a startable plan over and over
        views = sup.tick(act=True)

    row = next(view for view in views if view.topic == "startable")
    assert row.status == "unassigned"
    assert row.tmux is None
    assert not fake.has(method="new")  # no session was created for it...
    assert not fake.has(method="respawn")  # ...by either launch mechanism
    assert registry.read_mapping(store_path=sup.store_path) == []  # and nothing was mapped


def test_scenario_discovery_performs_no_file_level_probe_inside_a_plan_directory(*, tmp_path):
    """Scenario: Discovery performs no file-level probe inside a plan directory.

    Given a watched repository containing a plan directory, with or without a currently
    matching live session, the daemon's discovery pass performs no file-level probe inside
    the plan directory: it does not ask whether either handoff exists and never opens,
    reads, or hashes them as authorization.

    The negative clause is asserted by INSTRUMENTING `pathlib.Path` rather than by
    inspecting the daemon's output, because "did not read a file" leaves no trace in a
    result: any file-level `exists` / `is_file` / read probe below the plan directory raises
    at the moment it happens.

    This deliberately drives `build_rows`, not full `tick`: the ratified scenario is about
    DISCOVERY, while the live-session supervision-offer surface remains a separate
    evaluation concern. The live-session half still matters, though, because `act=True`
    discovery may auto-link a matching tmux session before returning the row set.

    INJECTED DEFECTS THAT REDDEN IT (run 2026-07-26, each reverted):
      - calling `registry.epic_from_plan_anchor` from daemon discovery -> the patched
        `read_text` raises on `plan/<topic>/handoff.md`.
      - checking `supervisor-handoff.md.exists()` from discovery -> the patched `exists`
        raises on a file-level path inside the plan directory.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    plan_dir = repo / "plan" / topic
    (repo / "plan" / topic / _HANDOFF).write_text("a supervisor charter\n")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, watch_repos=[str(repo)], out=_io.StringIO())

    with _watch_plan_file_access(plan_dir=plan_dir) as probes:
        live_rows = sup.build_rows(act=True)

        fake.sessions.clear()
        dead_rows = sup.build_rows(act=True)

    assert probes  # the patch was live and observed non-plan filesystem checks
    assert [(row.topic, row.tmux) for row in live_rows] == [(topic, session)]
    assert [(row.topic, row.tmux) for row in dead_rows] == [(topic, session)]


def test_supervision_offer_probe_still_never_reads_the_handoff_file(*, tmp_path):
    """The evaluation-tier supervision offer may existence-test but never read the handoff.

    This is the surviving half of the retired scenario: it is no longer the
    integration-tier scenario binding, but it keeps the read/hash prohibition pinned on
    the offer path that still checks whether a durable supervisor prompt exists.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    (repo / "plan" / topic / _HANDOFF).write_text("a supervisor charter\n")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, out=_io.StringIO())
    track = mapped_track(repo=repo, topic=topic, session=session)

    with (
        _watch_handoff_read_access(),
        _record_handoff_exists() as probes,
        contextlib.redirect_stderr(_io.StringIO()),
    ):
        live = sup.evaluate(track=track, act=True)

    assert live.status == "idle-with-context-left"
    assert _HANDOFF in probes


def test_scenario_topics_colliding_across_repositories_get_qualified_session_names(*, tmp_path):
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
    alpha, _ = make_plan(tmp_path=tmp_path, repo_name="alpha", topic="shared")
    beta, _ = make_plan(tmp_path=tmp_path, repo_name="beta", topic="shared")
    _plan(repo=beta, topic="solo")  # a topic unique to ONE repo

    fake = FakeTmux()
    fake.serve(session="alpha-shared", repo=alpha, capture=idle_capture(ctx=73))
    fake.serve(session="beta-shared", repo=beta, capture=idle_capture(ctx=73))
    fake.serve(session="solo", repo=beta, capture=idle_capture(ctx=73))
    fake.serve(session="shared", repo=alpha, capture=idle_capture(ctx=73))  # the RETIRED bare name
    sup = make_supervisor(
        tmp_path=tmp_path, fake=fake, watch_repos=[str(alpha), str(beta)], out=_io.StringIO()
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        _ = sup.tick(act=True)

    linked = {
        (row.repo, row.topic): row.tmux for row in registry.read_mapping(store_path=sup.store_path)
    }
    assert linked[(str(alpha), "shared")] == "alpha-shared"  # qualified, SINGLE dash
    assert linked[(str(beta), "shared")] == "beta-shared"
    assert linked[(str(beta), "solo")] == "solo"  # unique topic keeps its bare name
    assert "shared" not in linked.values()  # the bare colliding session was NOT claimed
    assert "alpha--shared" not in linked.values()  # ...and the retired double dash is gone
