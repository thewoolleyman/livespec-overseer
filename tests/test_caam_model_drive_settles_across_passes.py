"""Multi-pass settling for caam model enforcement (work-item overseer-o3t75c.2).

The residual defect after overseer-o3t75c.1: the actuator stopped switching a
pane that was already on the wanted model, but enforcement kept DRIVING the
picker into it pass after pass. Every suppression the merged fix added lives in
the caam state file -- the time-boxed ``models`` memo and the ``models_unknown``
verify memo -- and a memo is only as good as the pass that has to write it back.
Measured live 2026-08-30 on daemon v1.67.2: ``models_unknown`` was never present
in ``~/.local/state/caam-usage-rotate/state.json`` at all and the foreman's
``models`` memo was frozen ~5.7h stale, so neither gate ever held and the drives
never stopped.

The sensor is what makes that fatal rather than merely untidy. A parked pane's
last assistant ``message.model`` line eventually falls out of the bounded
backward scan, and a ``/model`` drive used to append only lines the sensor could
not read -- so the unknown read was permanent and the ONLY thing standing between
it and an unbounded re-drive was a memo surviving to the next pass.

These tests run enforcement the way production runs it: several passes, spaced
past the suppress window, each loading and saving the real state file, with the
real transcript sensor reading a real file whose tail is full of model-free
``/model`` local-command entries -- and a fake actuator that leaves behind what a
real drive leaves behind. The settle must hold on the transcript alone, so the
second test takes the memo away exactly as production does.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
SESSION = "livespec-overseer-foreman"
SESSION_ID = "sid-parked-foreman"
# Past `_caam_transcript_model._SCAN_MAX_BYTES`, so the seeded assistant model
# line below is genuinely out of the sensor's reach -- the parked-pane state the
# live foreman was in.
MODEL_FREE_TAIL_BYTES = 1_100_000
# Two hours, so every pass after the first is past the 3600s `models` window.
PASS_INTERVAL_S = 7_200.0
PASS_COUNT = 6


def enforcement_module() -> ModuleType:
    assert (ROOT / "overseer" / "caam_enforcement.py").is_file()
    return importlib.import_module("caam_enforcement")


def sessions_module() -> ModuleType:
    assert (ROOT / "overseer" / "caam_sessions.py").is_file()
    return importlib.import_module("caam_sessions")


def transcript_line(*, content: str) -> str:
    return json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + "\n"


def local_command_lines(*, at_least_bytes: int) -> str:
    """The model-free tail a `/model` invocation entry leaves behind."""

    line = transcript_line(content="<command-name>/model</command-name>")
    return line * (at_least_bytes // len(line) + 1)


def drive_lines(*, answer: str) -> str:
    """What one real `/model` drive appends: the invocation AND its answer.

    The answer is the line the pane renders back -- "Kept model as Fable 5" when
    the picker is dismissed on the model it opened on, "Set model to Fable 5"
    when it switched. Both were read out of the live foreman's own transcript
    (`plan/caam-model-set-idempotence/research/model-set-spam-mechanism.md`).
    """

    return transcript_line(content="<command-name>/model</command-name>") + transcript_line(
        content=f"<local-command-stdout>{answer}</local-command-stdout>"
    )


def transcript_path(*, home: Path, session_id: str) -> Path:
    path = home / ".claude" / "projects" / "-work" / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def park_transcript(*, home: Path, session_id: str, model: str) -> Path:
    """A pane whose last readable model line is buried past the scan bound."""

    path = transcript_path(home=home, session_id=session_id)
    _ = path.write_text(
        json.dumps({"message": {"model": model}})
        + "\n"
        + local_command_lines(at_least_bytes=MODEL_FREE_TAIL_BYTES),
        encoding="utf-8",
    )
    return path


class RecordingDrive:
    """A `/model` drive that leaves the footprint a real one leaves."""

    def __init__(self, *, transcript: Path, answer: str) -> None:
        self.transcript = transcript
        self.answer = answer
        self.drives: list[tuple[str, str]] = []

    def __call__(self, *, session: str, model: str) -> None:
        self.drives.append((session, model))
        with self.transcript.open("a", encoding="utf-8") as handle:
            _ = handle.write(drive_lines(answer=self.answer))


def high_effort_settings(*, tmp_path: Path) -> Path:
    settings = tmp_path / "settings.json"
    _ = settings.write_text(json.dumps({"effortLevel": "high"}), encoding="utf-8")
    return settings


def pane_seams(*, session_id: str):
    def pane_pid(*, session: str) -> int:
        del session
        return 40

    def children_of(*, pid: int) -> list[int]:
        return [41] if pid == 40 else []

    def environ_of(*, pid: int) -> bytes:
        return f"CLAUDE_CODE_SESSION_ID={session_id}\0".encode() if pid == 41 else b""

    return pane_pid, children_of, environ_of


def run_pass(*, module: ModuleType, tmp_path: Path, state_path: Path, now: float, drive) -> None:
    pane_pid, children_of, environ_of = pane_seams(session_id=SESSION_ID)
    _ = module.enforce_models(
        settings_path=high_effort_settings(tmp_path=tmp_path),
        no_models=False,
        home=tmp_path,
        state_path=state_path,
        session_names=(SESSION,),
        active_fable=10.0,
        foreman_model=None,
        session_models=(),
        dry_run=False,
        now=now,
        pane_pid=pane_pid,
        children_of=children_of,
        environ_of=environ_of,
        set_model=drive,
    )


def test_spaced_passes_stop_re_driving_a_parked_pane_already_on_the_wanted_model(
    *, tmp_path: Path
) -> None:
    module = enforcement_module()
    state_path = tmp_path / "state" / "state.json"
    transcript = park_transcript(home=tmp_path, session_id=SESSION_ID, model="claude-fable-5")
    drive = RecordingDrive(transcript=transcript, answer="Kept model as Fable 5")

    for index in range(PASS_COUNT):
        run_pass(
            module=module,
            tmp_path=tmp_path,
            state_path=state_path,
            now=1000.0 + index * PASS_INTERVAL_S,
            drive=drive,
        )

    assert drive.drives == [(SESSION, "fable")]


def test_the_settle_survives_a_state_file_that_never_keeps_the_memo(*, tmp_path: Path) -> None:
    """The measured production condition: the memo never reaches the next pass.

    Live evidence had ``models_unknown`` absent and the ``models`` memo frozen
    5.7h stale while drives continued, which is what a pass re-saving a snapshot
    it loaded before another pass's write looks like from the outside. Whatever
    loses it, suppression must not depend on it: the pane's own transcript
    records the answer to every drive, so one drive is enough to settle it.
    """

    module = enforcement_module()
    state_path = tmp_path / "state" / "state.json"
    transcript = park_transcript(home=tmp_path, session_id=SESSION_ID, model="claude-fable-5")
    drive = RecordingDrive(transcript=transcript, answer="Kept model as Fable 5")

    for index in range(PASS_COUNT):
        before = state_path.read_text(encoding="utf-8") if state_path.exists() else None
        run_pass(
            module=module,
            tmp_path=tmp_path,
            state_path=state_path,
            now=1000.0 + index * PASS_INTERVAL_S,
            drive=drive,
        )
        if before is None:
            state_path.unlink(missing_ok=True)
        else:
            _ = state_path.write_text(before, encoding="utf-8")

    assert drive.drives == [(SESSION, "fable")]


def test_a_model_local_command_answer_in_the_tail_names_the_current_model(
    *, tmp_path: Path
) -> None:
    module = sessions_module()
    transcript = park_transcript(home=tmp_path, session_id="sid-answer", model="claude-opus-5")
    with transcript.open("a", encoding="utf-8") as handle:
        _ = handle.write(drive_lines(answer="Kept model as Fable 5"))

    assert module.pane_model(home=tmp_path, session_id="sid-answer") == "fable"


def test_a_switching_answer_names_the_model_it_switched_to(*, tmp_path: Path) -> None:
    module = sessions_module()
    transcript = park_transcript(home=tmp_path, session_id="sid-switched", model="claude-fable-5")
    with transcript.open("a", encoding="utf-8") as handle:
        _ = handle.write(drive_lines(answer="Set model to Opus 5 (1M context)"))

    assert module.pane_model(home=tmp_path, session_id="sid-switched") == "opus"


def test_a_later_assistant_line_outranks_an_earlier_answer(*, tmp_path: Path) -> None:
    module = sessions_module()
    transcript = park_transcript(home=tmp_path, session_id="sid-later", model="claude-opus-5")
    with transcript.open("a", encoding="utf-8") as handle:
        _ = handle.write(drive_lines(answer="Kept model as Fable 5"))
        _ = handle.write(json.dumps({"message": {"model": "claude-sonnet-5"}}) + "\n")

    assert module.pane_model(home=tmp_path, session_id="sid-later") == "sonnet"


def test_a_local_command_output_that_names_no_model_stays_unknown(*, tmp_path: Path) -> None:
    module = sessions_module()
    transcript = park_transcript(home=tmp_path, session_id="sid-other", model="claude-fable-5")
    with transcript.open("a", encoding="utf-8") as handle:
        _ = handle.write(
            transcript_line(
                content="<local-command-stdout>Shell cwd was reset</local-command-stdout>"
            )
        )

    assert module.pane_model(home=tmp_path, session_id="sid-other") is None


def test_an_answer_naming_no_known_family_stays_unknown(*, tmp_path: Path) -> None:
    module = sessions_module()
    transcript = park_transcript(home=tmp_path, session_id="sid-default", model="claude-fable-5")
    with transcript.open("a", encoding="utf-8") as handle:
        _ = handle.write(drive_lines(answer="Set model to Default (recommended)"))

    assert module.pane_model(home=tmp_path, session_id="sid-default") is None
