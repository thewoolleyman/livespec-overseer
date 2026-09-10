"""The evidence-bound dead-track runtime classifier, and the verified Codex launcher.

Both are shared by every deliberate dead-track recovery entry point, so the classifier
is exercised directly here and its consequences are exercised through the callable
`recover_missing_sessions`. The `start` surface's half lives in
`tests/test_start_dead_track_runtime.py`.

``import supervisor`` resolves via conftest.py.
"""

import dataclasses
import importlib
from pathlib import Path

import pytest
import registry
from test_supervisor_builders import (
    codex_dead_track,
    codex_home_with,
    codex_idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    verify_codex_respawn,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

SID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER_SID = "11111111-2222-3333-4444-555555555555"
MODULE_PATH = Path(__file__).resolve().parent / "_supervisor_dead_track.py"


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def dead_track_module():
    """The ONE classifier both deliberate recovery entry points must share."""
    assert MODULE_PATH.is_file(), (
        "the shared dead-track runtime classifier must live in one module, "
        f"not be re-derived per entry point: {MODULE_PATH}"
    )
    return importlib.import_module("_supervisor_dead_track")


def classify(*, track, codex_home):
    module = dead_track_module()
    return module, module.classify_dead_track(track=track, codex_home=codex_home)


# --------------------------------------------------------------------------- #
# The classifier: the recorded identity is the only evidence, corroborated only.
# --------------------------------------------------------------------------- #


def test_an_exact_recorded_codex_identity_with_an_agreeing_index_classifies_as_codex(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    home = codex_home_with(tmp_path=tmp_path, topic=topic, session_id=SID)

    module, runtime = classify(
        track=codex_dead_track(repo=repo, topic=topic, session="s", session_id=SID),
        codex_home=str(home),
    )

    assert isinstance(runtime, module.CodexRuntime)
    assert runtime.session_id == SID


def test_a_track_with_no_recorded_identity_and_no_codex_namesake_keeps_the_claude_default(
    *, tmp_path
):
    """A brand-new mapped plan is the never-launched case: the documented Claude default."""
    repo, topic = make_plan(tmp_path=tmp_path)

    module, runtime = classify(
        track=mapped_track(repo=repo, topic=topic, session="s"),
        codex_home=str(tmp_path / "no-codex-home"),
    )

    assert isinstance(runtime, module.ClaudeRuntime)


def test_a_topic_only_codex_namesake_is_ambiguous_rather_than_a_codex_guess(*, tmp_path):
    """The retired path derived the runtime from the newest same-topic index entry.

    That is the stale-namesake defect the specification names outright: a topic present in
    the global Codex index is not evidence about THIS track, so it is reported.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    home = codex_home_with(tmp_path=tmp_path, topic=topic, session_id=SID)

    module, runtime = classify(
        track=mapped_track(repo=repo, topic=topic, session="s"), codex_home=str(home)
    )

    assert isinstance(runtime, module.AmbiguousRuntime)
    assert "topic-only guess" in runtime.reason


def test_a_proven_claude_identity_outranks_a_same_topic_codex_namesake(*, tmp_path):
    """`autonomous-mode` sat in the Codex index as a six-day-old namesake of a Claude track."""
    repo, topic = make_plan(tmp_path=tmp_path)
    home = codex_home_with(tmp_path=tmp_path, topic=topic, session_id=SID)

    module, runtime = classify(
        track=dataclasses.replace(
            mapped_track(repo=repo, topic=topic, session="s"),
            observed_session_identity=f"claude:s:{topic}",
        ),
        codex_home=str(home),
    )

    assert isinstance(runtime, module.ClaudeRuntime)


def test_a_recorded_codex_id_that_is_not_a_canonical_uuid_is_ambiguous(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    home = codex_home_with(tmp_path=tmp_path, topic=topic, session_id=SID)

    module, runtime = classify(
        track=dataclasses.replace(
            mapped_track(repo=repo, topic=topic, session="s"),
            observed_session_identity="codex:not-a-uuid",
        ),
        codex_home=str(home),
    )

    assert isinstance(runtime, module.AmbiguousRuntime)
    assert "interactive picker" in runtime.reason


def test_a_recorded_codex_id_the_index_maps_to_another_topic_is_ambiguous(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    home = codex_home_with(tmp_path=tmp_path, topic="a-different-thread", session_id=SID)

    module, runtime = classify(
        track=codex_dead_track(repo=repo, topic=topic, session="s", session_id=SID),
        codex_home=str(home),
    )

    assert isinstance(runtime, module.AmbiguousRuntime)
    assert "disagree" in runtime.reason


def test_a_recorded_codex_id_with_no_surviving_rollout_is_ambiguous(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    home = codex_home_with(tmp_path=tmp_path, topic=topic, session_id=SID, rollout=False)

    module, runtime = classify(
        track=codex_dead_track(repo=repo, topic=topic, session="s", session_id=SID),
        codex_home=str(home),
    )

    assert isinstance(runtime, module.AmbiguousRuntime)
    assert "rollout for session" in runtime.reason


def test_an_unrecognized_recorded_identity_is_ambiguous(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)

    module, runtime = classify(
        track=dataclasses.replace(
            mapped_track(repo=repo, topic=topic, session="s"),
            observed_session_identity="pi:1234",
        ),
        codex_home=str(tmp_path / "no-codex-home"),
    )

    assert isinstance(runtime, module.AmbiguousRuntime)
    assert "no supported runtime" in runtime.reason


def test_an_absent_codex_home_falls_back_to_the_default_location(*, tmp_path, monkeypatch):
    """The CLI builds its Supervisor with no `codex_home`, so `None` must resolve to `~/.codex`."""
    repo, topic = make_plan(tmp_path=tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    module, runtime = classify(
        track=mapped_track(repo=repo, topic=topic, session="s"), codex_home=None
    )

    assert isinstance(runtime, module.ClaudeRuntime)


# --------------------------------------------------------------------------- #
# The callable recovery entry point uses that classifier and a VERIFIED launcher.
# --------------------------------------------------------------------------- #


def codex_recovery(*, tmp_path, rollout=True, **verify):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    sup = make_supervisor(
        tmp_path=tmp_path,
        fake=fake,
        codex_home=str(
            codex_home_with(tmp_path=tmp_path, topic=topic, session_id=SID, rollout=rollout)
        ),
    )
    registry.append_mapping(
        track=codex_dead_track(repo=repo, topic=topic, session=session, session_id=SID),
        store_path=sup.store_path,
    )
    verify_codex_respawn(sup=sup, fake=fake, plan=(repo, topic, session), session_id=SID, **verify)
    return repo, topic, session, fake, sup


def test_recovery_never_reports_a_codex_resume_whose_pane_never_became_codex(*, tmp_path, capsys):
    _repo, _topic, _session, fake, sup = codex_recovery(tmp_path=tmp_path)
    fake.respawn_yields_codex = False

    assert sup.recover_missing_sessions() == []
    assert "codex_pane_never_became_codex" in capsys.readouterr().err


def test_recovery_never_reports_a_codex_resume_that_came_up_on_a_picker(*, tmp_path, capsys):
    _repo, _topic, _session, _fake, sup = codex_recovery(
        tmp_path=tmp_path,
        capture="Resume a previous session\n\n› 1. Choose a session\n  2. Start a new\n",
    )

    assert sup.recover_missing_sessions() == []
    assert "codex_resume_picker" in capsys.readouterr().err


def test_recovery_never_reports_a_codex_resume_holding_a_different_rollout(*, tmp_path, capsys):
    """The wrong-UUID case: a live Codex is not THIS track's resumed session."""
    _repo, _topic, _session, _fake, sup = codex_recovery(
        tmp_path=tmp_path, live=(tmp_path / "repo", OTHER_SID)
    )

    assert sup.recover_missing_sessions() == []
    assert "codex_live_process_missing" in capsys.readouterr().err


def test_recovery_never_reports_a_codex_resume_running_in_another_repository(*, tmp_path, capsys):
    """The wrong-cwd case: the resumed process must be in the track's own repository."""
    _repo, _topic, _session, _fake, sup = codex_recovery(
        tmp_path=tmp_path, live=(tmp_path / "somewhere-else", SID)
    )

    assert sup.recover_missing_sessions() == []
    assert "codex_live_process_missing" in capsys.readouterr().err


def test_recovery_never_reports_a_codex_resume_whose_kick_never_submitted(*, tmp_path, capsys):
    """A resumed Codex sitting idle never ran its kick, so the round is not a success."""
    _repo, _topic, _session, _fake, sup = codex_recovery(
        tmp_path=tmp_path, capture=codex_idle_capture()
    )

    assert sup.recover_missing_sessions() == []
    assert "codex_resume_kick_unconfirmed" in capsys.readouterr().err
