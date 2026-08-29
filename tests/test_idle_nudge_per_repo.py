"""The per-repo `idle_nudge` override and the completed three-tier precedence
(`overseer-4l5iph.3`).

Slice C of the idle-nudge configurability epic, and the last one. Slice A gave the daemon
ONE resolution function (`_supervisor_idle_nudge_policy.resolve_idle_nudge`) plus a
daemon-wide default; slice B added the per-track override that wins over it; this slice
adds the tier BETWEEN them — an override declared beside a checkout in the watch-set
(`~/.livespec-overseer-repos.json`) — so an operator can quiet a whole repo without
touching either the daemon flag or every track's mapping row.

Four things this file pins, in the order they matter:

  * BACKWARD COMPATIBILITY FIRST — a `repos[]` entry is EITHER the bare path string every
    existing fleet declaration is written in, OR an object `{"path": …, "idle_nudge": …}`.
    Both are admitted side by side in one document, so the object form is purely additive
    and no operator file has to change to keep working.
  * PRECEDENCE — per-track (if set), then per-repo (if the entry sets one), then the
    daemon-wide default, resolved in the ONE seam. The headline cases are real-shape
    controls: otherwise-identical tracks idling above threshold past the 1-hour floor,
    differing only in which tier declares something.
  * THREE STATES, NOT TWO — a bare-string entry and an object without the key are both
    "no override", never "off". That is what keeps the daemon-wide flag meaningful for
    every repo an operator has not spoken about.
  * THE BOUNDARY — the low-context wrap-up and the cardinal-rule restart-on-`ready` gain
    no off-switch at this tier either, exactly as they gained none at the other two.
"""

import dataclasses
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "overseer"))

import _supervisor_config
import _supervisor_idle_nudge_policy
import registry
from test_supervisor_builders import (
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    nudge_count,
    wrapup_count,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _write_watch_set(*, tmp_path, entries) -> Path:
    """A real `~/.livespec-overseer-repos.json`, written in the operator's own shape.

    Every control below goes through this rather than through an injected override map,
    because the whole point of the slice is that the declaration is a hand-edited file:
    a fixture that skipped the parser would prove the precedence and none of the shape.
    """
    declaration = tmp_path / "repos.json"
    declaration.write_text(json.dumps({"repos": entries}), encoding="utf-8")
    return declaration


def _repo_entry(*, repo, idle_nudge=None) -> object:
    if idle_nudge is None:
        return str(repo)
    return {"path": str(repo), "idle_nudge": idle_nudge}


def _resolved(*, tmp_path, per_track, per_repo, daemon_default):
    """The effective decision for ONE track, with all three tiers set as an operator
    would set them: the daemon flag on the `Supervisor`, the per-repo override in a real
    watch-set document the supervisor is pointed at, and the per-track field on the row."""
    repo, topic = make_plan(tmp_path=tmp_path)
    declaration = _write_watch_set(
        tmp_path=tmp_path, entries=[_repo_entry(repo=repo, idle_nudge=per_repo)]
    )
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=FakeTmux(),
        idle_nudge=daemon_default,
        watch_set_path=str(declaration),
    )
    track = dataclasses.replace(
        mapped_track(repo=repo, topic=topic, session="s"), idle_nudge=per_track
    )
    return _supervisor_idle_nudge_policy.resolve_idle_nudge(sup=sup, track=track)


@pytest.mark.parametrize(
    ("per_track", "per_repo", "daemon_default", "expected"),
    [
        # The tier this slice adds, in both directions, with nothing more specific set.
        pytest.param(None, False, True, False, id="per-repo-off-beats-daemon-on"),
        pytest.param(None, True, False, True, id="per-repo-on-beats-daemon-off"),
        # The per-track field still wins over the per-repo one, in both directions.
        pytest.param(False, True, True, False, id="per-track-off-beats-per-repo-on"),
        pytest.param(True, False, False, True, id="per-track-on-beats-per-repo-off"),
        # A repo that declares nothing is silent, not "off": the daemon flag still decides.
        pytest.param(None, None, True, True, id="no-override-inherits-daemon-on"),
        pytest.param(None, None, False, False, id="no-override-inherits-daemon-off"),
    ],
)
def test_a_per_repo_override_sits_between_the_per_track_field_and_the_daemon_default(
    *, tmp_path, per_track, per_repo, daemon_default, expected
):
    """The whole three-tier chain slice C completes, resolved in the ONE seam: the most
    specific tier that says anything decides, and a tier that says nothing defers."""
    assert (
        _resolved(
            tmp_path=tmp_path,
            per_track=per_track,
            per_repo=per_repo,
            daemon_default=daemon_default,
        )
        is expected
    )


def _idling_past_the_floor(*, tmp_path, per_track=None, per_repo=None, daemon_default=True):
    """A track idling at an empty prompt well ABOVE the wind-down threshold, ticked once to
    stamp `idle_since` and then advanced past the 1-hour `IDLE_NUDGE_AFTER` floor — so the
    ONLY thing left standing between it and a keep-going nudge is the tier under test.

    Each call builds its own root, so two of these side by side are genuinely separate
    repos, stores and stamp sidecars — which is what makes a twin a control rather than
    one track observed twice."""
    root = tmp_path / f"t{len(list(tmp_path.iterdir()))}"
    root.mkdir()
    repo, topic = make_plan(tmp_path=root)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    declaration = _write_watch_set(
        tmp_path=root, entries=[_repo_entry(repo=repo, idle_nudge=per_repo)]
    )
    sup = make_supervisor(
        tmp_path=root,
        fake=fake,
        now=lambda: clock["t"],
        idle_nudge=daemon_default,
        watch_set_path=str(declaration),
    )
    sup.claude_status_by_session = {session: "idle"}
    track = dataclasses.replace(
        mapped_track(repo=repo, topic=topic, session=session), idle_nudge=per_track
    )
    sup.evaluate(track=track, act=True)
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    return sup, fake, track


def test_a_per_repo_off_quiets_a_track_that_declares_nothing_while_its_twin_is_nudged(*, tmp_path):
    """The acceptance criterion's headline control, end to end: the SAME fixture, the same
    daemon-wide `on`, the same idle-past-the-floor pane, neither track carrying a per-track
    override — and the only difference between the one that gets the single-shot nudge and
    the one that gets none is the `idle_nudge` beside its checkout in the watch-set."""
    loud_sup, loud_fake, loud = _idling_past_the_floor(tmp_path=tmp_path)
    assert loud_sup.evaluate(track=loud, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=loud_fake) == 1

    quiet_sup, quiet_fake, quiet = _idling_past_the_floor(tmp_path=tmp_path, per_repo=False)
    # The row stays descriptive — the deferred "idle-nudge-suppressed" label is out of
    # scope, and silence with the same status is what the plan's scope event settled for.
    assert quiet_sup.evaluate(track=quiet, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=quiet_fake) == 0
    assert wrapup_count(fake=quiet_fake) == 0


def test_a_per_track_override_still_wins_over_the_per_repo_value_end_to_end(*, tmp_path):
    """The inverse control at the keystroke, not just at the seam: an operator who quieted a
    whole repo can still opt ONE track back in, and one who left a repo loud can still quiet
    a single track inside it."""
    opted_in_sup, opted_in_fake, opted_in = _idling_past_the_floor(
        tmp_path=tmp_path, per_track=True, per_repo=False
    )
    assert opted_in_sup.evaluate(track=opted_in, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=opted_in_fake) == 1

    opted_out_sup, opted_out_fake, opted_out = _idling_past_the_floor(
        tmp_path=tmp_path, per_track=False, per_repo=True
    )
    assert opted_out_sup.evaluate(track=opted_out, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=opted_out_fake) == 0


def test_the_daemon_wide_flag_alone_governs_a_track_with_neither_override(*, tmp_path):
    """The third control the acceptance criterion asks for: with the repo listed as a bare
    string and the row carrying no field, the daemon flag is still the whole answer — which
    is what makes slices A and B's behaviour survive this one unchanged."""
    on_sup, on_fake, on_track = _idling_past_the_floor(tmp_path=tmp_path, daemon_default=True)
    assert on_sup.evaluate(track=on_track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=on_fake) == 1

    off_sup, off_fake, off_track = _idling_past_the_floor(tmp_path=tmp_path, daemon_default=False)
    assert off_sup.evaluate(track=off_track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=off_fake) == 0


def test_a_bare_string_watch_set_keeps_working_and_declares_no_override(*, tmp_path):
    """BACKWARD COMPATIBILITY, stated as a fixture rather than as a promise: a declaration
    written entirely in the original bare-string shape — the shape every repos.json on the
    fleet is in today — still yields exactly the same watch set, and yields NO per-repo
    overrides, so every track in it falls through to the tiers that already existed."""
    alpha, _ = make_plan(tmp_path=tmp_path, repo_name="alpha")
    beta, _ = make_plan(tmp_path=tmp_path, repo_name="beta")
    declaration = _write_watch_set(tmp_path=tmp_path, entries=[str(alpha), str(beta)])

    assert registry.watch_set_from_config(config_path=declaration) == [
        registry.norm(repo=alpha),
        registry.norm(repo=beta),
    ]
    assert registry.repo_idle_nudge_from_config(config_path=declaration) == {}


def test_object_entries_are_watched_exactly_as_bare_strings_are(*, tmp_path):
    """The object form is a spelling of the same entry, not a second kind of entry: it is
    admitted by the same exists-and-has-a-`plan/`-dir rule, in declaration order, mixed
    freely with bare strings in one document."""
    alpha, _ = make_plan(tmp_path=tmp_path, repo_name="alpha")
    beta, _ = make_plan(tmp_path=tmp_path, repo_name="beta")
    gamma = tmp_path / "gamma"  # declared but never cloned — admission still refuses it
    declaration = _write_watch_set(
        tmp_path=tmp_path,
        entries=[
            {"path": str(alpha), "idle_nudge": False},
            str(beta),
            {"path": str(gamma), "idle_nudge": False},
        ],
    )

    assert registry.watch_set_from_config(config_path=declaration) == [
        registry.norm(repo=alpha),
        registry.norm(repo=beta),
    ]
    assert registry.repo_idle_nudge_from_config(config_path=declaration) == {
        registry.norm(repo=alpha): False,
        # `gamma` is unwatched but still DECLARED: the map records what the operator said
        # about a repo, and admission decides separately what gets supervised.
        registry.norm(repo=gamma): False,
    }


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param({"path": "/repo"}, id="object-without-the-key"),
        pytest.param({"path": "/repo", "idle_nudge": "off"}, id="string-instead-of-a-bool"),
        pytest.param({"path": "/repo", "idle_nudge": None}, id="explicit-null"),
        pytest.param("/repo", id="bare-string"),
    ],
)
def test_an_entry_that_does_not_carry_a_bool_declares_no_override(*, tmp_path, entry):
    """THREE STATES, NOT TWO, one tier down from `idle_nudge_from_row`: an override exists
    only when the key holds a bool. Anything else means "this repo says nothing", so the
    per-track field and then the daemon-wide default still decide — never "off"."""
    declaration = _write_watch_set(tmp_path=tmp_path, entries=[entry])
    assert registry.repo_idle_nudge_from_config(config_path=declaration) == {}


@pytest.mark.parametrize(
    "entries",
    [
        pytest.param([17], id="a-number"),
        pytest.param([{"idle_nudge": False}], id="an-object-with-no-path"),
        pytest.param([{"path": 17, "idle_nudge": False}], id="a-non-string-path"),
    ],
)
def test_an_unrecognizable_entry_is_dropped_from_both_readings(*, tmp_path, entries):
    """Fail-soft in the shape the rest of the module already is: a hand-edited file that
    says something meaningless about one repo loses that repo, not the daemon."""
    declaration = _write_watch_set(tmp_path=tmp_path, entries=entries)
    assert registry.watch_set_from_config(config_path=declaration) == []
    assert registry.repo_idle_nudge_from_config(config_path=declaration) == {}


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("{not json", id="malformed"),
        pytest.param('{"repos": "not-a-list"}', id="repos-is-not-a-list"),
        pytest.param("[]", id="document-is-not-an-object"),
    ],
)
def test_an_unusable_declaration_yields_no_overrides_and_reports_nothing(*, tmp_path, text, capsys):
    """`watch_set_from_config` owns the operator-facing diagnostic for this file and runs
    every tick; the override reader reads the SAME document on the SAME tick, so it stays
    silent. A second `warn` here would double-log every malformed declaration."""
    declaration = tmp_path / "repos.json"
    declaration.write_text(text, encoding="utf-8")
    _ = capsys.readouterr()

    assert registry.repo_idle_nudge_from_config(config_path=declaration) == {}
    assert capsys.readouterr().err == ""


def test_an_absent_declaration_yields_no_overrides(*, tmp_path):
    """The ordinary first-run state, and the one a supervisor with no watch-set path is in:
    nothing declared means no overrides, which is "inherit", not "off"."""
    assert registry.repo_idle_nudge_from_config(config_path=tmp_path / "nope.json") == {}


def test_a_supervisor_with_no_watch_set_path_falls_through_to_the_daemon_default(*, tmp_path):
    """The beside-tests inject `watch_repos` directly and never declare a watch-set file;
    so does the extra-repos-only path. With no document to read there is nothing to
    override, and the two pre-existing tiers answer exactly as they did before slice C."""
    repo, topic = make_plan(tmp_path=tmp_path)
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux(), idle_nudge=True)
    assert sup.watch_set_path is None
    track = mapped_track(repo=repo, topic=topic, session="s")
    assert _supervisor_idle_nudge_policy.resolve_idle_nudge(sup=sup, track=track) is True


def test_the_first_declaration_of_a_repo_wins(*, tmp_path):
    """A repo named twice resolves once, and to its FIRST entry — matching the watch-set's
    own de-duplication, so the two readings of one document never disagree about which
    entry a duplicated repo actually is."""
    repo, _ = make_plan(tmp_path=tmp_path)
    declaration = _write_watch_set(
        tmp_path=tmp_path,
        entries=[
            {"path": str(repo), "idle_nudge": False},
            {"path": str(repo), "idle_nudge": True},
        ],
    )
    assert registry.watch_set_from_config(config_path=declaration) == [registry.norm(repo=repo)]
    assert registry.repo_idle_nudge_from_config(config_path=declaration) == {
        registry.norm(repo=repo): False
    }


def test_a_per_repo_off_still_wraps_up_a_track_below_the_threshold(*, tmp_path):
    """OUT OF SCOPE stays out of scope at the third tier too: the per-repo override reaches
    the keep-going nudge and nothing else. A track at 40% against the default 50% threshold
    is warned and wound up even though its whole repo says "never nudge" — the low-context
    path has no off-switch at ANY tier, which is the promise slice A made daemon-wide."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    declaration = _write_watch_set(
        tmp_path=tmp_path, entries=[{"path": str(repo), "idle_nudge": False}]
    )
    sup = make_supervisor(
        tmp_path=tmp_path, fake=fake, idle_nudge=True, watch_set_path=str(declaration)
    )
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "warned"
    assert wrapup_count(fake=fake) == 1
    assert nudge_count(fake=fake) == 0
