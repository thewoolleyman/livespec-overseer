"""Tests for caam model-set idempotence (work-item overseer-o3t75c.1).

Three legs of the same defect: the actuator drove a switch into a pane that was
already on the wanted model, the transcript sensor read ``None`` once a tail of
model-free local-command entries pushed the last assistant model line out of the
window, and an unknown read re-authorized that drive on every later pass.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
# The production tail read starts at this many bytes; the fixtures below pad
# past it deliberately so the sensor has to scan further back.
TAIL_BYTES = 65_536
# ... and stops growing at this many, so a model line further back than this is
# genuinely out of reach.
SCAN_MAX_BYTES = 1_048_576


def picker_module() -> ModuleType:
    assert (ROOT / "overseer" / "caam_picker.py").is_file()
    return importlib.import_module("caam_picker")


def sessions_module() -> ModuleType:
    assert (ROOT / "overseer" / "caam_sessions.py").is_file()
    return importlib.import_module("caam_sessions")


class FakePickerTmux:
    def __init__(self, *, captures: tuple[str, ...]) -> None:
        self._captures = list(captures)
        self.keys: list[str] = []

    def capture_pane(self, *, session: str) -> str:
        _ = session
        if not self._captures:
            return ""
        return self._captures.pop(0)

    def send_keys(self, *, session: str, keys: str) -> bool:
        _ = session
        self.keys.append(keys)
        return True

    def send_literal_keys(self, *, session: str, text: str) -> bool:
        _ = session
        self.keys.append(text)
        return True


class NoSleep:
    def __call__(self, seconds: float) -> None:
        del seconds


def local_command_lines(*, at_least_bytes: int) -> str:
    """A model-free transcript tail: what every ``/model`` invocation writes."""

    line = (
        json.dumps(
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": "<command-name>/model</command-name>",
                },
            }
        )
        + "\n"
    )
    return line * (at_least_bytes // len(line) + 1)


def transcript(*, home: Path, session_id: str, body: str) -> None:
    path = home / ".claude" / "projects" / "-work" / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(body, encoding="utf-8")


def test_picker_dismisses_without_switching_when_the_current_row_is_already_wanted() -> None:
    caam_picker = picker_module()
    tmux = FakePickerTmux(
        captures=(
            "❯\n",
            """
Select model
  1. Default     Opus 5
❯ 2. Fable      Fast model
  3. Opus       Larger model
""",
        )
    )

    outcome = caam_picker.drive_model_picker(
        tmux=tmux,
        session="alpha-foreman",
        want="fable",
        sleep=NoSleep(),
    )

    assert tmux.keys == ["/model", "Enter", "Escape"]
    assert "s" not in tmux.keys
    assert outcome == caam_picker.PICKER_ALREADY_SET
    assert outcome != caam_picker.PICKER_SWITCHED


def test_picker_still_switches_when_the_current_row_is_a_different_model() -> None:
    caam_picker = picker_module()
    tmux = FakePickerTmux(
        captures=(
            "❯\n",
            """
Select model
❯ 1. Fable      Fast model
  2. Opus       Larger model
""",
            """
Switch model?
❯ 1. No
  2. Yes
""",
        )
    )

    outcome = caam_picker.drive_model_picker(
        tmux=tmux,
        session="alpha-foreman",
        want="opus",
        sleep=NoSleep(),
    )

    assert tmux.keys == ["/model", "Enter", "Down", "s", "Down", "Enter"]
    assert outcome == caam_picker.PICKER_SWITCHED


def test_transcript_tail_of_local_command_lines_still_yields_the_older_model(
    *, tmp_path: Path
) -> None:
    module = sessions_module()
    transcript(
        home=tmp_path,
        session_id="sid-local",
        body=json.dumps({"message": {"model": "claude-fable-5"}})
        + "\n"
        + local_command_lines(at_least_bytes=TAIL_BYTES),
    )

    assert module.pane_model(home=tmp_path, session_id="sid-local") == "fable"


def test_transcript_scan_back_is_bounded_and_reports_unknown_beyond_it(*, tmp_path: Path) -> None:
    module = sessions_module()
    transcript(
        home=tmp_path,
        session_id="sid-far",
        body=json.dumps({"message": {"model": "claude-fable-5"}})
        + "\n"
        + local_command_lines(at_least_bytes=SCAN_MAX_BYTES),
    )

    assert module.pane_model(home=tmp_path, session_id="sid-far") is None


def test_unknown_model_read_authorizes_one_verify_and_then_stops_re_driving() -> None:
    module = sessions_module()
    calls: list[tuple[str, str]] = []
    state: dict[str, object] = {}

    def set_model(*, session: str, model: str) -> None:
        calls.append((session, model))

    pane = module.SessionModel(session="alpha-foreman", session_id="sid-unknown", model=None)
    first = module.enforce_session_models(
        panes=(pane,),
        state=state,
        want="fable",
        now=1000.0,
        set_model=set_model,
    )
    later = module.enforce_session_models(
        panes=(pane,),
        state=state,
        want="fable",
        now=1_000_000.0,
        set_model=set_model,
    )

    assert first == ["alpha-foreman unknown->fable"]
    assert later == []
    assert calls == [("alpha-foreman", "fable")]


def test_a_known_mismatch_still_acts_after_an_unknown_verify() -> None:
    module = sessions_module()
    calls: list[tuple[str, str]] = []
    state: dict[str, object] = {}

    def set_model(*, session: str, model: str) -> None:
        calls.append((session, model))

    unknown = module.SessionModel(session="alpha-foreman", session_id="sid", model=None)
    known = module.SessionModel(session="alpha-foreman", session_id="sid", model="opus")
    _ = module.enforce_session_models(
        panes=(unknown,),
        state=state,
        want="fable",
        now=1000.0,
        set_model=set_model,
    )
    acted = module.enforce_session_models(
        panes=(known,),
        state=state,
        want="fable",
        now=1_000_000.0,
        set_model=set_model,
    )
    settled = module.enforce_session_models(
        panes=(unknown,),
        state=state,
        want="fable",
        now=2_000_000.0,
        set_model=set_model,
    )

    assert acted == ["alpha-foreman opus->fable"]
    assert settled == ["alpha-foreman unknown->fable"]
    assert calls == [
        ("alpha-foreman", "fable"),
        ("alpha-foreman", "fable"),
        ("alpha-foreman", "fable"),
    ]
